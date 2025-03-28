# 🔧 Bittensor Subnet Setup (One-Time)

This guide walks through setting up your local Bittensor subnet environment.
## Table of Contents
1. [Install Bittensor](#1-install-bittensor)
2. [Install Dependencies](#2-install-dependencies)
3. [Install Rust and Cargo](#3-install-rust-and-cargo)
4. [Clone Subtensor Repo and Initialize](#4-clone-subtensor-repo-and-initialize)
5. [Build the subtensor node](#5-build-the-subtensor-node)
6. [Manual setup of Blockchain nodes](#6-manual-setup-of-blockchain-nodes)
---
### 1. Install Bittensor
- 🆕 Fresh installation:
    ```sh
    # Create and activate a virtual environment (recommended)
    python3 -m venv venv
    source venv/bin/activate  # macOS/Linux
    venv\Scripts\activate     # Windows

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/master/scripts/install.sh)"
    ```

 - 🔄 Update existing installation:
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

### 5. Build the Subtensor Node
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
> The localnet script spins up a local blockchain with pre-configured nodes. This is ideal for local development — not for connecting to testnet or mainnet. \
> ⚠️ If you see 0 peers, proceed to set up Alice and Bob [manually](#7-manual-setup-of-blockchain-nodes).
---
### 6. Manual Setup of Blockchain Nodes

> **Alternative path:** Use this method only if the localnet script didn’t work properly.
---
#### Step 1: Set up First Node (Alice)

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
#### Step 2: Get Alice's Boot Node Address

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
#### Step 3: Start the Second Node (Bob)

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
#### Step 4: Verify Nodes are Running

Check the logs in both terminals — they should each show 1 peer connected.

As long as both nodes are running in the background, you're ready to continue.
The rest of the guide will take place in a separate directory (i.e. the FLock-subnet repo).

---
### ✅ What's Next?

You can continue to follow the next steps to create your subnet and configure it for use with a miner or validator:

👉 [Continue to Wallet & Subnet Setup ›](./subnet-setup.md)

This includes:
- Creating `owner`, `miner`, and `validator` wallets
- Funding wallets via faucet
- Registering a subnet
- Adding stake and boosting emissions

Make sure your local Subtensor node is still running in the background before continuing.

