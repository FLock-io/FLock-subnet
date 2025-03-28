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
10. [Register keys in sdubnet](#10-register-keys-in-the-subnet)
11. [Add stake](#11-add-stake)
12. [Set weights for subnet](#12-set-weights-for-subnet)
13. [Run Miner and Validator Scripts](#13-run-miner-and-validator-scripts)
14. [Verify incentive mechanism](#14-verify-incentive-mechanism)

---

## 1. Install Bittensor

### If Bittensor is **not installed**, run:
```sh
# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/master/scripts/install.sh)"
```

### If Bittensor is **already installed**, update it:
```sh
python3 -m pip install --upgrade bittensor
```

### Verify Installation:
```sh
pip show bittensor
btcli --version
```

Both commands should return valid versions of bittensor and btcli.

## 2. Install Dependencies

## For macOS:
```sh
brew update
brew install make git curl openssl llvm protobuf
```

## For Linux/WSL (Windows Subsystem for Linux):
**Note: On Windows, use [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/install) to run these commands.**
```sh
sudo apt update
sudo apt install --assume-yes make build-essential git clang curl libssl-dev llvm libudev-dev protobuf-compiler
```

## 3. Install Rust and Cargo:
```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

## 4. Clone Subtensor Repo and Initialize
```sh
git clone https://github.com/opentensor/subtensor.git
./subtensor/scripts/init.sh
```

## 5. Set up the Wallets
1. Owner
```sh
btcli wallet new_coldkey --wallet.name owner
```
2. Miner
**Note: you would want to create multiple Miner Wallets to mimic the validation process accurately and realistically.**
```sh
btcli wallet new_coldkey --wallet.name miner
btcli wallet new_hotkey --wallet.name miner --wallet.hotkey default
```
3. Validator
```sh
btcli wallet new_coldkey --wallet.name validator
btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default
```

## 6. Build the Subtensor Node
**Note: This step takes a while to complete.**
```sh
cargo build -p node-subtensor --profile release --features pow-faucet
```

**At this point, ***delete*** the target folder, and run the below command:**

_The localnet script spins up a local blockchain with pre-configured nodes. This is ideal for local testing and development, not for connecting to testnet or mainnet._
```sh
BUILD_BINARY=1 ./scripts/localnet.sh False
```
This would start the Blockchain. However, if there are 0 peers, we would have to set up Alice and Bob [manually](#7-manual-setup-of-blockchain-nodes).

## 7. Manual Setup of Blockchain Nodes

**Note: This step is an alternative setup procedure in case the bash script did not work.**

### Step 1: Set up First Node (Alice)
Run the following command:
```sh
./subtensor/target/release/node-subtensor \
    --base-path /tmp/alice \
    --chain=./subtensor/scripts/specs/local.json \
    --alice --port 30334 --rpc-port 9944 --validator \
    --rpc-cors=all --allow-private-ipv4 --discover-local \
    --unsafe-force-node-key-generation
```
Explanation of Flags:
- alice → Identifies this node as Alice.
- port 30334 → Communication port.
- rpc-port 9944 → RPC access for API calls.
- validator → Runs Alice as a validator.

### Step 2: Get Alice's Boot Node Address
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

### Step 3: Start the Second Node (Bob)
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

### Step 4: Verify Nodes are Running

The logs for Alice and Bob in their respective terminals should indicate that they have 1 peer (i.e. each other). As long as the nodes are running in the background, you can do the remaining steps in any other directories, preferably the directory of FLock-subnet. So, the set up is split into 2 main parts: the setting up of the local blockchain, and the set up of the testing environment for FLock-subnet.

## 8. Top Up Wallets with TAO from Faucet
Run Faucet Command in a **separate terminal**:
```sh
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli wallet faucet --wallet.name miner --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9944
```
Note: The port 9944 should match the RPC port of your Alice node.

## 9. Create a subnet
```sh
btcli subnet create --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9944
```

## 10. Register Keys in the subnet
```sh
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli subnet register --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```
You wouldn't actually need to register the owner wallet since it is automatically registered when you created the subnet. But if there are any issues, registering it again might help.

## 11. Add Stake
```sh
btcli stake add --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```

## 12. Set weights for subnet
Register a validator on the root subnet and boost to set weights for your subnet. This is a necessary step to ensure that the subnet is able to receive emmissions.
```sh
btcli root register --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
btcli root boost --netuid 1 --increase 1 --wallet.name validator --wallet.hotkey default --subtensor.chain_endpoint ws://127.0.0.1:9944
```

## 13. Run Miner and Validator scripts
After setting up the blockchain, you can now clone and test a subnet. You can do this in a separate directory. **Make sure to use to correct netuid.** The netuid must match that of your subnet. The details of the running FLock-subnet can be found [here](README.md).

## 14. Verify incentive mechanism
After a few blocks the subnet validator will set weights. This indicates that the incentive mechanism is active. Then after a subnet tempo elapses (360 blocks or 72 minutes) you will see your incentive mechanism beginning to distribute TAO to the subnet miner.
```sh
btcli wallet overview --wallet.name miner --subtensor.chain_endpoint ws://127.0.0.1:9944
```
