# ⛏️ Mining with FLockDataset

This guide explains how to run a FLock miner, from installation and dataset preparation to submitting metadata on-chain.

---
### 🎯 Role of a Miner

**Task:** Create and upload datasets that improve model performance (e.g., low evaluation loss).

**Process:**
- Curate a dataset (e.g., conversational pairs in JSONL)
- Upload to Hugging Face with version control
- Register metadata on-chain (~0.01 TAO fee)

**Goal:** Outperform other miners in validator evaluations.

---
### 🖥️ System Requirements
Miners require minimal compute as their focus is on dataset creation and uploading.

| Resource      | Requirement        |
|---------------|--------------------|
| GPU           | ❌ Not required     |
| RAM           | ✅ 8GB             |
| Storage       | ✅ ~10GB           |
| Hugging Face  | ✅ Account + API token |

---
### ⚙️ Installation

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

4. Ensure the token has write access so you as a miner can upload datasets.
---
### 🗃️ Prepare Dataset
1. Create a Hugging Face Dataset Repo
    
    **Example:** 
    ```text
    yourusername/my-dataset
    ```
    >This is where your dataset will be uploaded, and where validators will later fetch it from.
2. Generate a dataset in JSONL format (one JSON object per line)

    Each entry must follow this structure:

    ```json
    {
        "system": "You are a helpful assistant.",
        "conversations": [
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "AI is artificial intelligence."}
        ]
    }
    ```
    **Example:**

    ```json 
        {
            "system": "You are a helpful assistant.",
            "conversations": [
                {"role": "user", "content": "What is AI?"},
                {"role": "assistant", "content": "AI is artificial intelligence."}
            ]
        }
        {
            "system": null,
            "conversations": [
                {"role": "user", "content": "Tell me a joke."},
                {"role": "assistant", "content": "Why don't skeletons fight? They don't have guts."}
            ]
        }
    ```
    > Use a script, scrape data, or manually curate data.jsonl. Aim for high-quality, diverse user-assistant pairs to maximize validator scores.

3. **Bittensor Wallet:** 
Create a wallet and register your hotkey on the subnet. 
    ```bash
    btcli wallet new_coldkey --wallet.name <wallet_name>
    btcli wallet new_hotkey --wallet.name <wallet_name> --wallet.hotkey <hotkey_name>

    btcli subnet register --netuid <uid> --wallet.name <wallet_name> --wallet.hotkey <hotkey_name>
    ```
    Replace placeholders:
    - `wallet_name`: Your Bittensor wallet name
    - `hotkey_name`: Your miner's hotkey
    - `uid`: The subnet uid you want to register on

---
### 🚀 Running the Miner:

#### Prerequisites

- **Hugging Face Account and Repository with write permissions**
- **Dataset Creation**
- **Bittensor Wallet with hotkey registered on subnet**

#### Run the Miner Script

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
- `finney`: Network
- `yourusername/my-dataset`: Your Hugging Face repo
- `netuid`: Subnet UID (adjust if different)
- `./data/data.jsonl`: Path to your dataset

#### What Happens:
- The script uploads data.jsonl to your Hugging Face repo
- It retrieves a commit hash (e.g., abc123...) and constructs a ModelId (e.g., yourusername/my-dataset:ORIGINAL_COMPETITION_ID:abc123...)
- It registers this metadata on the Bittensor chain (retrying every 120 seconds if the 20-minute commit cooldown applies)

#### Tips:
- Ensure your dataset is unique—validators penalize duplicates
- Monitor logs (--logging.trace) for upload or chain errors

---
### 🎉 You're Now Mining

Your dataset is live. It's uploaded, committed, and ready to be judged by validators.

From here:

- ✅ Keep improving your dataset quality
- 🔁 Re-run the script anytime you push updates
- 🧠 Stay creative — unique, high-signal data stands out


_Questions or feedback? Open an issue or pull request on GitHub — we’re always improving the network together._