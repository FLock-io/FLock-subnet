# 🧠 Run a Miner

This script uploads your dataset to Hugging Face, creates a unique model ID, and commits that ID to the chain.

---

## 📦 Requirements

- Subtensor chain must be running  
- Wallets must be created and funded  
- Subnet must already exist  
- Hugging Face token must be available in `.env` or exported as an env variable

> 💡 If you haven’t done those steps yet, start with:
> - [Subtensor Setup](./subtensor-setup.md)
> - [Wallet & Subnet Setup](./wallets-and-subnet.md)

---

## 🚀 Run the Miner

```sh
python miners/miner.py \
  --dataset_path path/to/data.json \
  --hf_repo_id your-org/your-repo \
  --netuid 1 \
  --wallet.name miner \
  --wallet.hotkey default
```

This script will:
1. Upload your dataset to Hugging Face
2. Generate a ModelId
3. Attempt to commit that model to the chain
4. Retry every 2 minutes if the commit fails

> Use different dataset-miner wallet pairs to simulate different miners. \
> Make sure the netuid (--netuid) matches the one you created earlier.