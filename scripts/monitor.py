#!/usr/bin/env python3
"""Read-only, one-shot Slurm account and visible-QOS resource summary."""
import argparse
import datetime as dt
import getpass
import json
import math
import os
import re
import subprocess
import sys

RESOURCES = ('cpu', 'gpu', 'mem_gib')
TERMINAL = {'COMPLETED', 'CANCELLED', 'FAILED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'}


class MonitorError(Exception):
    pass


def run(args):
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith('SQUEUE_') and k != 'SLURM_CLUSTERS'}
        p = subprocess.run(args, text=True, capture_output=True, timeout=45, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise MonitorError(f'{args[0]} failed: {e}') from e
    if p.returncode:
        raise MonitorError(f'{args[0]} exited {p.returncode}: {p.stderr.strip()[:600]}')
    return p.stdout, p.stderr.strip()


def number(value):
    if isinstance(value, dict):
        if not value.get('set') or value.get('infinite'):
            return None
        value = value.get('number')
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def memory_gib(value):
    m = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)([KMGTPE]?)(?:i?B)?', value, re.I)
    if not m:
        return None
    n, unit = float(m[1]), m[2].upper()
    return n * {'': 1/1024, 'K': 1/1024**2, 'M': 1/1024, 'G': 1, 'T': 1024, 'P': 1024**2, 'E': 1024**3}[unit]


def tres_values(raw, limits=False):
    result = dict.fromkeys(RESOURCES)
    if not isinstance(raw, str) or not raw.strip():
        return result
    fields = {}
    for part in raw.split(','):
        if '=' not in part:
            continue
        key, val = part.strip().split('=', 1)
        fields[key] = val
    def count(val):
        return int(val) if val is not None and re.fullmatch(r'\d+', val) else None
    result['cpu'] = count(fields.get('cpu'))
    result['mem_gib'] = memory_gib(fields['mem']) if 'mem' in fields else None
    if 'gres/gpu' in fields:
        result['gpu'] = count(fields['gres/gpu'])
    elif not limits:
        typed = [count(v) for k, v in fields.items() if k.startswith('gres/gpu:')]
        result['gpu'] = sum(typed) if all(v is not None for v in typed) else None
    return result


def array_count(expression):
    """Count Slurm's compressed array syntax without expanding large ranges."""
    s = expression.strip().strip('[]').split('%', 1)[0]
    if not s:
        return 1
    total = 0
    for part in s.split(','):
        m = re.fullmatch(r'(\d+)(?:-(\d+)(?::(\d+))?)?', part)
        if not m:
            raise MonitorError(f'Unrecognized array range: {expression}')
        lo, hi, step = int(m[1]), int(m[2] or m[1]), int(m[3] or 1)
        if hi < lo or step < 1:
            raise MonitorError(f'Invalid array range: {expression}')
        total += (hi-lo)//step + 1
    return total


def parse_job(j):
    states = j.get('job_state')
    if isinstance(states, str):
        states = [states]
    if not states or not isinstance(states, list):
        raise MonitorError('Job state missing from Slurm JSON')
    state = states[0]
    account, qos = j.get('account'), j.get('qos')
    if not account or not qos or j.get('job_id') is None:
        raise MonitorError('Job identity/account/QOS missing from Slurm JSON')
    expr = j.get('array_task_string') or ''
    task = number(j.get('array_task_id'))
    parent = number(j.get('array_job_id'))
    count = array_count(expr) if expr else 1
    jid = str(j['job_id'])
    if parent and expr:
        jid = f'{int(parent)}_[{expr}]'
    elif parent and task is not None:
        jid = f'{int(parent)}_{int(task)}'
    pending = state == 'PENDING'
    raw = j.get('tres_req_str' if pending else 'tres_alloc_str')
    resources = tres_values(raw)
    # Pending mem=0 can mean all memory, not a known zero-byte request.
    if pending and resources['mem_gib'] == 0:
        resources['mem_gib'] = None
    if count != 1 and not pending:
        raise MonitorError('Compressed non-pending array cannot be summed safely')
    # Suspended/configuring/completing resource release can be partial.
    # Keep them visible, but do not claim precise headroom.
    if not pending and (state != 'RUNNING' or any(f in states[1:] for f in ('COMPLETING', 'CONFIGURING', 'RESIZING', 'SUSPENDED'))) and state not in TERMINAL:
        resources = dict.fromkeys(RESOURCES)
    resources = {k: v * count if v is not None else None for k, v in resources.items()}
    start = number(j.get('start_time'))
    return dict(id=jid, account=account, qos=qos, user=j.get('user_name') or str(j.get('user_id', '?')),
                state=state, state_flags=states[1:], count=count, resources=resources,
                partition=j.get('partition', ''), name=j.get('name', ''),
                reason=j.get('state_reason', ''), start_epoch=start, tres=raw or '')


