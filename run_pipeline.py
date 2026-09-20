"""End-to-end pipeline: build data -> version it in ClearML -> train LoRA
and QLoRA adapters -> evaluate both against the base model -> promote
whichever candidate passes the quality gate.

This mirrors the flow of notebooks/LLM_tuning.ipynb, but as scripted stages
you can also run independently via the src/ modules (src/data_pipeline.py,
src/train.py, src/evaluate.py, src/promote.py).

Requires CLEARML_API_ACCESS_KEY / CLEARML_API_SECRET_KEY in the environment
(see .env.example).
"""
import argparse
import gc

import torch
from clearml import Model

from src import data_pipeline, evaluate, judge, promote, train
from src.clearml_utils import pull_dataset, register_dataset
from src.config import DATA_PROCESSED_DIR, configure_clearml_env
from src.pipeline_state import clear_state, load_state, save_state


def free_gpu_memory():
    """Reclaim VRAM from models the caller has just deleted.

    Stages run sequentially in one process on a single ~8GB GPU, so a
    model left alive after its stage finishes crowds out the next one.
    Call `del <model var>` in the caller before this — deleting a local
    inside this helper wouldn't drop the caller's own reference.
    """
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def run_judge_diagnosis(task, prefix, predictions):
    """Diagnose why this candidate's exact-match failures happened, using a
    bigger Qwen2.5 model as judge. Logs a breakdown to ClearML for visibility
    only — does not feed into promote.passes_quality_gate().
    """
    n_failures = sum(1 for p in predictions if p["predicted_parsed"] != p["expected"])
    if n_failures == 0:
        print(f"[{prefix}] no exact-match failures — skipping judge diagnosis")
        return

    judge_model, judge_tokenizer = judge.load_judge_model()
    _, counts = judge.diagnose_failures(predictions, judge_model, judge_tokenizer)
    judge.log_diagnosis_summary(task, prefix, counts, n_failures)

    del judge_model
    free_gpu_memory()


def parse_args():
    parser = argparse.ArgumentParser(description="Run the full LoRA/QLoRA training pipeline")
    parser.add_argument(
        "--fresh", action="store_true",
        help="Ignore any saved outputs/pipeline_state.json and rerun every stage from scratch",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    configure_clearml_env()

    if args.fresh:
        clear_state()
    state = load_state()

    # 1. Build the dataset and version it in ClearML — skipped on resume,
    # it's a fixed external dataset so re-fetching it would just reproduce
    # the same data anyway (see data_pipeline.fetch_raw_tickets).
    if "dataset_id" in state:
        dataset_id = state["dataset_id"]
        print(f"Resuming with previously registered dataset: {dataset_id}")
    else:
        data_pipeline.build_dataset()
        dataset_id = register_dataset(DATA_PROCESSED_DIR, dataset_name="ticket-extraction-v1")
        state["dataset_id"] = dataset_id
        save_state(state)

    test_data = evaluate.load_test_data(pull_dataset(dataset_id))

    # 2. Train LoRA, then evaluate it against a fresh base model — skipped
    # on resume if it already finished (train+eval) last run.
    if "lora" in state:
        print("Resuming: LoRA already trained and evaluated, reusing its results.")
        lora_output_model = Model(model_id=state["lora"]["output_model_id"])
        base_metrics = state["lora"]["base_metrics"]
        lora_metrics = state["lora"]["lora_metrics"]
    else:
        lora_model, lora_tokenizer, lora_task, lora_output_model = train.train("lora", dataset_id)

        base_model = evaluate.load_base_model_for_eval()
        base_predictions = evaluate.run_predictions(base_model, lora_tokenizer, test_data)
        lora_predictions = evaluate.run_predictions(lora_model, lora_tokenizer, test_data)
        base_metrics = evaluate.compute_metrics(base_predictions)
        lora_metrics = evaluate.compute_metrics(lora_predictions)
        evaluate.log_metrics(lora_task, base_metrics, "base")
        evaluate.log_metrics(lora_task, lora_metrics, "lora")

        # Free the LoRA and base eval models before loading the judge (and,
        # after that, QLoRA's model) — the GPU is too small to hold more
        # than one model at a time (see free_gpu_memory).
        del lora_model, base_model
        free_gpu_memory()

        run_judge_diagnosis(lora_task, "lora", lora_predictions)
        lora_task.close()

        state["lora"] = {
            "task_id": lora_task.id,
            "output_model_id": lora_output_model.id,
            "base_metrics": base_metrics,
            "lora_metrics": lora_metrics,
        }
        save_state(state)

    # 3. Train QLoRA, evaluate it too — skipped on resume the same way.
    # If a previous run died mid-training, train.train() itself picks back
    # up from the last saved checkpoint instead of starting at step 0.
    if "qlora" in state:
        print("Resuming: QLoRA already trained and evaluated, reusing its results.")
        qlora_output_model = Model(model_id=state["qlora"]["output_model_id"])
        qlora_metrics = state["qlora"]["qlora_metrics"]
    else:
        qlora_model, qlora_tokenizer, qlora_task, qlora_output_model = train.train("qlora", dataset_id)
        qlora_predictions = evaluate.run_predictions(qlora_model, qlora_tokenizer, test_data)
        qlora_metrics = evaluate.compute_metrics(qlora_predictions)
        evaluate.log_metrics(qlora_task, qlora_metrics, "qlora")

        del qlora_model
        free_gpu_memory()

        run_judge_diagnosis(qlora_task, "qlora", qlora_predictions)
        qlora_task.close()

        state["qlora"] = {
            "task_id": qlora_task.id,
            "output_model_id": qlora_output_model.id,
            "qlora_metrics": qlora_metrics,
        }
        save_state(state)

    evaluate.compare(base_metrics, lora_metrics, qlora_metrics)

    # 4. Promote whichever candidate passes the quality gate
    lora_passed, lora_reasons = promote.passes_quality_gate(lora_metrics, base_metrics)
    qlora_passed, qlora_reasons = promote.passes_quality_gate(qlora_metrics, base_metrics)
    print("LoRA passes gate:", lora_passed, "| Reasons:", lora_reasons if not lora_passed else "N/A")
    print("QLoRA passes gate:", qlora_passed, "| Reasons:", qlora_reasons if not qlora_passed else "N/A")

    candidates = []
    if lora_passed:
        candidates.append(("lora", lora_metrics, lora_output_model))
    if qlora_passed:
        candidates.append(("qlora", qlora_metrics, qlora_output_model))

    winner = promote.pick_winner(candidates)
    promote.promote(winner)
    promote.reject_losers(
        {"lora": lora_output_model, "qlora": qlora_output_model},
        winner_name=winner[0] if winner else None,
    )

    # Pipeline finished end-to-end — clear the checkpoint so the next
    # invocation starts a fresh run instead of reusing this one forever.
    clear_state()


if __name__ == "__main__":
    main()
