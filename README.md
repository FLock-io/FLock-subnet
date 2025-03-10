# **Bittensor Subnet - AI Model Evaluation & Ranking**  

## **Overview**  
This repository implements a **Bittensor subnet** where:  
1. **Miners submit AI models** for evaluation.  
2. **Validators rank miner models** based on quality.  
3. **Dynamic TAO (dTAO) mechanics** determine rewards.  

Validators use a **trained AI model** to score miner responses, ensuring fair, unbiased rankings that influence TAO emissions.  

---

## **Key Components**  

### **Miners**  
- Train AI models and submit responses to requests.  
- Evaluated based on quality, accuracy, and relevance.  

### **Validators**  
- Rank miner submissions using a pre-trained evaluation model.  
- Update weights dynamically to determine miner rewards.  
- Train their own model using structured datasets.  

### **Stakers & Delegators**  
- Can stake on validators to earn a share of emissions.  
- dTAO system influences emissions based on staking & liquidity.  

---

## **Repo Structure**  

📂 **`miner/`** → Handles **model submission & metadata storage**  
📂 **`validator/`** → Manages **ranking, training, & scoring of miners**  

---

## **How It Works**  

1. **Miners submit models** and generate responses.  
2. **Validators retrieve responses**, process them using a **trained AI model**.  
3. **Validator ranks miners**, submits scores to the blockchain.  
4. **Yuma Consensus determines emissions** based on validator trust & dTAO mechanics.  
5. **Rewards are distributed** based on miner performance and validator rankings.  

---

## **Setup & Installation**  

```bash
pip install -r requirements.txt  
btcli wallet create  # Create a wallet  
btcli subnet create  # Register a subnet    
```

---

## **Next Steps**  
**Integrate dTAO mechanics into ranking & emissions.**  
**Optimize validator training for better accuracy.**  
**Enhance miner evaluation beyond simple benchmarks.**  