def aggregate(jobs):
    total = {'jobs': 0, **dict.fromkeys(RESOURCES, 0)}
    for job in jobs:
        total['jobs'] += job['count']
        for key in RESOURCES:
            v = job['resources'][key]
            total[key] = None if v is None or total[key] is None else total[key] + v
    return total


def association_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cells = line.split('|')
        if len(cells) < 5:
            raise MonitorError('Unexpected sacctmgr association format')
        rows.append(dict(zip(('cluster', 'account', 'user', 'qos', 'default_qos'), cells)))
    return rows


def select_account(rows, requested, user):
    accounts = sorted({r['account'] for r in rows if r['user'] == user and r['account']})
    if requested:
        if requested not in accounts:
            raise MonitorError(f'Account {requested!r} not in your associations: {", ".join(accounts)}')
        return requested
    if len(accounts) != 1:
        raise MonitorError('Choose --account from: ' + (', '.join(accounts) or '(no visible accounts)'))
    return accounts[0]


def read_jobs(filter_arg):
    out, stderr = run(['squeue', '--local', '--all', '--json', '--array', filter_arg])
    try:
        snapshot = json.loads(out)
    except ValueError as e:
        raise MonitorError('Invalid squeue JSON') from e
    if not isinstance(snapshot, dict) or snapshot.get('errors') or not isinstance(snapshot.get('jobs'), list):
        raise MonitorError('squeue returned errors or an unsupported JSON schema')
    warnings = ([stderr] if stderr else [])
    if snapshot.get('warnings'):
        warnings.append('Slurm JSON warnings: ' + json.dumps(snapshot['warnings']))
    return [parse_job(j) for j in snapshot['jobs']], warnings


