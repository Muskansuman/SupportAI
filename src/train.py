"""
Train a LoRA or QLoRA adapter on top of the base model.

The script:
    1. Pulls the dataset from ClearML.
    2. Formats and tokenizes examples.
    3. Loads the base Qwen model in BF16 (LoRA) or 4-bit NF4 (QLoRA).
    4. Applies a LoRA adapter.
    5. Trains using the same hyperparameters for LoRA and QLoRA.
    6. Evaluates using the real task metric.
    7. Saves only the adapter.
    8. Registers the adapter as a ClearML candidate model.

Usage:
    python -m src.train --method lora --dataset-id <clearml_dataset_id>

    python -m src.train --method qlora --dataset-id <clearml_dataset_id>

Resume an interrupted run:

    python -m src.train \
        --method lora \
        --dataset-id <clearml_dataset_id> \
        --resume
"""

import argparse
import json
import shutil
from pathlib import Path

import torch

from clearml import OutputModel
from datasets import load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)
from transformers.trainer_utils import get_last_checkpoint

from src.callbacks import RealTaskEvalCallback
from src.clearml_utils import pull_dataset, start_task
from src.config import MODEL_NAME, MODEL_REGISTRY_NAME, OUTPUTS_DIR
from src.prompting import format_example, make_tokenize_fn


# ============================================================================
# Experiment configuration
# ============================================================================

SEED = 42

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

LEARNING_RATE = 2e-4

NUM_EPOCHS = 5

PER_DEVICE_TRAIN_BATCH_SIZE = 6
GRADIENT_ACCUMULATION_STEPS = 2

# Effective batch size on a single GPU:
#
#     6 * 2 = 12
#
# If using multiple GPUs:
#
#     6 * 2 * number_of_GPUs
#
EFFECTIVE_BATCH_SIZE = (
    PER_DEVICE_TRAIN_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS
)

SAVE_STEPS = 50

# The real task evaluation should be substantially cheaper than running
# generation/evaluation over the complete validation set.
REAL_EVAL_SAMPLE_SIZE = 48

EARLY_STOPPING_PATIENCE = 3


# ============================================================================
# LoRA / QLoRA configuration
# ============================================================================

TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]


METHOD_CONFIGS = {
    "lora": {
        "quantization": None,
    },
    "qlora": {
        "quantization": "4bit-nf4",
    },
}


# ============================================================================
# Utility functions
# ============================================================================

def validate_environment():
    """Validate the hardware/software environment before starting training."""

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU is required for LoRA/QLoRA training."
        )

    print("=" * 80)
    print("Training environment")
    print("=" * 80)

    print(f"PyTorch version : {torch.__version__}")
    print(f"CUDA available  : {torch.cuda.is_available()}")
    print(f"CUDA version    : {torch.version.cuda}")

    device_name = torch.cuda.get_device_name(0)
    total_memory_gb = (
        torch.cuda.get_device_properties(0).total_memory / 1e9
    )

    print(f"GPU             : {device_name}")
    print(f"GPU memory      : {total_memory_gb:.2f} GB")

    if not torch.cuda.is_bf16_supported():
        raise RuntimeError(
            "BF16 support is required by this training configuration."
        )

    print("BF16 supported  : yes")
    print("=" * 80)


def load_tokenizer():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Qwen models commonly use EOS as PAD when a dedicated PAD token
    # is not present.
    tokenizer.padding_side = "right"

    return tokenizer


def load_base_model(method):
    """
    Load the base model.

    LoRA:
        BF16 base weights.

    QLoRA:
        4-bit NF4 base weights + BF16 computation.
    """

    quantized = method == "qlora"

    if quantized:
        print("Loading base model using 4-bit NF4 quantization...")

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            quantization_config=bnb_config,
            device_map="auto",
        )

        # Required preparation for QLoRA / k-bit PEFT training.
        model = prepare_model_for_kbit_training(model)

    else:
        print("Loading base model in BF16 for LoRA...")

        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            dtype=torch.bfloat16,
            device_map="auto",
        )

    # Gradient checkpointing is used for BOTH methods so that the
    # comparison does not give one method an artificial memory advantage.
    model.gradient_checkpointing_enable()

    # KV cache is incompatible/unnecessary during training.
    model.config.use_cache = False

    # Important when training a PEFT model with gradient checkpointing.
    model.enable_input_require_grads()

    return model


