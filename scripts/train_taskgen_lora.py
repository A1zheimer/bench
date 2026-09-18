import argparse
import os

import torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen2.5-Coder-7B-Instruct with LoRA on task generation SFT data")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--data", type=str, default="./sft_data/taskgen_train.jsonl")
    parser.add_argument("--output", type=str, default="./models/taskgen-lora")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--max-seq-length", type=int, default=8192)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quantize", action="store_true")
    parser.add_argument("--merge-and-save", action="store_true")
    return parser.parse_args()


def print_trainable_parameters(model):
    trainable_params = 0
    all_params = 0
    for _, param in model.named_parameters():
        all_params += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()
    print(
        f"Total params: {all_params:,d} || "
        f"Trainable params: {trainable_params:,d} || "
        f"Trainable%: {100 * trainable_params / all_params:.4f}%"
    )


def formatting_prompts_func(examples, tokenizer):
    outputs = []
    for messages in examples["messages"]:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        outputs.append(text)
    return {"text": outputs}


def main():
    args = parse_args()

    print(f"Loading tokenizer from {args.model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"Loading dataset from {args.data}...")
    dataset = load_dataset("json", data_files=args.data, split="train")
    print(f"Dataset size: {len(dataset)} examples")

    dataset = dataset.map(
        lambda examples: formatting_prompts_func(examples, tokenizer),
        batched=True,
        remove_columns=dataset.column_names,
    )

    quantization_config = None
    if args.quantize:
        print("Using 4-bit quantization via bitsandbytes...")
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    print(f"Loading model from {args.model}...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
    )

    model = get_peft_model(model, lora_config)
    print_trainable_parameters(model)

    if args.dry_run:
        print("Dry run complete. Model and data loaded successfully.")
        print(f"Would train for {args.epochs} epochs with lr={args.lr}")
        print(f"Output would be saved to {args.output}")
        return

    training_args = SFTConfig(
        output_dir=args.output,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        bf16=True,
        logging_steps=1,
        save_strategy="epoch",
        gradient_checkpointing=True,
        max_seq_length=args.max_seq_length,
        optim="adamw_torch",
        dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    print("Starting training...")
    trainer.train()

    print(f"Saving LoRA adapter to {args.output}...")
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    if args.merge_and_save:
        print("Merging LoRA weights into base model...")
        merged_dir = os.path.join(args.output, "merged")
        merged_model = model.merge_and_unload()
        merged_model.save_pretrained(merged_dir)
        tokenizer.save_pretrained(merged_dir)
        print(f"Merged model saved to {merged_dir}")

    print("Training complete.")


if __name__ == "__main__":
    main()
