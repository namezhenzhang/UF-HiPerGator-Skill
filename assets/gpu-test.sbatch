#!/bin/bash
#SBATCH --job-name=hpg_gpu_test
#SBATCH --account=YOUR_ACCOUNT
#SBATCH --qos=YOUR_GPU_QOS
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --output=logs/gpu_%j.out
#SBATCH --error=logs/gpu_%j.err
#SBATCH --partition=hpg-turin
#SBATCH --gpus=1

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
hostname
date
nvidia-smi
