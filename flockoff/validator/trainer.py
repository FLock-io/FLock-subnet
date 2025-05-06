import os
import shutil
import torch

os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":16:8"
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True
torch.use_deterministic_algorithms(True)

import yaml
from huggingface_hub import HfApi
from peft import LoraConfig, PeftModel
from dataclasses import dataclass
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer
from trl import SFTTrainer, SFTConfig
from .dataset import SFTDataCollator, SFTDataset
from .constants import model2template
import bittensor as bt

api = HfApi()


@dataclass
class LoraTrainingArguments:
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    num_train_epochs: int
    lora_rank: int
    lora_alpha: int
    lora_dropout: int


def download_dataset(
    namespace: str, revision: str, local_dir: str = "data", cache_dir: str = None
):
    # Create cache directory if it doesn't exist
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["HF_HOME"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = os.path.join(cache_dir, "models")

    # Check if the revision is a specific commit hash
    check_commit_env = os.environ.get("VALIDATOR_CHECK_COMMIT_HASH", "true").lower()
    should_check_commit = check_commit_env not in ("false", "0", "no", "f")

    if should_check_commit:
        try:
            repo_info = api.repo_info(repo_id=namespace, revision=revision, repo_type="dataset")
            if repo_info.sha != revision:
                raise ValueError(
                    f"Revision '{revision}' for dataset '{namespace}' is not a specific commit hash. "
                    f"Resolved SHA: '{repo_info.sha}'. "
                    f"Please use a specific commit hash for the revision. "
                    f"To disable this check, set the environment variable VALIDATOR_CHECK_COMMIT_HASH=false."
                )
            bt.logging.info(f"Revision '{revision}' is a valid commit hash.")
        except Exception as e:
            # Catch HfHubHTTPError if revision doesn't exist or other API errors
            bt.logging.error(f"Error fetching repo info for {namespace}@{revision}: {e}")
            raise ValueError(
                f"Failed to validate revision '{revision}' for dataset '{namespace}'. "
                f"Ensure the revision exists and is accessible. Original error: {e}. "
                f"To disable this check, set the environment variable VALIDATOR_CHECK_COMMIT_HASH=false."
            )

    if not os.path.isabs(local_dir):
        local_dir = os.path.abspath(local_dir)

    os.makedirs(local_dir, exist_ok=True)
    api.snapshot_download(
        repo_id=namespace, local_dir=local_dir, revision=revision, repo_type="dataset"
    )

def clean_cache_folder(
    data_dir: str = None,
    eval_data_dir: str = None,
    cache_dir: str = None,
):
    """
    Remove any leftover data / eval_data / cache data
    """
    for d in (data_dir, eval_data_dir, cache_dir):  # ← changed
        if d and os.path.exists(d):
            try:
                shutil.rmtree(d)
            except Exception as e:
                bt.logging.warning(f"Could not clean {d}: {e}")


def train_lora(
    lucky_num: int,
    benchmark_loss: float,
    eval_size: int,
    cache_dir: str = None,
    data_dir: str = "data",
    eval_data_dir: str = "eval_data",
) -> float:
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["HF_HOME"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = os.path.join(cache_dir, "models")

    # set the same random seed to detect duplicate data sets
    from dotenv import load_dotenv

    load_dotenv()
    os.environ["PYTHONHASHSEED"] = str(lucky_num)

    torch.manual_seed(lucky_num)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(lucky_num)
        torch.cuda.manual_seed_all(lucky_num)

    CONTEXT_LENGTH = 2048
    with open(f"flockoff/validator/training_args.yaml", "r") as f:
        all_training_args = yaml.safe_load(f)
    model_key = next(iter(all_training_args))
    args = LoraTrainingArguments(**all_training_args[model_key])

    lora_config = LoraConfig(
        r=args.lora_rank,
        target_modules="all-linear",
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        task_type="CAUSAL_LM",
    )

    # Load model in 4-bit to do qLoRA
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    sft_conf = SFTConfig(
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        warmup_steps=5,
        learning_rate=2e-4,
        bf16=True,
        save_strategy="no",
        output_dir=".",
        logging_dir=None,
        optim="paged_adamw_8bit",
        remove_unused_columns=False,
        per_device_eval_batch_size=1,
        num_train_epochs=args.num_train_epochs,
        max_seq_length=CONTEXT_LENGTH,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_key,
        use_fast=True,
        cache_dir=os.path.join(cache_dir, "models") if cache_dir else None,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_key,
        quantization_config=bnb_config,
        device_map={"": 0},
        token=os.environ["HF_TOKEN"],
        cache_dir=os.path.join(cache_dir, "models") if cache_dir else None,
    )

    # Load dataset
    train_ds = SFTDataset(
        file=os.path.join(data_dir, "data.jsonl"),
        tokenizer=tokenizer,
        max_seq_length=CONTEXT_LENGTH,
        template=model2template[model_key],
    )

    if len(train_ds) > eval_size:
        bt.logging.info(
            f"Dataset has {len(train_ds)} examples, expected {eval_size}, pruning..."
        )
        train_ds.data_list = train_ds.data_list[:eval_size]

    eval_path = os.path.join(eval_data_dir, "data.jsonl")
    if not os.path.exists(eval_path):
        # Look for any jsonl file in the eval directory
        jsonl_files = []
        for root, _, files in os.walk(eval_path):
            for file in files:
                if file.endswith(".jsonl"):
                    jsonl_files.append(os.path.join(root, file))

        if jsonl_files:
            eval_path = jsonl_files[0]
            bt.logging.info(f"Using evaluation file: {eval_path}")
        else:
            bt.logging.error(f"No evaluation file found in {eval_path}")
            return benchmark_loss

    eval_ds = SFTDataset(
        file=eval_path,
        tokenizer=tokenizer,
        max_seq_length=CONTEXT_LENGTH,
        template=model2template[model_key],
    )

    # Define trainer
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=sft_conf,
        peft_config=lora_config,
        data_collator=SFTDataCollator(tokenizer, max_seq_length=CONTEXT_LENGTH),
    )

    # Train model
    trainer.train()
    # save model
    trainer.save_model('output')

    # Create a separate model for evaluation without quantization
    eval_model = AutoModelForCausalLM.from_pretrained(
        model_key,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
        token=os.environ["HF_TOKEN"],
        cache_dir=os.path.join(cache_dir, "models") if cache_dir else None,
    )
    bt.logging.info(f"Loaded eval model")

    eval_model = PeftModel.from_pretrained(
        eval_model,
        "output",
        device_map={"": 0},
    )
    bt.logging.info(f"Loaded eval PeftModel")
    
    # Load the trained LoRA weights into the evaluation model
    eval_model = eval_model.merge_and_unload()
    bt.logging.info(f"Merged eval model")
    
    # Create a separate trainer for evaluation with the non-quantized model

    eval_trainer = Trainer(
        model=eval_model,
        eval_dataset=eval_ds,
        args=sft_conf,
        data_collator=SFTDataCollator(tokenizer, max_seq_length=CONTEXT_LENGTH),
    )
        
    # Eval model
    eval_result = eval_trainer.evaluate()

    return eval_result["eval_loss"]
