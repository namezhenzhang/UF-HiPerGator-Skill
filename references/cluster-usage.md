# HiPerGator cluster usage

Official documentation checked: 2026-09-18. Commands below use placeholders, not a particular person's account.

## Access and allocation

Federated users connect eduVPN to UF, authenticate using the institution bound to their account, and use an SSH key for `hpg.rc.ufl.edu`. See [the illustrated guide](application-guide.md) for setup. HPG passwords are not a fallback for federated SSH.

On the cluster, inspect identity and scheduling associations:

```bash
whoami
id
module load ufrc
showAssoc
showQos YOUR_QOS
showAllocation -g YOUR_GROUP
sinfo -s
scontrol show partition
squeue -u "$USER" -o "%.18i %.9P %.20j %.2t %.10M %.9l %.6D %R"
```

Use the Account/QOS association actually available to the user. A Linux group name alone does not prove a valid scheduler combination. The UCSB example group is `ericxwang.ucsb`, but its current resource quantities are intentionally not hard-coded.

Sources: [UFRC tools](https://docs.rc.ufl.edu/software/ufrc_tools/), [Account and QOS](https://docs.rc.ufl.edu/scheduler/qos_limits/).

## Storage

- `/home`: configuration and small scripts; not job data I/O.
- `/blue/YOUR_GROUP/YOUR_HPG_USERNAME`: typical active project location. Confirm the path and write access; secondary group directories may need setup.
- `/orange/YOUR_GROUP`: archival storage when allocated, not the default for heavy job I/O.
- `$SLURM_TMPDIR`: job-local scratch, removed when the job ends. Copy necessary results back to Blue before exit.

Some paths automount on access. Try the known full path before concluding that a directory is missing. Use `home_quota`, `blue_quota`, or `orange_quota` to inspect quotas. Maintain a separate backup plan for important data.

Source: [Practical Storage](https://docs.rc.ufl.edu/quickstart/practical_storage/).

## Prepare and submit a smoke test

Create a project directory under a confirmed writable Blue path. Copy the appropriate template from `assets/`, replace Account/QOS values and any partition choices, then prepare its output directories:

```bash
mkdir -p logs results
bash -n cpu-test.sbatch
sbatch cpu-test.sbatch
```

Run these from the project directory. `sbatch` returns a Job ID, not proof of execution. `#SBATCH` values do not expand shell variables.

The GPU template requests one L4 in `hpg-turin`. The official GPU guide also lists `hpg-rtx6000` for RTX6000 and `hpg-b200` for B200. Recheck these against current documentation and the user's allocation. Each GPU requires at least one CPU core; GPU burst QOS is not available. Templates request modest resources only to test scheduling, not to establish appropriate training requirements.

Sources: [Slurm commands](https://docs.rc.ufl.edu/scheduler/slurm_commands/), [GPU access](https://docs.rc.ufl.edu/scheduler/gpu_access/).

### Resource limits are shared across jobs

Check both the user's association and the Account/QOS limits. A group's CPU and memory quota can be much smaller than a physical GPU node's capacity. Count the group's other running jobs when planning parallel submissions, and respect the stricter applicable QOS and partition wall-time limits.

Use additional scheduler queries when the UFRC summary tools do not expose enough detail:

```bash
sacctmgr -n -P show assoc user="$USER" format=Cluster,Account,User,Partition,QOS,DefaultQOS
sacctmgr -n -P show qos YOUR_QOS format=Name,Priority,MaxWall,MaxSubmitPU,GrpTRES,Flags
sinfo -o '%P|%a|%D|%t|%G|%c|%m|%f'
```

A `DenyOnLimit` flag can cause requests exceeding applicable limits to be rejected immediately. Do not reduce a job's memory request below its measured need just to pass submission.

## Software and interactive work

Discover modules with `module spider python`, `module spider conda`, and `module list`. Prefer an existing suitable environment. For a new environment or sustained debugging, first request an authorized interactive allocation, for example:

```bash
srun --account=YOUR_ACCOUNT --qos=YOUR_CPU_QOS \
  --nodes=1 --ntasks=1 --cpus-per-task=2 \
  --mem=8G --time=00:30:00 --pty bash -i
```

Once a compute shell is allocated:

```bash
module load conda
conda create -p /blue/YOUR_GROUP/YOUR_HPG_USERNAME/envs/demo python=3.11 -y
conda activate /blue/YOUR_GROUP/YOUR_HPG_USERNAME/envs/demo
python --version
```

Python 3.11 is illustrative; use the project's required version. End the interactive session with `exit`. In a batch script, load the required module and activate the exact environment before invoking the user's program. Do not silently modify a shared environment or global shell configuration.

Sources: [Development and Testing](https://docs.rc.ufl.edu/quickstart/development_testing/), [Conda creation](https://docs.rc.ufl.edu/software/conda_creation/), [Conda in scripts](https://docs.rc.ufl.edu/software/conda_using_environments/).

## Inspect results and troubleshoot

```bash
squeue -u "$USER"
scontrol show job JOB_ID
sacct -j JOB_ID --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

Replace `JOB_ID` with the returned number. Inspect both `.out` and `.err` logs and expected output files. Cancel a specific user-authorized job with `scancel JOB_ID`.

| Symptom | Check |
| --- | --- |
| SSH timeout | VPN connection and hostname |
| Public key denied | Assigned HPG username, matching key, key permissions |
| Web identity mismatch | Institution associated with the existing HPG account |
| Invalid Account or QOS | Actual `showAssoc` output and allocation permissions |
| `QOSGrpGRES`, `QOSGrpTRES`, or related QOS reasons | Shared resource limits or usage; wait or revise a request only if the workload permits |
| `AssocGrpMemLimit` or memory QOS reasons | Group memory allocation and other jobs; CPU-only jobs may have a different eligible QOS |
| `Resources` | Matching resources are unavailable; inspect requested shape and current nodes |
| `Priority` | Waiting behind other jobs; this is not an application failure |
| `ReqNodeNotAvail` | Requested nodes may be unavailable, drained, down, or reserved; inspect before changing constraints |
| CPU out of memory | Requested RAM and application memory demand |
| CUDA out of memory | GPU VRAM, workload size, and GPU type; `--mem` does not add VRAM |
| Completed without expected result | Application logs, exit handling, working directory and output paths |

For support, collect the Job ID, resource requests, working directory, and relevant redacted errors. Exclude credentials and sensitive datasets.

Sources: [Job states](https://docs.rc.ufl.edu/scheduler/job_states/), [Support](https://support.rc.ufl.edu/).

## File transfers and browser access

Use [Open OnDemand](https://ood.rc.ufl.edu/) for browser-based file access and scheduled interactive apps. Ordinary HPG Shell access is not itself a compute allocation. End interactive apps when finished.

With a configured `hpg` SSH alias, run transfers on the local computer:

```bash
rsync -avP ./project/ hpg:/blue/YOUR_GROUP/YOUR_HPG_USERNAME/project/
rsync -avP hpg:/blue/YOUR_GROUP/YOUR_HPG_USERNAME/project/results/ ./results/
```

Confirm destinations and existing files before copying. For large datasets, consider [Globus](https://docs.rc.ufl.edu/data_transfer/globus/). Source: [Data Transfer](https://docs.rc.ufl.edu/data_transfer/overview/).

## Existing project launchers

The source HPG skill also covered a project-specific training launcher. For another repository, inspect the actual wrapper and its dry-run mode before reusing its resource pattern. Check whether it synchronizes files, overrides Account/QOS, starts Ray or other services, or changes container mounts. Only run a wrapper when its side effects are within the user's request. Keep project-specific paths and credentials outside this reusable skill.
