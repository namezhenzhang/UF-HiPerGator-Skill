import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).parents[1]/'scripts/monitor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def job(**kw):
    d = dict(job_id=123, job_state=['RUNNING'], account='a', qos='q', user_name='alice',
             tres_alloc_str='cpu=8,mem=16G,gres/gpu=2,gres/gpu:l4=2',
             tres_req_str='cpu=8,mem=16G,gres/gpu=2')
    d.update(kw)
    return d


def runner(jobs=None, private='none', fail=None, accounts='a', warnings=None, flags=''):
    def call(cmd):
        if cmd[0] == fail:
            raise m.MonitorError('unavailable')
        if cmd[0] == 'scontrol':
            return f'ClusterName = hpg\nPrivateData = {private}\n', ''
        if cmd[0] == 'squeue':
            assert '--qos=q' in cmd or '--account=a' in cmd
            assert '--array' in cmd and '--local' in cmd and '--all' in cmd
            selected = [j for j in (jobs or []) if j['account'] == 'a'] if '--account=a' in cmd else jobs or []
            return json.dumps(dict(jobs=selected, errors=[], warnings=warnings or [])), ''
        if 'assoc' in cmd:
            return ''.join(f'hpg|{a}|alice|q|q|\n' for a in accounts.split(',')), ''
        return f'q|cpu=32,mem=64G,gres/gpu=4|{flags}|\n', ''
    return call


class Tests(unittest.TestCase):
    def collect(self, **kw):
        with patch.object(m, 'run', side_effect=runner(**kw)), patch.object(m.getpass, 'getuser', return_value='alice'):
            return m.collect()

    def test_tres_memory_and_gpu_not_double_counted(self):
        self.assertEqual(m.parse_job(job())['resources'], dict(cpu=8, mem_gib=16, gpu=2))

    def test_typed_gpu_sum_without_generic(self):
        self.assertEqual(m.tres_values('cpu=1,mem=1024M,gres/gpu:l4=2,gres/gpu:b200=1')['gpu'], 3)
        self.assertIsNone(m.tres_values('gres/gpu:l4=2', limits=True)['gpu'])

    def test_array_ranges_and_throttle(self):
        self.assertEqual(m.array_count('0-70'), 71)
        self.assertEqual(m.array_count('0-8:2,11,15-17%3'), 9)
        j = m.parse_job(job(job_state=['PENDING'], array_job_id=100, array_task_string='0-70'))
        self.assertEqual(j['count'], 71)
        self.assertEqual(j['resources']['mem_gib'], 1136)
        self.assertEqual(j['id'], '100_[0-70]')

    def test_array_bad_or_truncated_fails(self):
        for s in ['0-7...', '8-1', '1-8:0']:
            with self.assertRaises(m.MonitorError): m.array_count(s)

    def test_expanded_array_task_zero(self):
        j=m.parse_job(job(array_job_id={'set':True,'number':100}, array_task_id={'set':True,'number':0}))
        self.assertEqual(j['id'], '100_0')
        self.assertEqual(j['count'], 1)

    def test_queue_failure_never_idle(self):
        with self.assertRaises(m.MonitorError): self.collect(fail='squeue')

    def test_missing_allocations_unknown(self):
        d=self.collect(jobs=[job(tres_alloc_str='')])
        self.assertFalse(d['complete'])
        self.assertIsNone(d['qos']['q']['headroom_estimate']['gpu'])

    def test_shared_qos_other_account(self):
        d=self.collect(jobs=[job(tres_alloc_str='cpu=2,mem=2G,gres/gpu=1'),
                             job(job_id=456,account='b',user_name='bob')])
        self.assertEqual(d['qos']['q']['headroom_estimate']['gpu'],1)
        self.assertEqual(d['users']['alice']['running']['gpu'],1)
        self.assertEqual(len(d['jobs']),1)
        self.assertEqual(d['qos']['q']['visible_accounts'],['a','b'])

    def test_pending_demand_does_not_consume_headroom(self):
        d=self.collect(jobs=[job(job_state=['PENDING'])])
        self.assertEqual(d['qos']['q']['headroom_estimate']['gpu'],4)
        self.assertEqual(d['qos']['q']['pending']['gpu'],2)

    def test_restricted_visibility_unknown(self):
        d=self.collect(private='jobs',jobs=[job()])
        self.assertFalse(d['complete'])
        self.assertIsNone(d['qos']['q']['headroom_estimate']['cpu'])

    def test_config_failure_keeps_visible_usage_not_balance(self):
        d=self.collect(fail='scontrol',jobs=[job()])
        self.assertEqual(d['qos']['q']['allocated']['cpu'],8)
        self.assertIsNone(d['qos']['q']['headroom_estimate']['cpu'])

    def test_multiple_accounts_requires_choice(self):
        with self.assertRaises(m.MonitorError): self.collect(accounts='a,b')
        rows=m.association_rows('hpg|a|alice|q|q|\nhpg|b|alice|q|q|')
        self.assertEqual(m.select_account(rows,'b','alice'),'b')
        with self.assertRaises(m.MonitorError): m.select_account(rows,'c','alice')

    def test_transitional_state_not_silently_ignored(self):
        d=self.collect(jobs=[job(job_state=['COMPLETING'])])
        self.assertFalse(d['complete'])
        self.assertEqual(d['users']['alice']['other']['jobs'],1)

    def test_warning_prevents_confident_headroom(self):
        d=self.collect(jobs=[job()],warnings=[{'description':'partial'}])
        self.assertFalse(d['complete'])
        self.assertIsNone(d['qos']['q']['headroom_estimate']['gpu'])

    def test_relative_qos_not_treated_as_absolute(self):
        d=self.collect(flags='Relative')
        self.assertFalse(d['complete'])
        self.assertIsNone(d['qos']['q']['headroom_estimate']['cpu'])

    def test_other_account_member_qos_discovered(self):
        calls=[]
        def query(cmd):
            calls.append(cmd)
            if cmd[0]=='scontrol': return 'ClusterName = hpg\nPrivateData = none\n',''
            if 'assoc' in cmd: return 'hpg|a|alice|q|q|',''
            if cmd[0]=='sacctmgr': return 'q|cpu=32,mem=64G,gres/gpu=4|\nother|cpu=10,mem=10G,gres/gpu=0|',''
            js=[job(qos='other',user_name='bob',tres_alloc_str='cpu=2,mem=2G')]
            return json.dumps(dict(jobs=js,errors=[],warnings=[])),''
        with patch.object(m,'run',side_effect=query), patch.object(m.getpass,'getuser',return_value='alice'):
            d=m.collect()
        self.assertIn('bob',d['users'])
        self.assertIn('other',d['qos'])
        self.assertTrue(any('--qos=other,q' in cmd for cmd in calls))

    def test_empty_success_is_zero(self):
        d=self.collect()
        self.assertTrue(d['complete'])
        self.assertEqual(d['qos']['q']['allocated']['gpu'],0)
        self.assertEqual(d['qos']['q']['headroom_estimate']['gpu'],4)


if __name__ == '__main__': unittest.main()
