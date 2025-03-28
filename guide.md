# Bittensor Local Subnet Setup Guide

This guide walks through setting up a local Bittensor subnet, including installing dependencies, initializing the blockchain, setting up wallets, and running nodes. **Note that you will require a large amount of memory for this setup.**

---
## Table of Contents
1. [Install Bittensor](#1-install-bittensor)
2. [Install Dependencies](#2-install-dependencies)
3. [Install Rust and Cargo](#3-install-rust-and-cargo)
4. [Clone Subtensor Repo and Initialize](#4-clone-subtensor-repo-and-initialize)
5. [Set up the wallets](#5-set-up-the-wallets)
6. [Build the subtensor node](#6-build-the-subtensor-node)
7. [Manual setup of Blockchain nodes](#7-manual-setup-of-blockchain-nodes)
8. [Top up wallets](#8-top-up-wallets-with-tao-from-faucet)
9. [Create a subnet](#9-create-a-subnet)
10. [Register keys in subnet](#10-register-keys-in-the-subnet)
11. [Add stake](#11-add-stake)
12. [Set weights for subnet](#12-set-weights-for-subnet)
13. [Run Miner and Validator Scripts](#13-run-miner-and-validator-scripts)
14. [Verify incentive mechanism](#14-verify-incentive-mechanism)

---
### 1. Install Bittensor
- 🆕 Fresh install:
    ```sh
    # Create and activate a virtual environment (recommended)
    python3 -m venv venv
    source venv/bin/activate  # macOS/Linux
    venv\Scripts\activate     # Windows

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/master/scripts/install.sh)"
    ```

 - 🔄 Update existing install:
    ```sh
    python3 -m pip install --upgrade bittensor
    ```

 - ✅ Verify installation:
    ```sh
    pip show bittensor
    btcli --version
    ```
    > Both commands should return valid versions of bittensor and btcli.
---
### 2. Install Dependencies

- For macOS:
    ```sh
    brew update
    brew install make git curl openssl llvm protobuf
    ```

- For Linux/WSL (Windows Subsystem for Linux):
    > **Note: On Windows, use [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/install) to run these commands.**
    ```sh
    sudo apt update
    sudo apt install --assume-yes make build-essential git clang curl libssl-dev llvm libudev-dev protobuf-compiler
    ```
---
### 3. Install Rust and Cargo
```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```
---
### 4. Clone Subtensor Repo and Initialize
```sh
git clone https://github.com/opentensor/subtensor.git
./subtensor/scripts/init.sh
```
---
### 5. Set up the Wallets
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
### 6. Build the Subtensor Node
> **⚠️ Note: This step takes a while to complete.**
```sh
cargo build -p node-subtensor --profile release --features pow-faucet
```
Once the build is complete:

1. **_Delete_** the target folder
2. Run the below command:
    ```sh
    BUILD_BINARY=1 ./scripts/localnet.sh False
    ```
> The localnet script spins up a local blockchain with pre-configured nodes. This is ideal for local development — not for connecting to testnet or mainnet.

> ⚠️ If you see 0 peers, proceed to set up Alice and Bob [manually](#7-manual-setup-of-blockchain-nodes).
---
### 7. Manual Setup of Blockchain Nodes

> **Alternative path:** Use this method only if the localnet script didn’t work properly.
---
**Step 1: Set up First Node (Alice)**

Run the following command:
```sh
./subtensor/target/release/node-subtensor \
    --base-path /tmp/alice \
    --chain=./subtensor/scripts/specs/local.json \
    --alice --port 30334 --rpc-port 9944 --validator \
    --rpc-cors=all --allow-private-ipv4 --discover-local \
    --unsafe-force-node-key-generation
```

> 💡 Explanation of Flags:
> - alice → Identifies this node as Alice.
> - port 30334 → Communication port.
> - rpc-port 9944 → RPC access for API calls.
> - validator → Runs Alice as a validator.
---
**Step 2: Get Alice's Boot Node Address**

Find Alice’s bootnode address by running:

```sh
curl -H "Content-Type: application/json" -d \
'{"jsonrpc":"2.0","id":1,"method":"system_localPeerId","params":[]}' \
http://127.0.0.1:9944
```
Look for an address like:
```sh
/ip4/127.0.0.1/tcp/30334/p2p/12D3KooWHTt3ZwHTARPS35SSHW7M3bcAhWfkYysn93EQmZFHnXsQ
```
---
**Step 3: Start the Second Node (Bob)**

Replace `<alice_bootnode>` with Alice's boot node address from Step 2 and run the below in a **separate terminal**:
```sh
./subtensor/target/release/node-subtensor \
    --base-path /tmp/bob \
    --chain=./subtensor/scripts/specs/local.json \
    --bob --port 30335 --rpc-port 9945 --validator \
    --rpc-cors=all --allow-private-ipv4 --discover-local \
    --unsafe-force-node-key-generation \
    --bootnodes /ip4/127.0.0.1/tcp/30334/p2p/<alice_bootnode>
```
---
**Step 4: Verify Nodes are Running**

Check the logs in both terminals — they should each show 1 peer connected.

As long as both nodes are running in the background, you're ready to continue.
The rest of the guide will take place in a separate directory (i.e. the FLock-subnet repo).
---
### 8. Top Up Wallets with TAO from Faucet
Run Faucet Command in a **separate terminal**:
```sh
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli wallet faucet --wallet.name miner --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9944
```
> Note: The port 9944 should match the RPC port of your Alice node.
---
### 9. Create a Subnet
```sh
btcli subnet create --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9944
```
---
### 10. Register Keys in the Subnet
```sh
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli subnet register --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
> Note: The owner wallet is automatically registered when creating the subnet.
You can register it again manually if needed.
---
### 11. Add Stake
```sh
btcli stake add --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
---
### 12. Set Weights for Subnet
Register a validator on the root subnet and boost to set weights for your subnet. 
```sh
btcli root register --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli root boost --netuid 1 --increase 1 --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
> 💡 This step is required for your subnet to start receiving emissions.
---
### 13. Run Miner and Validator scripts
After setting up the blockchain, you can now clone and test a subnet.
> 📂 Run these in a separate directory.\
> 🔢 Make sure the --netuid matches your subnet ID.

The details of the running FLock-subnet can be found [here](README.md).
---
### 14. Verify Incentive Mechanism
After a few blocks, the subnet validator should begin setting weights.
Then, once a full subnet tempo passes (360 blocks = ~72 minutes), TAO emissions will start flowing to the miner.

Check miner balance:
```sh
btcli wallet overview --wallet.name miner --subtensor.chain_endpoint ws://127.0.0.1:9944
```