def load_tokenized_datasets(dataset_path, tokenizer):
    """
    Load train/validation JSONL files and tokenize them.
    """

    data_files = {
        "train": str(Path(dataset_path) / "train.jsonl"),
        "validation": str(Path(dataset_path) / "val.jsonl"),
    }

    raw_datasets = load_dataset(
        "json",
        data_files=data_files,
    )

    print(
        f"Train examples      : {len(raw_datasets['train'])}"
    )
    print(
        f"Validation examples : {len(raw_datasets['validation'])}"
    )

    formatted_datasets = raw_datasets.map(
        format_example,
        desc="Formatting examples",
    )

    tokenize_fn = make_tokenize_fn(tokenizer)

    tokenized_datasets = formatted_datasets.map(
        tokenize_fn,
        remove_columns=formatted_datasets["train"].column_names,
        desc="Tokenizing examples",
    )

    return tokenized_datasets, formatted_datasets


def build_lora_model(model, method):
    """
    Attach the LoRA adapter.
    """

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        target_modules=TARGET_MODULES,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)

    print()
    print("=" * 80)
    print("LoRA parameters")
    print("=" * 80)

    model.print_trainable_parameters()

    print("=" * 80)

    return model


def save_experiment_config(output_dir, config):
    """
    Save the exact experiment configuration next to checkpoints.

    This makes accidental resume from a differently configured run
    much easier to detect.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    config_path = output_dir / "experiment_config.json"

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(
            config,
            f,
            indent=2,
            sort_keys=True,
        )

    print(f"Experiment config saved to: {config_path}")


def get_existing_checkpoint(output_dir):
    """
    Find the latest checkpoint, if one exists.
    """

    if not output_dir.is_dir():
        return None

    return get_last_checkpoint(str(output_dir))


def reset_gpu_memory_stats():
    """
    Reset CUDA peak-memory counters immediately before training.
    """

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()


def get_gpu_memory_stats():
    """
    Return peak allocated and reserved GPU memory.
    """

    if not torch.cuda.is_available():
        return {
            "peak_allocated_gb": None,
            "peak_reserved_gb": None,
        }

    return {
        "peak_allocated_gb": (
            torch.cuda.max_memory_allocated() / 1e9
        ),
        "peak_reserved_gb": (
            torch.cuda.max_memory_reserved() / 1e9
        ),
    }


# ============================================================================
# Training
# ============================================================================

def train(
    method,
    dataset_id,
    fresh_start=True,
):
    if method not in METHOD_CONFIGS:
        raise ValueError(
            f"Unknown method: {method}. "
            f"Available: {list(METHOD_CONFIGS)}"
        )

    validate_environment()

    method_config = METHOD_CONFIGS[method]

    # ------------------------------------------------------------------------
    # Reproducibility
    # ------------------------------------------------------------------------

    torch.manual_seed(SEED)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    # ------------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------------

    output_dir = (
        Path(OUTPUTS_DIR)
        / f"qwen-{method}-run1"
    )

    adapter_dir = output_dir / "adapter"

    # ------------------------------------------------------------------------
    # Fresh/resume handling
    # ------------------------------------------------------------------------

    existing_checkpoint = get_existing_checkpoint(output_dir)

    if fresh_start and output_dir.is_dir():
        print(
            f"Removing existing output directory for fresh {method} run:"
        )
        print(f"    {output_dir}")

        shutil.rmtree(output_dir)

        existing_checkpoint = None

    elif not fresh_start and existing_checkpoint:
        print(
            f"Resume requested. Existing checkpoint detected:"
        )
        print(f"    {existing_checkpoint}")

    elif not fresh_start:
        print(
            "Resume requested, but no checkpoint was found. "
            "Starting a new run."
        )

    # ------------------------------------------------------------------------
    # Load tokenizer / dataset
    # ------------------------------------------------------------------------

    tokenizer = load_tokenizer()

    dataset_path = pull_dataset(dataset_id)

    print(f"Dataset pulled to: {dataset_path}")

    tokenized_datasets, formatted_datasets = (
        load_tokenized_datasets(
            dataset_path,
            tokenizer,
        )
    )

    # ------------------------------------------------------------------------
    # Load model
    # ------------------------------------------------------------------------

    model = load_base_model(method)

    model = build_lora_model(
        model,
        method,
    )

    # ------------------------------------------------------------------------
    # Experiment configuration
    # ------------------------------------------------------------------------

    task_config = {
        "model_name": MODEL_NAME,
        "method": method,

        "seed": SEED,

        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,

        "target_modules": TARGET_MODULES,

        "quantization": method_config["quantization"],

        "epochs": NUM_EPOCHS,

        "learning_rate": LEARNING_RATE,

        "per_device_train_batch_size": (
            PER_DEVICE_TRAIN_BATCH_SIZE
        ),

        "gradient_accumulation_steps": (
            GRADIENT_ACCUMULATION_STEPS
        ),

        "effective_batch_size": (
            EFFECTIVE_BATCH_SIZE
        ),

        "save_steps": SAVE_STEPS,

        "real_eval_sample_size": (
            REAL_EVAL_SAMPLE_SIZE
        ),

        "early_stopping_patience": (
            EARLY_STOPPING_PATIENCE
        ),
    }

    print()
    print("=" * 80)
    print("Experiment configuration")
    print("=" * 80)

    for key, value in task_config.items():
        print(f"{key:35s}: {value}")

    print("=" * 80)

    save_experiment_config(
        output_dir,
        task_config,
    )

    # ------------------------------------------------------------------------
    # ClearML
    # ------------------------------------------------------------------------

    task = start_task(
        f"qwen0.5b-{method}-run1",
        config=task_config,
    )

    # ------------------------------------------------------------------------
    # IMPORTANT:
    #
    # We intentionally DO NOT use Trainer's normal validation loss evaluation
    # every 50 steps.
    #
    # The previous run showed repeated ~1.87 GB allocation failures during
    # evaluation because CausalLM evaluation produces logits over the very
    # large vocabulary.
    #
    # The real task callback is the metric we actually care about.
    # ------------------------------------------------------------------------

    training_args = TrainingArguments(
        output_dir=str(output_dir),

        # ------------------------------------------------------------
        # Training batch
        # ------------------------------------------------------------

        per_device_train_batch_size=(
            PER_DEVICE_TRAIN_BATCH_SIZE
        ),

        gradient_accumulation_steps=(
            GRADIENT_ACCUMULATION_STEPS
        ),

        # ------------------------------------------------------------
        # Optimization
        # ------------------------------------------------------------

        num_train_epochs=NUM_EPOCHS,

        learning_rate=LEARNING_RATE,

        # ------------------------------------------------------------
        # Logging
        # ------------------------------------------------------------

        logging_steps=10,

        # ------------------------------------------------------------
        # Checkpointing
        # ------------------------------------------------------------

        save_strategy="steps",
        save_steps=SAVE_STEPS,
        save_total_limit=2,

        # ------------------------------------------------------------
        # Evaluation
        #
        # Disabled here because normal CausalLM evaluation was causing
        # very large temporary logits allocations on the 8 GB GPU.
        #
        # RealTaskEvalCallback is responsible for task evaluation.
        # ------------------------------------------------------------

        eval_strategy="no",

        # ------------------------------------------------------------
        # Precision
        # ------------------------------------------------------------

        bf16=True,

        # ------------------------------------------------------------
        # Reproducibility
        # ------------------------------------------------------------

        seed=SEED,
        data_seed=SEED,

        # ------------------------------------------------------------
        # Logging backends
        # ------------------------------------------------------------

        report_to="none",

        # ------------------------------------------------------------
        # Keep training behavior explicit
        # ------------------------------------------------------------

        remove_unused_columns=True,
    )

    # ------------------------------------------------------------------------
    # Real task evaluation
    # ------------------------------------------------------------------------

    real_task_callback = RealTaskEvalCallback(
        tokenizer=tokenizer,
        eval_examples=formatted_datasets["validation"],
        task=task,
        sample_size=REAL_EVAL_SAMPLE_SIZE,
    )

    # ------------------------------------------------------------------------
    # Trainer
    #
    # NOTE:
    # EarlyStoppingCallback is intentionally kept here only if
    # RealTaskEvalCallback provides the monitored metric to Trainer.
    #
    # Once callbacks.py is checked, we can make the metric naming and
    # early-stopping behavior completely explicit.
    # ------------------------------------------------------------------------

    trainer = Trainer(
        model=model,
        args=training_args,

        train_dataset=tokenized_datasets["train"],

        # No eval_dataset is supplied because we disabled Trainer's
        # standard evaluation. The real task callback owns evaluation.
        eval_dataset=None,

        callbacks=[
            real_task_callback,
        ],
    )

    # ------------------------------------------------------------------------
    # GPU memory measurement starts HERE.
    #
    # This excludes model-loading allocations from peak training VRAM.
    # ------------------------------------------------------------------------

    reset_gpu_memory_stats()

    # ------------------------------------------------------------------------
    # Train
    # ------------------------------------------------------------------------

    print()
    print("=" * 80)
    print(f"Starting {method.upper()} training")
    print("=" * 80)

    if existing_checkpoint and not fresh_start:
        print(
            f"Resuming from checkpoint: {existing_checkpoint}"
        )

        train_result = trainer.train(
            resume_from_checkpoint=existing_checkpoint
        )

    else:
        print("Starting from scratch.")

        train_result = trainer.train()

    # ------------------------------------------------------------------------
    # Training complete
    # ------------------------------------------------------------------------

    print()
    print("=" * 80)
    print(f"{method.upper()} training complete")
    print("=" * 80)

    # ------------------------------------------------------------------------
    # GPU memory statistics
    # ------------------------------------------------------------------------

    memory_stats = get_gpu_memory_stats()

    print(
        "Peak GPU memory allocated: "
        f"{memory_stats['peak_allocated_gb']:.2f} GB"
    )

    print(
        "Peak GPU memory reserved : "
        f"{memory_stats['peak_reserved_gb']:.2f} GB"
    )

    # Log memory for BOTH LoRA and QLoRA.
    task.get_logger().report_scalar(
        title="resource_usage",
        series="peak_vram_allocated_gb",
        value=memory_stats["peak_allocated_gb"],
        iteration=0,
    )

    task.get_logger().report_scalar(
        title="resource_usage",
        series="peak_vram_reserved_gb",
        value=memory_stats["peak_reserved_gb"],
        iteration=0,
    )

    # ------------------------------------------------------------------------
    # Training statistics
    # ------------------------------------------------------------------------

    if train_result.metrics:
        for key, value in train_result.metrics.items():

            if isinstance(value, (int, float)):
                task.get_logger().report_scalar(
                    title="training_summary",
                    series=key,
                    value=value,
                    iteration=0,
                )

    # ------------------------------------------------------------------------
    # Save adapter
    # ------------------------------------------------------------------------

    print()
    print(f"Saving adapter to: {adapter_dir}")

    adapter_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    model.save_pretrained(
        str(adapter_dir)
    )

    tokenizer.save_pretrained(
        str(adapter_dir)
    )

    print("Adapter saved successfully.")

    # ------------------------------------------------------------------------
    # Register ClearML model
    # ------------------------------------------------------------------------

    output_model = OutputModel(
        task=task,
        name=MODEL_REGISTRY_NAME,
        framework="PyTorch",
    )

    output_model.update_weights(
        str(adapter_dir)
    )

    output_model.tags = [
        "candidate",
        method,
        f"seed-{SEED}",
    ]

    print(
        f"Model registered in ClearML as "
        f"'candidate' ({method})"
    )

    return (
        model,
        tokenizer,
        task,
        output_model,
    )


# ============================================================================
# CLI
# ============================================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Fine-tune Qwen with LoRA or QLoRA"
        )
    )

    parser.add_argument(
        "--method",
        choices=list(METHOD_CONFIGS),
        required=True,
        help="Training method: lora or qlora",
    )

    parser.add_argument(
        "--dataset-id",
        required=True,
        help=(
            "ClearML dataset ID from dataset registration"
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from the latest checkpoint in the output "
            "directory. Only use this when continuing the exact "
            "same experiment configuration."
        ),
    )

    args = parser.parse_args()

    train(
        method=args.method,
        dataset_id=args.dataset_id,
        fresh_start=not args.resume,
    )


if __name__ == "__main__":
    main()