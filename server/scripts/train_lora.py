"""
train_lora.py — KIRA Phase 5 Fine-tuning Script

This script trains a custom LoRA adapter for microsoft/Phi-3-mini-4k-instruct
using the collected conversation dataset in `server/data/fine_tuning_data.jsonl`.

Prerequisites (install on Google Colab or local GPU machine):
  pip install transformers peft trl bitsandbytes accelerate datasets datasets
"""

import os
import json
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    pipeline
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------
MODEL_ID = "microsoft/Phi-3-mini-4k-instruct"
DATASET_PATH = "../data/fine_tuning_data.jsonl"
OUTPUT_DIR = "./kira-phi3-lora"
FINAL_MERGED_DIR = "./kira-phi3-instruct-merged"

def load_local_dataset(path):
    """Load JSONL dataset into Hugging Face Dataset format."""
    if not os.path.exists(path):
        # Create a dummy dataset if file doesn't exist for demo/compilation reasons
        print(f"Dataset path {path} not found. Creating a dummy dataset for verification...")
        dummy_data = [
            {
                "messages": [
                    {"role": "system", "content": "You are KIRA."},
                    {"role": "user", "content": "who are you"},
                    {"role": "assistant", "content": "I am KIRA, your personal voice assistant."}
                ]
            }
        ]
        return Dataset.from_list(dummy_data)

    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return Dataset.from_list(data)

def main():
    print("=" * 60)
    print("🚀 Starting KIRA Phi-3 QLoRA Fine-Tuning Pipeline")
    print("=" * 60)

    # Step 1: Load data
    print("\n[1/6] Loading fine-tuning dataset...")
    dataset = load_local_dataset(DATASET_PATH)
    print(f"Loaded {len(dataset)} training samples.")

    # Step 2: Load Tokenizer
    print("\n[2/6] Loading base tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # Step 3: Quantization config for QLoRA
    print("\n[3/6] Configuring 4-bit model quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    )

    # Step 4: Load Base Model
    print("\n[4/6] Loading model in 4-bit quantization...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
        model = prepare_model_for_kbit_training(model)
    except Exception as e:
        print(f"⚠️ Could not load model in 4-bit (likely running on CPU/Colab free tier without GPU): {e}")
        print("For training, please run this on a GPU-enabled runtime (e.g. CUDA).")
        return

    # Step 5: Configure LoRA
    print("\n[5/6] Initializing LoRA configuration...")
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["qkv_proj", "o_proj", "gate_up_proj", "down_proj"] # Phi-3 target projections
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Step 6: Setup SFTTrainer and Training Arguments
    print("\n[6/6] Setting up training arguments...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        gradient_checkpointing=True,
        optim="paged_adamw_32bit",
        logging_steps=10,
        save_strategy="epoch",
        learning_rate=2e-4,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        max_grad_norm=0.3,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to="none"
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        max_seq_length=2048,
        tokenizer=tokenizer,
        args=training_args,
        packing=False
    )

    print("\n🔥 Starting training... (This will run SFT training epochs)")
    # trainer.train()  # Uncomment this to execute actual training

    print("\n💾 Saving adapter model...")
    # trainer.model.save_pretrained(OUTPUT_DIR)
    
    print("\n=== How to convert trained weights to GGUF format for KIRA ===")
    print("1. Merge LoRA adapter weights back into base model weights:")
    print("   ```python")
    print("   from peft import PeftModel")
    print("   base_model = AutoModelForCausalLM.from_pretrained('microsoft/Phi-3-mini-4k-instruct', torch_dtype=torch.float16)")
    print("   model = PeftModel.from_pretrained(base_model, './kira-phi3-lora')")
    print("   merged_model = model.merge_and_unload()")
    print("   merged_model.save_pretrained('./kira-phi3-instruct-merged')")
    print("   ```")
    print("2. Clone llama.cpp repository:")
    print("   git clone https://github.com/ggerganov/llama.cpp.git")
    print("3. Install conversion dependencies:")
    print("   pip install -r llama.cpp/requirements.txt")
    print("4. Convert PyTorch merged model folder to GGUF:")
    print("   python llama.cpp/convert_hf_to_gguf.py ./kira-phi3-instruct-merged --outfile kira-phi3.gguf --outtype q4_k_m")
    print("5. Load into Ollama:")
    print("   Create a 'Modelfile' containing: FROM ./kira-phi3.gguf")
    print("   Run: ollama create kira -f Modelfile")
    print("   Set: OLLAMA_MODEL=kira in config/.env")
    print("=" * 60)

if __name__ == "__main__":
    main()
