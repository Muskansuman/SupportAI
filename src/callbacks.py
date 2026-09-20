"""Trainer callbacks for metrics that plain eval_loss can't capture."""
from transformers import TrainerCallback

from src.evaluate import compute_metrics, run_predictions


class RealTaskEvalCallback(TrainerCallback):
    """At each eval checkpoint, runs actual model.generate() on a fixed
    validation subsample and folds JSON-validity / exact-match / per-field
    accuracy into the Trainer's own `metrics` dict (mutated in place) so
    metric_for_best_model and EarlyStoppingCallback can act on real generation
    quality instead of teacher-forced eval_loss, which saturates near-zero on
    this task almost immediately and stops being informative.

    Must be listed before EarlyStoppingCallback in Trainer(callbacks=[...]) —
    EarlyStoppingCallback reads metrics[metric_for_best_model] during the same
    on_evaluate pass, before this callback would otherwise have added it.
    """

    def __init__(self, tokenizer, eval_examples, task, sample_size=48):
        self.tokenizer = tokenizer
        sample_size = min(sample_size, len(eval_examples))
        self.eval_examples = eval_examples.select(range(sample_size))
        self.task = task

    def on_evaluate(self, args, state, control, model, metrics, **kwargs):
        was_training = model.training
        prev_use_cache = model.config.use_cache
        model.eval()
        model.config.use_cache = True

        predictions = run_predictions(model, self.tokenizer, self.eval_examples)

        model.config.use_cache = prev_use_cache
        if was_training:
            model.train()

        real_task_metrics = compute_metrics(predictions)
        logger = self.task.get_logger()
        for name, value in real_task_metrics.items():
            metrics[f"eval_{name}"] = value
            logger.report_scalar(
                title="real_task_eval", series=name, value=value, iteration=state.global_step
            )
