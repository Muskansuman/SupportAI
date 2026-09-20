"""Retrieve relevant KB chunks for a support ticket and draft a grounded
reply using Groq's free-tier LLM API.

Standalone smoke test: python3 -m src.rag.retrieve
serve.py's /assist endpoint calls draft_reply() directly.
"""
import os

from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

from src.config import ROOT_DIR

CHROMA_DIR = ROOT_DIR / "data" / "chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL = "openai/gpt-oss-20b"
TOP_K = 3

_PROMPT_TEMPLATE = """You are a customer support agent. Using ONLY the knowledge base \
excerpts below, draft a short, helpful reply to the customer's message. If the \
excerpts don't cover the question, say you'll escalate to a human agent instead \
of guessing.

Knowledge base excerpts:
{context}

Customer message: {ticket_text}

Reply:"""


def _load_retriever(intent=None):
    if not CHROMA_DIR.exists():
        raise RuntimeError(
            f"No vector store found at {CHROMA_DIR} — run `python3 -m src.rag.ingest` first."
        )
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vector_store = Chroma(persist_directory=str(CHROMA_DIR), embedding_function=embeddings)
    search_kwargs = {"k": TOP_K}
    if intent:
        # Each KB article is tagged with the intent it covers — scoping
        # retrieval to the already-classified intent avoids pulling in
        # loosely-related articles that pure semantic search over the whole
        # KB can surface (e.g. "How to place an order" showing up for a
        # ticket about tracking a missing one).
        search_kwargs["filter"] = {"intent": intent}
    return vector_store.as_retriever(search_kwargs=search_kwargs)


def _load_llm():
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set — sign up at console.groq.com (free tier) "
            "and add GROQ_API_KEY to your .env before using reply drafting."
        )
    return ChatGroq(model=GROQ_MODEL, temperature=0.2)


def draft_reply(ticket_text, intent=None):
    """Retrieve relevant KB chunks and draft a grounded reply.

    `intent`, when given (the classifier's own output for this ticket),
    scopes retrieval to that intent's KB article instead of searching the
    whole KB — falls back to unfiltered search if that scoped search comes
    back empty (e.g. an intent the KB doesn't actually cover).

    Rebuilds the retriever and LLM client on every call — fine for a demo;
    if latency creeps up under repeated use, move both to serve.py's
    startup section instead (mirroring how the classifier model is loaded
    once at import time there) rather than optimizing this up front.
    """
    docs = _load_retriever(intent=intent).invoke(ticket_text)
    if not docs and intent:
        docs = _load_retriever(intent=None).invoke(ticket_text)
    context = "\n\n".join(d.page_content for d in docs)

    llm = _load_llm()
    prompt = _PROMPT_TEMPLATE.format(context=context, ticket_text=ticket_text)
    response = llm.invoke(prompt)

    sources = [{"id": d.metadata.get("id"), "title": d.metadata.get("title")} for d in docs]
    return {"reply": response.content, "sources": sources}


if __name__ == "__main__":
    result = draft_reply("do I get charged if I cancel my plan early?")
    print("Reply:", result["reply"])
    print("Sources:", result["sources"])
