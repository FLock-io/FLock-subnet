# 🔐 Wallet and Subnet Setup

This guide walks you through creating the necessary wallets, funding them with test TAO, and setting up your local subnet.

> 💡 This assumes your local Subtensor node is already running.  
> If not, go back and complete the [Subtensor Setup](./subtensor-setup.md) first.

## Table of Contents
1. [Set up the Wallets](#1-set-up-the-wallets)
2. [Top up the Wallets](#2-top-up-wallets-with-tao-from-faucet)
3. [Create a Subnet](#3-create-a-subnet)
4. [Register Keys in the Subnet](#4-register-keys-in-the-subnet)
5. [Add Stake](#5-add-stake)
6. [Set Weights for Subnet](#6-set-weights-for-subnet)
---

### 1. Set up the Wallets
- **Owner**
    ```sh
    btcli wallet new_coldkey --wallet.name owner
    ```
- **Miner**
    > **Note: You may want to create multiple miner wallets to simulate a more realistic validation setup.**
    ```sh
    btcli wallet new_coldkey --wallet.name miner
    btcli wallet new_hotkey --wallet.name miner --wallet.hotkey default
    ```
- **Validator**
    ```sh
    btcli wallet new_coldkey --wallet.name validator
    btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default
    ```
---
### 2. Top Up Wallets with TAO from Faucet
Run Faucet Command in a **separate terminal**:
```sh
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli wallet faucet --wallet.name miner --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9944
```
> Note: The port 9944 should match the RPC port of your Alice node.
---
### 3. Create a Subnet
```sh
btcli subnet create --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9944
```
---
### 4. Register Keys in the Subnet
```sh
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli subnet register --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
> Note: The owner wallet is automatically registered when creating the subnet.
You can register it again manually if needed.

---
### 5. Add Stake
```sh
btcli stake add --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
---
### 6. Set Weights for Subnet
Register a validator on the root subnet and boost to set weights for your subnet. 
```sh
btcli root register --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli root boost --netuid 1 --increase 1 --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
> 💡 This step is required for your subnet to start receiving emissions.
---

## ✅ What's Next?

Now that your subnet is set up and your wallets are funded, you're ready to run your miner or validator:

- 🧠 [Run a Miner](./miner.md)
- ✅ [Run a Validator](./validator.md)

> Make sure your subnet is still live and you're using the correct `--netuid` for your miner or validator scripts.
