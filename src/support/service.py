"""Builds the live pipeline: dataset store, policy index, fine-tuned
classifier and (optionally) the Groq LLM."""
import os
from pathlib import Path

import torch

from src.config import CLEARML_PROJECT_NAME, MODEL_NAME, ROOT_DIR, SUPPORT_MODEL_REGISTRY_NAME
from src.support.classifier import SupportClassifier
from src.support.knowledge import KnowledgeBase
from src.support.pipeline import SupportPipeline
from src.support.store import DataStore

LOCAL_ADAPTER = ROOT_DIR / "outputs" / "support-classifier" / "adapter"
GROQ_MODEL = os.environ.get("SUPPORTAI_GROQ_MODEL", "openai/gpt-oss-20b")


def adapter_path():
    """SUPPORTAI_ADAPTER_DIR wins, then the ClearML production model, then the local training output."""
    explicit = os.environ.get("SUPPORTAI_ADAPTER_DIR")
    if explicit:
        return explicit, "SUPPORTAI_ADAPTER_DIR"
    if os.environ.get("CLEARML_API_ACCESS_KEY"):
        try:
            from clearml import Model

            from src.config import configure_clearml_env

            configure_clearml_env()
            models = Model.query_models(project_name=CLEARML_PROJECT_NAME, model_name=SUPPORT_MODEL_REGISTRY_NAME, tags=["production"])
            if models:
                path = models[0].get_local_copy()
                if path:
                    return path, f"ClearML model {models[0].id}"
        except Exception as exc:
            print(f"ClearML model lookup failed ({type(exc).__name__}: {exc}); trying the local adapter")
    if LOCAL_ADAPTER.exists():
        return str(LOCAL_ADAPTER), "local training output"
    raise RuntimeError("No classifier adapter found. Train one with `python scripts/train_support_classifier.py`.")


def load_classifier():
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    path, source = adapter_path()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.bfloat16, device_map="auto")
    model = PeftModel.from_pretrained(base, path)
    model.eval()
    print(f"Support classifier loaded from {source}")
    return SupportClassifier(model, tokenizer), source


def build_llm():
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set: responses will use the built-in templates")
        return None
    from langchain_groq import ChatGroq

    return ChatGroq(model=GROQ_MODEL, temperature=0.2, timeout=25, max_retries=1)


def build_pipeline(classifier=None):
    store = DataStore()
    knowledge = KnowledgeBase()
    if knowledge.count() == 0:
        knowledge.build()
    source = "provided"
    if classifier is None:
        classifier, source = load_classifier()
    pipeline = SupportPipeline(store, classifier, knowledge, build_llm())
    pipeline.classifier_source = source
    return pipeline