def collect(account_arg=None):
    warnings = []
    user = getpass.getuser()
    out, err = run(['sacctmgr', '-n', '-P', 'show', 'assoc', f'user={user}',
                    'format=Cluster,Account,User,QOS,DefaultQOS'])
    if err:
        warnings.append(err)
    rows = association_rows(out)
    account = select_account(rows, account_arg, user)
    # Cluster-local snapshot; reject ambiguous multi-cluster associations.
    config = None
    try:
        config, err = run(['scontrol', 'show', 'config'])
        if err:
            warnings.append(err)
    except MonitorError as e:
        warnings.append(str(e))
    cluster_match = re.search(r'^\s*ClusterName\s*=\s*(\S+)', config or '', re.M)
    cluster = cluster_match[1] if cluster_match else None
    relevant = [r for r in rows if r['account'] == account and r['user'] == user and (not cluster or r['cluster'] == cluster)]
    if not relevant or len({r['cluster'] for r in relevant}) != 1:
        raise MonitorError('Cannot resolve the selected account on one local cluster')
    cluster = cluster or relevant[0]['cluster']
    qos_names = set()
    for r in relevant:
        qos_names.update(q for q in r['qos'].split(',') if q)
        if r['default_qos']:
            qos_names.add(r['default_qos'])
    account_jobs, account_warnings = read_jobs(f'--account={account}')
    warnings.extend(account_warnings)
    own = [j for j in account_jobs if j['account'] == account and j['state'] not in TERMINAL]
    qos_names.update(j['qos'] for j in own)
    if not qos_names:
        raise MonitorError('No QOS visible for selected account')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', q) for q in qos_names):
        raise MonitorError('Unresolved QOS list; inspect sacctmgr associations')
    qcsv = ','.join(sorted(qos_names))
    out, err = run(['sacctmgr', '-n', '-P', 'show', 'qos', f'name={qcsv}', 'format=Name,GrpTRES,Flags'])
    if err:
        warnings.append(err)
    limits = {}
    relative_qos = set()
    raw_limits = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        cells = line.split('|')
        if len(cells) < 2:
            raise MonitorError('Unexpected QOS format')
        limits[cells[0]] = tres_values(cells[1], limits=True)
        if len(cells) > 2 and 'relative' in cells[2].lower():
            relative_qos.add(cells[0])
            limits[cells[0]] = dict.fromkeys(RESOURCES)
            warnings.append(f'{cells[0]} uses Relative QOS limits; absolute headroom is unknown.')
        raw_limits[cells[0]] = cells[1]
    if not qos_names.issubset(limits):
        raise MonitorError('Some selected QOS limits could not be read')
    # A second batch includes other accounts sharing any QOS used by this account.
    jobs, queue_warnings = read_jobs(f'--qos={qcsv}')
    warnings.extend(queue_warnings)
    jobs = [j for j in jobs if j['state'] not in TERMINAL and j['qos'] in qos_names]
    private = re.search(r'^\s*PrivateData\s*=\s*(.*)$', config or '', re.M)
    privacy_known = private is not None
    private_jobs = bool(private and re.search(r'\b(jobs|all)\b', private[1], re.I))
    complete_scope = privacy_known and not private_jobs and not queue_warnings and not account_warnings
    if not complete_scope:
        warnings.append('Job visibility may be restricted or incomplete; QOS headroom is unknown.')
    users = {}
    for name in sorted({j['user'] for j in own}):
        uj = [j for j in own if j['user'] == name]
        users[name] = dict(running=aggregate(j for j in uj if j['state'] == 'RUNNING'),
                           pending=aggregate(j for j in uj if j['state'] == 'PENDING'),
                           other=aggregate(j for j in uj if j['state'] not in ('RUNNING', 'PENDING')))
    qos = {}
    for name in sorted(qos_names):
        qj = [j for j in jobs if j['qos'] == name]
        allocated = aggregate(j for j in qj if j['state'] != 'PENDING')
        pending = aggregate(j for j in qj if j['state'] == 'PENDING')
        cap = limits[name]
        remaining = {k: cap[k]-allocated[k] if complete_scope and cap[k] is not None and allocated[k] is not None else None for k in RESOURCES}
        qos[name] = dict(limits=cap, limits_tres=raw_limits[name], allocated=allocated,
                         pending=pending, headroom_estimate=remaining,
                         visible_accounts=sorted({j['account'] for j in qj}))
    incomplete = any(v is None for j in jobs + own for v in j['resources'].values())
    if incomplete:
        warnings.append('Some job resources are unknown; affected totals and headroom are null.')
    return dict(schema_version=1, timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
                user=user, account=account, cluster=cluster,
                scope='visible jobs across all accounts using selected QOS on the local cluster',
                visibility_complete=complete_scope, complete=complete_scope and not incomplete and not relative_qos,
                warnings=warnings, users=users, qos=qos, jobs=own,
                notes=['Allocated resources, not measured CPU/GPU/RAM utilization.',
                       'Pending is demand, not reserved capacity. Headroom does not guarantee scheduling.',
                       'QOS GrpTRES only; association, partition, typed GPU, and per-job limits may also apply.'])


