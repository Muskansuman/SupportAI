"""RAG over the policy documents.

The 10 markdown policies are split into one chunk per `##` section and
embedded (local sentence-transformers, no API key) into a Chroma collection.
It lives in the same persistent Chroma directory as the earlier demo's index,
in its own collection, so there is a single vector store.

    python -m src.support.knowledge      # (re)build the index
"""
import re
from pathlib import Path

from src.config import ROOT_DIR
from src.support.store import DATA_DIR

KB_DIR = DATA_DIR / "knowledge_base"
CHROMA_DIR = ROOT_DIR / "data" / "chroma_db"
COLLECTION = "supportai_kb"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EXCERPT_CHARS = 320


def _title(markdown):
    match = re.match(r"#\s+(.+)", markdown)
    return match.group(1).strip() if match else "Policy"


def load_chunks(kb_dir=KB_DIR):
    """One chunk per `##` section, plus the document title for context."""
    chunks = []
    for path in sorted(Path(kb_dir).glob("*.md")):
        markdown = path.read_text()
        title = _title(markdown)
        body = "\n".join(line for line in markdown.splitlines() if not line.startswith(">"))
        for section in re.split(r"\n(?=## )", body):
            if not section.startswith("## "):
                continue
            heading, _, text = section.partition("\n")
            heading = heading[3:].strip()
            chunks.append({"doc_id": path.stem, "title": title, "section": heading, "text": f"{title} - {heading}\n{text.strip()}"})
    return chunks


class KnowledgeBase:
    def __init__(self, persist_dir=CHROMA_DIR, kb_dir=KB_DIR):
        from langchain_huggingface import HuggingFaceEmbeddings

        self.kb_dir = kb_dir
        self.persist_dir = persist_dir
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self.store = self._new_store()

    def _new_store(self):
        from langchain_community.vectorstores import Chroma

        return Chroma(
            collection_name=COLLECTION,
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_metadata={"hnsw:space": "cosine"},
        )

    def build(self):
        chunks = load_chunks(self.kb_dir)
        self.store.delete_collection()
        self.store = self._new_store()
        self.store.add_texts(
            [c["text"] for c in chunks],
            metadatas=[{"doc_id": c["doc_id"], "title": c["title"], "section": c["section"]} for c in chunks],
            ids=[f"{c['doc_id']}::{i}" for i, c in enumerate(chunks)],
        )
        return len(chunks)

    def count(self):
        return self.store._collection.count()

    def search(self, query, k=4):
        """Top chunks with cosine relevance (1 = identical). Only what was retrieved is returned."""
        hits = self.store.similarity_search_with_score(query, k=k)
        return [
            {
                "doc_id": doc.metadata["doc_id"],
                "title": doc.metadata["title"],
                "section": doc.metadata["section"],
                "excerpt": doc.page_content[:EXCERPT_CHARS] + ("…" if len(doc.page_content) > EXCERPT_CHARS else ""),
                "text": doc.page_content,
                "score": round(1 - float(distance), 4),
            }
            for doc, distance in hits
        ]


if __name__ == "__main__":
    kb = KnowledgeBase()
    print(f"Indexed {kb.build()} chunks from {len(list(Path(KB_DIR).glob('*.md')))} documents into collection '{COLLECTION}' ({kb.count()} stored)")
