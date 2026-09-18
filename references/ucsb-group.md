# Xin Eric Wang UCSB group

Use this profile only for members or authorized collaborators of this group.

## Application

- Sponsor: **Xin Eric Wang**.
- Sponsor email: `ericxwang@ucsb.edu`.
- Organization for UCSB applicants: `University of California, Santa Barbara`.
- Linux group: `ericxwang.ucsb`.
- Application route: the [federated application tutorial](application-guide.md).

Each applicant uses their own name, email, public key, invitation link, and assigned HPG username. The identity provider used for an existing account can differ from the sponsor's institution; follow that account's binding.

## Scheduling

The existing remote `hpg-slurm` skill identified these group-specific resource names:

| Purpose | Account | QOS |
| --- | --- | --- |
| Investment allocation, including authorized GPU work | `ericxwang.ucsb` | `ericxwang.ucsb` |
| CPU-only burst allocation | `ericxwang.ucsb` | `ericxwang.ucsb-b` |

These are lookup candidates, not proof of a new member's permissions. Verify with `showAssoc` and current scheduler queries before using them. Do not send GPU jobs to the CPU-only burst QOS.

```bash
module load ufrc
showAssoc
showQos ericxwang.ucsb
showQos ericxwang.ucsb-b
showAllocation -g ericxwang.ucsb
```

The source skill included historical resource quantities. Those quantities are intentionally omitted because allocations and usage change. Pay particular attention to shared CPU and memory limits when launching GPU jobs.

A typical Blue path is `/blue/ericxwang.ucsb/YOUR_HPG_USERNAME`. Confirm its existence and permissions before creating files. Do not substitute another member's username.
