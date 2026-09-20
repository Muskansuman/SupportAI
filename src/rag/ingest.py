"""Chunk data/kb/articles.jsonl and embed into a local Chroma vector store
using free local sentence-transformers embeddings (no API key needed).

Re-run any time articles.jsonl changes:
    python3 -m src.rag.ingest
"""
import json

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import ROOT_DIR

KB_PATH = ROOT_DIR / "data" / "kb" / "articles.jsonl"
CHROMA_DIR = ROOT_DIR / "data" / "chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_articles():
    with open(KB_PATH) as f:
        articles = [json.loads(line) for line in f]
    return [
        Document(
            page_content=f"{a['title']}\n\n{a['content']}",
            metadata={"id": a["id"], "intent": a["intent"], "title": a["title"]},
        )
        for a in articles
    ]


def build_vector_store():
    documents = load_articles()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vector_store = Chroma.from_documents(
        chunks, embeddings, persist_directory=str(CHROMA_DIR)
    )
    print(f"Ingested {len(documents)} articles -> {len(chunks)} chunks -> {CHROMA_DIR}")
    return vector_store


if __name__ == "__main__":
    build_vector_store()
