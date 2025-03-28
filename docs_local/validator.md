# ✅ Run a Validator

The validator is responsible for monitoring model performance and submitting weights to guide TAO emissions.

---

## 📦 Requirements

- Subtensor node must be running  
- Wallets must be created and staked  
- Subnet must be created and boosted  
- Validator must be registered in the subnet

> 💡 If you're not ready yet, complete:
> - [Subtensor Setup](./subtensor-setup.md)
> - [Wallet & Subnet Setup](./wallets-and-subnet.md)

---

## 🛠️ Run the Validator

```sh
python validators/validator.py \
  --netuid 1 \
  --wallet.name validator \
  --wallet.hotkey default
```

> This script monitors activity in the subnet and contributes to setting weights. It should run continuously in the background.

---
### Check Validator Status
```sh
btcli wallet overview --wallet.name validator \
  --subtensor.chain_endpoint ws://127.0.0.1:9944
```
This will show your validator's balance, stake, and emissions.