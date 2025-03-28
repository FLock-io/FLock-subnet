# 🧑‍🏫 Validating with FLockDataset
This guide walks through setting up and running a FLockDataset validator. Validators evaluate miner-submitted datasets by training LoRA models and updating weights on the Bittensor chain.

---
### 🎯 Role of a Validator

**Task:** Assess dataset quality and set miner rewards.

**Process:**
- Fetch miner metadata from the chain
- Download datasets from Hugging Face
- Train LoRA on meta-llama/Llama-3.2-1B with each dataset
- Evaluate loss on a standard test set
- Compute win rates and update weights on-chain

**Goal:** Fairly reward miners based on dataset utility.

---
### 🖥️ System Requirements
Validators perform model training, so strong hardware is essential:

| Resource      | Recommended               |
|---------------|----------------------------|
| GPU           | ✅ NVIDIA RTX 4090 (24GB VRAM)  
| RAM           | ✅ 16GB  
| Storage       | ✅ ~50GB SSD  
| CPU           | ✅ 8-core Intel i7 or better  
| CUDA/cuDNN    | ✅ Installed & compatible with PyTorch  

> 💡 Minimum supported GPU: NVIDIA RTX 3060 (12GB), though performance will be significantly limited.

---
### ⚙️Installation

#### 1. Clone the repository

```bash
git clone https://github.com/FLock-io/FLock-subnet.git
cd FLock-subnet
```

#### 2. Install dependencies with poetry
  2.1. Install the Poetry tool (if not already installed): 
  ```bash
  curl -sSL https://install.python-poetry.org | python3 -
  ```

  2.2 Use Poetry to install project dependencies:
  ```bash
  poetry install
  poetry shell
  ```

---
### 🔐 Set up Hugging Face credentials

1. Create a Hugging Face account at huggingface.co
2. Generate an API token at huggingface.co/settings/tokens
3. Create a .env file in the project root:

    ```
    HF_TOKEN=<YOUR_HUGGING_FACE_API_TOKEN>
    ``` 

4. Ensure the token has read access (validators only need to download datasets).
---

### 🚀 Running the Validator

#### Prerequisites

- **Hardware:** NVIDIA 4090 (24GB VRAM) recommended
- **Bittensor Wallet:** Register your hotkey on the subnet
- **Hugging Face Token:** Read access for downloading datasets

#### Steps to Run a Validator

1. Ensure GPU Setup:
- Install CUDA (e.g., 12.1) and cuDNN compatible with PyTorch
- Verify with nvidia-smi and torch.cuda.is_available()

2. Run the Validator Script:
    ```bash
    python3 neurons/validator.py \
      --wallet.name your_coldkey_name \
      --netuid netuid \
      --logging.trace
    ```

    Replace placeholders:
    - `your_coldkey_name`: Your Bittensor wallet name
    - `netuid`: Subnet UID 

#### What Happens:
- Syncs the metagraph to identify active miners
- Selects up to 32 miners per epoch using an EvalQueue
- For each miner:
  - Retrieves metadata (e.g., ModelId) from the chain
  - Downloads the dataset from Hugging Face (e.g., yourusername/my-dataset:abc123...)
  - Downloads a fixed evaluation dataset (eval_data/eval_data.jsonl)
  - Trains a LoRA model on the miner's dataset using meta-llama/Llama-3.2-1B
  - Evaluates loss on eval_data
  - Computes win rates, adjusts weights, and submits them to the chain

#### Training Details:

| Config        | Value                          |
|---------------|--------------------------------|
| Model         | meta-llama/Llama-3.2-1B (4-bit)|
| LoRA Rank     | 4                              |
| Alpha         | 8                              |
| Dropout       | 0.1                            |
| Target Modules| q_proj, v_proj                 |
| Epochs        | 3                              |
| Context Length| 512 tokens                     |
| Batch Size    | 1 (with grad accumulation = 8) |
> With 24GB VRAM, you can usually process ~10k–20k rows per dataset depending on length and timing.

#### Tips:
- Ensure ample storage for datasets and model checkpoints
- Use --logging.trace to debug training or chain issues

### 🎉  You're Now Validating
Your validator is now live and contributing to the quality of the subnet by scoring miner datasets and updating chain weights.

From here:

- ✅ Let the validator run — it trains, scores, and updates weights automatically
- 🔍 Monitor logs (--logging.trace) for insights or debugging
- 🧪 Expect LoRA training and evaluation to run continuously across epochs



_Questions or feedback? Open an issue or pull request on GitHub — we’re always improving the network together._