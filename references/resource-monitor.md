# Read-only resource monitor

Run `bash scripts/monitor.sh` from this skill's directory on a HiPerGator login node. It requires Python 3.8+ and Slurm clients with the JSON job fields used by HPG Slurm 25.11.8. No third-party Python packages are required. Unsupported schemas or failed required queries produce an error, not an idle-cluster report.

```bash
bash scripts/monitor.sh
bash scripts/monitor.sh --account YOUR_ACCOUNT
bash scripts/monitor.sh --summary
bash scripts/monitor.sh --json
```

The default view includes active users, colored QOS allocation bars, and task identities, names, partitions, reasons, and available start estimates. Use `--summary` to hide task details. `--detail` remains supported and explicitly selects the default view. `NO_COLOR=1` disables color. Pending start times are scheduler estimates and may be absent or stale.

Use this helper when the user asks about group resource allocation or when shared limits matter to submission planning. Do not run it before syntax explanations or every script edit. It takes one snapshot, without polling, submission, cancellation, installation, or configuration changes.

## Interpretation

- The account defaults only when the current user has one visible account. Multiple accounts require `--account`.
- Two batch JSON queries collect selected-account jobs and then jobs across visible accounts sharing the relevant QOS on the local cluster. The QOS set includes both the user association and QOS found on account jobs, so other members with different QOS are included. This prevents counting just the selected account against a shared QOS limit. Array elements are expanded by Slurm where supported; compressed ranges are counted without expanding them in Python. Pending totals are aggregate demand, not a prediction that every array task can run concurrently.
- CPU, GPU, and memory come from allocated TRES for running jobs and requested TRES for pending jobs. Generic and typed GPU counts are not double-counted. These are allocation quantities, not measured utilization or GPU VRAM.
- Headroom is an estimate of QOS GrpTRES minus visible allocation. Pending demand is separate. Physical availability, reservations, priority, association, partition, typed GPU and per-job limits still affect scheduling. No generic QOS cap is displayed as `not-set`, not as unlimited runnable capacity.
- The monitor checks `PrivateData` before presenting numeric headroom. If job visibility cannot be established, the result is marked incomplete and headroom is unknown. Missing resource fields or transitional states also make affected totals unknown. Relative QOS limits are not converted to absolute capacities.
- Queries are separate snapshots, so values may change during collection. Refresh near an actual submission if the estimate matters; avoid rapid polling of the scheduler.

## JSON and exit status

JSON includes `schema_version`, timestamp, account, cluster, scope, visibility, warnings, per-user totals, per-QOS totals, and selected-account job details. Unknown numbers are `null`, never silently zero.

| Exit | Meaning |
| --- | --- |
| 0 | Snapshot collected with complete required visibility and resource fields |
| 1 | Required query, schema, or account selection failed; JSON includes an error |
| 2 | Invalid command-line usage |
| 3 | Usable but incomplete snapshot; inspect warnings and null values |

A code of 0 does not guarantee that a new job can start. Scripts consuming JSON should distinguish exit 3 from a total query failure. Detailed output includes job names and users; keep personal snapshots out of the public repository.

## Validation

Run the synthetic regression suite locally:

```bash
python3 -m unittest discover -s tests -v
```

It covers failed queries, missing allocation fields, memory units, GPU counting, compressed arrays, multiple accounts, shared QOS usage, pending demand, restricted visibility, and relative limits. Live checks are read-only; no workload submission is needed to validate the monitor.
