# FLock OFF

## A Dataset Quality Competition Network for Machine Learning

FLock OFF is a Bittensor subnet designed to incentivize the creation of high-quality datasets for machine learning. Miners generate and upload datasets to Hugging Face, while validators assess their quality by training LoRA (Low-Rank Adaptation) models on a standardized base model (Qwen/Qwen2.5-1.5B-Instruct) and rewarding miners based on performance.

---

## Table of Contents

- [Compute Requirements](#compute-requirements)
- [Installation](#installation)
- [How to Run FLock OFF](#how-to-run-flock-off)
  - [Running a Miner](#running-a-miner)
  - [Running a Validator](#running-a-validator)
- [What is a Dataset Competition Network?](#what-is-a-dataset-competition-network)
  - [Role of a Miner](#role-of-a-miner)
  - [Role of a Validator](#role-of-a-validator)
- [Features of FLock OFF](#features-of-flock-off)
  - [Hugging Face Integration](#hugging-face-integration)
  - [LoRA Training Evaluation](#lora-training-evaluation)

---

## Compute Requirements

### For Validators

Validators perform LoRA training on miners' datasets, requiring significant GPU resources:

- **Recommended GPU:** NVIDIA-RTX 4090 with 24GB VRAM
- **Minimum GPU:** NVIDIA RTX 3060 with 12GB VRAM  
- **Storage:** ~50GB SSD
- **RAM:** 16GB
- **CPU:** 8-core Intel i7 or equivalent

### For Miners

Miners focus on dataset creation and uploading, requiring minimal compute:

- **GPU:** Not required  
- **Storage:** ~10GB  
- **RAM:** 8GB  
- **Hugging Face Account:** Required with an API token for dataset uploads

---

## Installation

### Overview

In order to run FLock OFF, you will need to install the FLock OFF package and set up a Hugging Face account. The following instructions apply to all major operating systems.

### Clone the repository

```bash
git clone https://github.com/FLock-io/FLock-subnet.git
cd FLock-subnet
```

### Install dependencies with uv

1. Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Set up python environment and install dependencies: 

```bash
# Install dependencies
uv sync

# Install the package in development mode
uv pip install -e .
```

### Set up Hugging Face credentials

1. Create a Hugging Face account at huggingface.co
2. Generate an API token at huggingface.co/settings/tokens
3. Create a .env file in the project root:

```bash
HF_TOKEN=<YOUR_HUGGING_FACE_API_TOKEN>
```

4. Ensure the token has write access for miners (to upload datasets) and read access for validators

---

## How to Run FLock OFF

### Running a Miner

#### Prerequisites

Before mining, prepare the following:

1. **Hugging Face Account and Repository:**
   - Create a dataset repository on Hugging Face (e.g., yourusername/my-dataset)
   - Ensure your API token has write permissions

2. **Dataset Creation:**
   - Generate a dataset in JSONL format (one JSON object per line)
   - Each entry must follow this structure:

```json
{
  "system": "Optional system prompt (can be null)",
  "conversations": [
    {"role": "user", "content": "User input text"},
    {"role": "assistant", "content": "Assistant response text"}
  ]
}
```

**Example:**

```jsonl
{"system": "You are a helpful assistant.", "conversations": [{"role": "user", "content": "What is AI?"}, {"role": "assistant", "content": "AI is artificial intelligence."}]}
{"system": null, "conversations": [{"role": "user", "content": "Tell me a joke."}, {"role": "assistant", "content": "Why don't skeletons fight? They don't have guts."}]}
```

3. **Bittensor Wallet:** Register your hotkey on the subnet

#### Steps to Run a Miner

**Prepare Your Dataset:**
Use a script, scrape data, or manually curate data.jsonl. Aim for high-quality, diverse user-assistant pairs to maximize validator scores.

**Run the Miner Script:**

```bash
python3 neurons/miner.py \
  --wallet.name your_coldkey_name \
  --wallet.hotkey your_hotkey_name \
  --subtensor.network finney \
  --hf_repo_id yourusername/my-dataset \
  --netuid netuid \
  --dataset_path ./data/data.jsonl \
  --logging.trace
```

Replace placeholders:

- `your_coldkey_name`: Your Bittensor wallet name
- `your_hotkey_name`: Your miner's hotkey
- `finney`: Network (use local for testing)
- `yourusername/my-dataset`: Your Hugging Face repo
- `netuid`: Subnet UID (adjust if different)
- `./data/data.jsonl`: Path to your dataset

**What Happens:**

- The script uploads data.jsonl to your Hugging Face repo
- It retrieves a commit hash (e.g., abc123...) and constructs a ModelId (e.g., yourusername/my-dataset:ORIGINAL_COMPETITION_ID:abc123...)
- It registers this metadata on the Bittensor chain (retrying every 120 seconds if the 20-minute commit cooldown applies)

**Tips:**

- Ensure your dataset is unique—validators penalize duplicates
- Monitor logs (--logging.trace) for upload or chain errors

### Running a Validator

#### Prerequisites

- **Hardware:** NVIDIA 4090 (24GB VRAM) recommended
- **Bittensor Wallet:** Register your hotkey on the subnet
- **Hugging Face Token:** Read access for downloading datasets

#### Steps to Run a Validator

**Ensure GPU Setup:**

- Install CUDA (e.g., 12.1) and cuDNN compatible with PyTorch
- Verify with nvidia-smi and torch.cuda.is_available()

**Run the Validator Script:**

```bash
python3 neurons/validator.py \
  --wallet.name your_coldkey_name \
  --netuid netuid \
  --logging.trace
```

Replace placeholders:

- `your_coldkey_name`: Your Bittensor wallet name
- `netuid`: Subnet UID

**What Happens:**

- Syncs the metagraph to identify active miners
- Selects up to 32 miners per epoch using an EvalQueue
- For each miner:
  - Retrieves metadata (e.g., ModelId) from the chain
  - Downloads the dataset from Hugging Face (e.g., yourusername/my-dataset:abc123...)
  - Downloads a fixed evaluation dataset (eval_data/data.jsonl)
  - Trains a LoRA model on the miner's dataset using Qwen/Qwen2.5-1.5B-Instruct
  - Evaluates loss on eval_data
  - Computes win rates, adjusts weights, and submits them to the chain

**Training Details:**

- **Model:** Qwen/Qwen2.5-1.5B-Instruct
- **LoRA Config:** Rank=16, Alpha=32, Dropout=0.1, targeting all linear layers
- **Training Args:** Batch size=2, gradient accumulation=4, 2 epochs, 4096-token context
- **Data Capacity:** With 24GB VRAM, ~10,000-20,000 rows (assuming ~256 tokens/row) per dataset, though limited by epoch duration and miner sample size (32)

**Tips:**

- Ensure ample storage for datasets and model checkpoints
- Use --logging.trace to debug training or chain issues

---

## What is a Dataset Competition Network?

FLock OFF is a decentralized subnet where miners compete to create high-quality datasets, and validators evaluate them using LoRA training. Rewards (in TAO) are distributed based on dataset performance, not raw compute power.

### Role of a Miner

**Task:** Create and upload datasets that improve model performance (e.g., low evaluation loss).

**Process:**

- Curate a dataset (e.g., conversational pairs in JSONL)
- Upload to Hugging Face with version control
- Register metadata on-chain (~0.01 TAO fee)

**Goal:** Outperform other miners in validator evaluations.

### Role of a Validator

**Task:** Assess dataset quality and set miner rewards.

**Process:**

- Fetch miner metadata from the chain
- Download datasets from Hugging Face
- Train LoRA on Qwen/Qwen2.5-1.5B-Instruct with each dataset
- Evaluate loss on a standard test set
- Compute win rates and update weights on-chain

**Goal:** Fairly reward miners based on dataset utility.

---

## Features of FLock OFF

### Hugging Face Integration

- **Storage:** Miners use Hugging Face repos for datasets (e.g., username/repo:commit)
- **Versioning:** Git-based commits ensure reproducibility
- **Accessibility:** Validators download datasets via the Hugging Face API

### LoRA Training Evaluation

- **Efficiency:** LoRA adapts Qwen/Qwen2.5-1.5B-Instruct with minimal parameters
- **Fairness:** Fixed training config ensures consistent evaluation
- **Capacity:** Validators can process ~10,000-20,000 rows per dataset on a 4090, depending on token length and epoch timing
- **Metrics:** Evaluation loss determines dataset quality, with duplicates penalized
