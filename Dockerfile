# GPU serving image for the ticket-extraction FastAPI app.
#
# torch (2.13.0+cu130) and bitsandbytes (0.50.1, bundles precompiled
# libbitsandbytes_cudaXXX.so per CUDA version) are both self-contained pip
# wheels — no system CUDA toolkit is needed in the image itself. At `docker
# run` time, the NVIDIA driver + nvidia-container-toolkit on the HOST is
# what exposes the GPU into the container via `--gpus all`.
FROM python:3.10-slim

WORKDIR /app

# build-essential: chromadb's hnswlib dependency occasionally needs to
# compile from source if no prebuilt wheel matches the target platform.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY evaluation/ ./evaluation/
COPY data/kb/ ./data/kb/

# The synthetic dataset and the policy index are built here from source
# (fixed seed), not copied from the dev tree, so the image is reproducible.
RUN python scripts/generate_dataset.py && python scripts/validate_dataset.py > /dev/null
RUN python -m src.support.knowledge
# Legacy ticket-extractor index (its own collection in the same Chroma store).
RUN python -m src.rag.ingest

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# ClearML (CLEARML_API_ACCESS_KEY, CLEARML_API_SECRET_KEY) and Groq
# (GROQ_API_KEY) credentials are NOT baked into the image — pass them at
# `docker run` time via --env-file, so secrets never live in an image layer.
CMD ["uvicorn", "src.serve:app", "--host", "0.0.0.0", "--port", "8000"]
