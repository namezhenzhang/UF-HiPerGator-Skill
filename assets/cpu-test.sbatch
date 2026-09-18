#!/bin/bash
#SBATCH --job-name=hpg_cpu_test
#SBATCH --account=YOUR_ACCOUNT
#SBATCH --qos=YOUR_CPU_QOS
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=logs/cpu_%j.out
#SBATCH --error=logs/cpu_%j.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
hostname
date
printf "CPU test completed\n" > "results/cpu_${SLURM_JOB_ID}.txt"
