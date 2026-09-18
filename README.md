# UF HiPerGator Skill

An agent skill and illustrated English guide for applying for and using the University of Florida HiPerGator cluster.

The application walkthrough is tailored to UCSB members sponsored by **Xin Eric Wang**. The operational skill supports other groups by using each user's own identity, scheduler permissions, and storage paths.

## Read the guide

- [Illustrated application, eduVPN, and SSH guide](references/application-guide.md)
- [Download the standalone HTML guide](https://github.com/namezhenzhang/UF-HiPerGator-Skill/raw/refs/heads/main/docs/UF_HiPerGator_Application_Guide.html), then open it in a browser. All seven screenshots are embedded.
- [Cluster usage and troubleshooting](references/cluster-usage.md)

Screenshots contain example applicant details. Enter your own name and email, upload your own public key, and use your own invitation email. The personal invitation-link screenshot is excluded.

## Install the skill

The repository root is the skill folder, with `SKILL.md`, `agents/`, `references/`, and `assets/` kept together.

For a manual Codex installation, clone into a new, unused skill directory:

```bash
git clone https://github.com/namezhenzhang/UF-HiPerGator-Skill.git ~/.codex/skills/ufhpg
```

If that directory already exists, inspect it before updating. For another agent, place the complete repository in that agent's supported skills directory. Reload the agent's skills after installation.

You can also ask your skill installer:

> Install the ufhpg skill from https://github.com/namezhenzhang/UF-HiPerGator-Skill.

Then invoke it with a request such as:

> Use $ufhpg to help me configure eduVPN and SSH for my new HiPerGator account.

> Use $ufhpg to prepare a single-GPU Slurm job using my existing allocation. Check my Account and QOS first.

## Included files

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Agent workflow and reference routing |
| `references/application-guide.md` | Screenshot-based account application and connection tutorial |
| `references/cluster-usage.md` | Storage, environment, scheduling and troubleshooting guidance |
| `references/ucsb-group.md` | Eric Wang group profile with live verification requirements |
| `assets/*.sbatch` | CPU and GPU smoke-test templates |
| `docs/UF_HiPerGator_Application_Guide.html` | Standalone illustrated document |

Templates contain placeholders and must be adapted before submission. Their shell syntax is checked; they have not been submitted against a reader's allocation. This repository does not provision accounts, purchase resources, or launch jobs automatically.

## Sources and maintenance

Official guidance was checked on **2026-09-18**. Follow the linked UF documentation and current scheduler state for policies, partitions, resource limits, and software versions. This is a community guide, not an official UF publication.

- [UF Research Computing documentation](https://docs.rc.ufl.edu/)
- [Federated account requests](https://docs.rc.ufl.edu/access/federated_request/)
- [Federated login](https://docs.rc.ufl.edu/access/federated_login/)
- [GPU access](https://docs.rc.ufl.edu/scheduler/gpu_access/)

## Origin

The operational guidance is adapted from the existing `hpg-slurm` Codex skill on the maintainer's HiPerGator account. It preserves live resource checks, shared QOS budgeting, pending-job diagnosis, and project-wrapper inspection. Personal work paths and historical quota numbers are excluded. The application and connection guide follows the supplied screenshots and reviewed instructions.

The root-level skill layout and installation presentation follow the pattern used by [blader/humanizer](https://github.com/blader/humanizer); no Humanizer skill text or code is copied.
