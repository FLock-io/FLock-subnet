# FLockDataset

## A Dataset Quality Competition Network for Machine Learning

FLockDataset is a Bittensor subnet designed to incentivize the creation of high-quality datasets for machine learning. Miners generate and upload datasets to Hugging Face, while validators assess their quality by training LoRA (Low-Rank Adaptation) models on a standardized base model (meta-llama/Llama-3.2-1B) and rewarding miners based on performance.

---

## Table of Contents

- [System Requirements](#️-system-requirements)
- [Getting Started](#-getting-started)
- [What is a Dataset Competition Network?](#what-is-a-dataset-competition-network)
- [Roles](#-roles)
- [Features of FLockDataset](#features-of-flockdataset)
  - [Hugging Face Integration](#hugging-face-integration)
  - [LoRA Training Evaluation](#lora-training-evaluation)

---

## 🖥️ System Requirements
- **Miners**: No GPU required. Basic CPU and internet access are enough.
- **Validators**: Strong GPU required (NVIDIA 4090 recommended).
  
  👉 See detailed specs for [miners](./docs/miner.md#️-system-requirements) and [validators](./docs/validator.md#️-system-requirements)

---

## 🚀 Getting Started

- **[Run a Miner ›](./miner.md)**
- **[Run a Validator ›](./validator.md)**
---

## What is a Dataset Competition Network?

FLockDataset is a decentralized subnet where miners compete to create high-quality datasets, and validators evaluate them using LoRA training. Rewards (in TAO) are distributed based on dataset performance, not raw compute power.

## 👤 Roles

- **Miners**: Create & upload datasets to Hugging Face, register metadata on-chain.
- **Validators**: Train LoRA models on miner data, evaluate performance, set weights.

👉 See full guides:
- [How Mining Works ›](./docs/miner.md#-role-of-a-miner)
- [How Validation Works ›](./docs/validator.md#-role-of-a-validator)

---

## Features of FLockDataset

### Hugging Face Integration

- **Storage:** Miners use Hugging Face repos for datasets (e.g., username/repo:commit)
- **Versioning:** Git-based commits ensure reproducibility
- **Accessibility:** Validators download datasets via the Hugging Face API

### LoRA Training Evaluation

- **Efficiency:** LoRA adapts meta-llama/Llama-3.2-1B with minimal parameters (rank=4)
- **Fairness:** Fixed training config ensures consistent evaluation
- **Capacity:** Validators can process ~10,000-20,000 rows per dataset on a 4090, depending on token length and epoch timing
- **Metrics:** Evaluation loss determines dataset quality, with duplicates penalized

