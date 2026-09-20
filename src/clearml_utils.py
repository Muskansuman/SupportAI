"""ClearML dataset/task/model-registry helpers.

Wraps the ClearML calls from the original notebook (dataset versioning,
task bookkeeping, and the candidate/production model promotion flow) so
train.py, evaluate.py, and promote.py don't repeat this boilerplate.
"""
from clearml import Dataset, Task

from src.config import CLEARML_PROJECT_NAME


def check_connection():
    test_task = Task.init(project_name=CLEARML_PROJECT_NAME, task_name="connectivity-check")
    print(f"Connected to ClearML — check app.clear.ml, project '{CLEARML_PROJECT_NAME}'")
    test_task.close()


def register_dataset(local_dir, dataset_name):
    """Version the processed data folder in ClearML. Returns the new dataset ID."""
    dataset = Dataset.create(dataset_name=dataset_name, dataset_project=CLEARML_PROJECT_NAME)
    dataset.add_files(str(local_dir))
    dataset.upload()
    dataset.finalize()
    print(f"Dataset registered. Dataset ID: {dataset.id}")
    return dataset.id


def pull_dataset(dataset_id):
    """Fetch a previously registered dataset by ID, returning its local path."""
    local_path = Dataset.get(dataset_id=dataset_id).get_local_copy()
    print("Dataset pulled to:", local_path)
    return local_path


def start_task(task_name, config=None):
    # output_uri=True uploads models/artifacts to the configured ClearML files
    # server instead of leaving them referenced by a local temp-file path —
    # without it, OutputModel.update_weights() registers a file:///tmp/... URI
    # that gets garbage-collected the moment the temp file is cleaned up,
    # leaving the registered "model" with no actually-retrievable weights.
    task = Task.init(project_name=CLEARML_PROJECT_NAME, task_name=task_name, output_uri=True)
    if config:
        task.connect(config)
    return task