def fmt(v):
    if v is None:
        return '?'
    return (str(int(v)) if v.is_integer() else f'{v:.1f}') if isinstance(v, float) else str(v)


def clean(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def table(headers, rows):
    rows = [[clean(v) for v in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    for row in [headers] + rows:
        print('  '.join(v.ljust(widths[i]) for i, v in enumerate(row)))


def render(data, detail=False):
    color = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
    def heading(s):
        print(('\033[1;36m' if color else '') + s + ('\033[0m' if color else ''))
    heading('Slurm account resource summary')
    print(f"Account: {data['account']}  Cluster: {data['cluster']}  User: {data['user']}")
    print('Snapshot: ' + data['timestamp'])
    heading('\nAccount usage by user')
    rows = []
    for user, info in data['users'].items():
        r, p, o = info['running'], info['pending'], info['other']
        rows.append([user, fmt(r['jobs']), fmt(r['cpu']), fmt(r['gpu']), fmt(r['mem_gib']), fmt(p['jobs']), fmt(p['cpu']), fmt(p['gpu']), fmt(p['mem_gib']), fmt(o['jobs'])])
    table(['USER', 'RUN', 'CPU', 'GPU', 'GiB', 'PEND', 'P_CPU', 'P_GPU', 'P_GiB', 'OTHER'], rows)
    if not rows:
        print('(no visible active jobs in this account)')
    heading('\nQOS allocation across visible accounts')
    for name, q in data['qos'].items():
        print(f"\n{name}  visible accounts: {', '.join(q['visible_accounts']) or '(none)'}")
        for key in RESOURCES:
            used, cap = q['allocated'][key], q['limits'][key]
            bar = '?' * 20
            if cap == 0 and used is not None:
                bar = '·'*20 if used == 0 else '█'*20
            if used is not None and cap is not None and cap > 0:
                n = max(0, min(20, round(20*used/cap)))
                bar = '█'*n + '·'*(20-n)
            tint = '\033[31m' if cap and used is not None and used/cap >= .9 else '\033[32m'
            if color:
                bar = tint + bar + '\033[0m'
            print(f"  {key:8} [{bar}] allocated={fmt(used)} cap={fmt(cap) if cap is not None else 'not-set'} headroom~={fmt(q['headroom_estimate'][key])} pending-demand={fmt(q['pending'][key])}")
        print('  GrpTRES: ' + (q['limits_tres'] or '(not set)'))
    if detail:
        heading('\nAccount job details')
        rows = []
        now = dt.datetime.now().timestamp()
        for j in data['jobs']:
            start = j['start_epoch']
            eta = '-'
            if j['state'] == 'PENDING':
                eta = 'unknown' if not start else ('stale estimate' if start <= now else f'~{math.ceil((start-now)/60)}m')
            r = j['resources']
            rows.append([j['id'], j['user'], j['state'], str(j['count']), j['partition'], j['name'], j['qos'], fmt(r['cpu']), fmt(r['gpu']), fmt(r['mem_gib']), eta, j['reason']])
        table(['JOB', 'USER', 'STATE', 'TASKS', 'PARTITION', 'NAME', 'QOS', 'CPU', 'GPU', 'GiB', 'ETA', 'REASON'], rows)
    print()
    for note in data['notes']:
        print(note)
    for warning in data['warnings']:
        print('WARNING: ' + warning)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', help='Slurm account; required when you have multiple accounts')
    parser.add_argument('--detail', action='store_true', help='include account job details in terminal output')
    parser.add_argument('--json', action='store_true', help='machine-readable snapshot; unknown values are null')
    args = parser.parse_args()
    try:
        data = collect(args.account)
    except MonitorError as e:
        if args.json:
            print(json.dumps({'schema_version': 1, 'complete': False, 'error': str(e)}))
        else:
            print('ERROR: ' + str(e), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, indent=2, allow_nan=False))
    else:
        render(data, args.detail)
    return 0 if data['complete'] else 3


if __name__ == '__main__':
    sys.exit(main())
