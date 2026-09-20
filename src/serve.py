"""FastAPI app.

Primary: the fashion e-commerce support demo (src/support). All data is
synthetic. Also kept: the earlier ticket-extractor endpoints (/assist,
/generate), which load their own model and are optional: if it can't be
loaded the support demo still serves.

Run with: uvicorn src.serve:app --host 0.0.0.0 --port 8000
"""
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.support import api as support_api
from src.support.service import build_pipeline

support_pipeline = build_pipeline()
support_api.set_pipeline(support_pipeline)

# ---- legacy ticket-extractor model (optional) ----
legacy = None
try:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    from src.config import MODEL_NAME
    from src.promote import get_production_weights
    from src.prompting import generate_prediction, try_parse_json
    from src.rag.retrieve import draft_reply as rag_draft_reply
    from src.train import load_tokenizer

    _model_info, _weights = get_production_weights()
    _base = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.bfloat16, device_map="auto")
    _model = PeftModel.from_pretrained(_base, _weights)
    _model.eval()
    legacy = {"info": _model_info, "model": _model, "tokenizer": load_tokenizer()}
except Exception as exc:  # the demo must not depend on the old model
    print(f"Legacy ticket-extractor model unavailable ({type(exc).__name__}: {exc}). Support demo is unaffected.")

app = FastAPI(title="SupportAI (synthetic demo)")

# Wide open for this demo (no auth, no real data) so the React frontend can
# call it from any origin. Tighten to the frontend's origin before handling
# anything sensitive.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(support_api.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pipeline": True,
        "classifier_source": support_pipeline.classifier_source,
        "llm_enabled": support_pipeline.llm is not None,
        "model_tags": legacy["info"].tags if legacy else [],
    }


def _require_legacy():
    if legacy is None:
        raise HTTPException(status_code=503, detail="The legacy ticket-extractor model is not loaded")
    return legacy


@app.get("/model")
def model_info():
    return {"model_id": _require_legacy()["info"].id, "tags": legacy["info"].tags}


class GenerateRequest(BaseModel):
    instruction: str
    input: str
    max_new_tokens: int = 100


class GenerateResponse(BaseModel):
    model: str
    response: str
    latency_ms: float


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    state = _require_legacy()
    start = time.time()
    output_text = generate_prediction(state["model"], state["tokenizer"], req.instruction, req.input, req.max_new_tokens)
    return GenerateResponse(model="qwen-ticket-extractor-production", response=output_text, latency_ms=round((time.time() - start) * 1000, 2))


class AssistRequest(BaseModel):
    instruction: str
    input: str
    max_new_tokens: int = 40


class AssistResponse(BaseModel):
    classification: Optional[dict]
    classification_raw: str
    reply: str
    sources: List[dict]
    # "high"/"low" is coarse: whether the model's output parsed as valid JSON.
    # The newer /support/resolve endpoint uses real token probabilities.
    confidence: str
    latency_ms: float
    escalation_required: bool


@app.post("/assist", response_model=AssistResponse)
def assist(req: AssistRequest):
    state = _require_legacy()
    start = time.time()
    classification_raw = generate_prediction(state["model"], state["tokenizer"], req.instruction, req.input, req.max_new_tokens)
    classification = try_parse_json(classification_raw)
    intent = classification.get("intent") if classification else None
    confidence = "high" if classification else "low"
    try:
        rag_result = rag_draft_reply(req.input, intent=intent)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return AssistResponse(
        classification=classification,
        classification_raw=classification_raw,
        reply=rag_result["reply"],
        sources=rag_result["sources"],
        confidence=confidence,
        latency_ms=round((time.time() - start) * 1000, 2),
        escalation_required=confidence == "low",
    )
