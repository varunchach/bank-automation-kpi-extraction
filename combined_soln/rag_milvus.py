"""RAG using Milvus Lite (milvus.db) + sentence-transformers. Optional: runs without pymilvus (e.g. local dev)."""

import logging
from pathlib import Path
from typing import List, Any

LOG = logging.getLogger("kpi_app.rag")

try:
    from pymilvus import MilvusClient, DataType
    try:
        from pymilvus.exceptions import ConnectionConfigException
    except ImportError:
        ConnectionConfigException = Exception  # type: ignore[misc, assignment]
    PYMILVUS_AVAILABLE = True
except ImportError:
    MilvusClient = None  # type: ignore[misc, assignment]
    DataType = None  # type: ignore[misc, assignment]
    ConnectionConfigException = Exception  # type: ignore[misc, assignment]
    PYMILVUS_AVAILABLE = False
    LOG.info("pymilvus not installed: RAG search disabled (chat will use KPI table only). Install with: pip install pymilvus")

MILVUS_DB_PATH = Path("/tmp") / "kpi_app" / "milvus.db"
COLLECTION_NAME = "pdf_chunks"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
TOP_K = 5


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    if not text or not text.strip():
        return []
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


def _get_embedder():
    """Lazy load sentence-transformers. Use GPU when available."""
    from sentence_transformers import SentenceTransformer
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"
    return SentenceTransformer("all-MiniLM-L6-v2", device=device)


def index_documents(
    pdf_text: str,
    milvus_path: Path = MILVUS_DB_PATH,
) -> int:
    """Chunk PDF text, embed, and store in Milvus. Returns count of chunks indexed. Returns 0 if pymilvus not installed."""
    if not PYMILVUS_AVAILABLE:
        LOG.info("index_documents: pymilvus not available, skipping RAG indexing")
        return 0
    if not pdf_text or not pdf_text.strip():
        LOG.warning("index_documents: empty pdf_text, skipping")
        return 0
    chunks = _chunk_text(pdf_text)
    if not chunks:
        LOG.warning("index_documents: no chunks produced")
        return 0
    LOG.info("RAG: chunked to %d chunks, loading embedder", len(chunks))
    embedder = _get_embedder()
    LOG.info("RAG: encoding chunks")
    embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()

    milvus_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        client = MilvusClient(str(milvus_path))
    except (ConnectionConfigException, Exception) as e:
        if "milvus_lite" in str(e).lower() or "milvus-lite" in str(e).lower():
            LOG.warning("MilvusClient requires milvus_lite for file URI; RAG indexing skipped: %s", e)
        else:
            LOG.warning("MilvusClient connect failed; RAG indexing skipped: %s", e)
        return 0
    dim = len(embeddings[0])
    try:
        if COLLECTION_NAME in client.list_collections():
            client.drop_collection(COLLECTION_NAME)
    except Exception:
        pass

    schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=True)
    schema.add_field("vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("text", datatype=DataType.VARCHAR, max_length=65535)
    client.create_collection(collection_name=COLLECTION_NAME, schema=schema)

    data = [{"vector": emb, "text": chunks[i]} for i, emb in enumerate(embeddings)]
    client.insert(collection_name=COLLECTION_NAME, data=data)
    LOG.info("RAG: indexed %d chunks into Milvus", len(chunks))
    return len(chunks)


def get_fallback_chunks(pdf_text: str, max_chunks: int = 5) -> List[str]:
    """When RAG/Milvus is not available, return first N chunks of pdf_text so the LLM still gets extracted context (not empty)."""
    if not pdf_text or not pdf_text.strip():
        return []
    chunks = _chunk_text(pdf_text)
    return chunks[:max_chunks] if chunks else []


def search_chunks(
    question: str,
    top_k: int = TOP_K,
    milvus_path: Path = MILVUS_DB_PATH,
) -> List[str]:
    """Embed question, search Milvus, return matching chunk texts. Returns [] if pymilvus not installed or milvus_lite missing."""
    if not PYMILVUS_AVAILABLE or not question or not question.strip():
        return []
    try:
        client = MilvusClient(str(milvus_path))
    except (ConnectionConfigException, Exception) as e:
        if "milvus_lite" in str(e).lower() or "milvus-lite" in str(e).lower():
            LOG.debug("MilvusClient requires milvus_lite for file URI; returning []")
        return []
    try:
        if COLLECTION_NAME not in client.list_collections():
            return []
    except Exception:
        return []
    embedder = _get_embedder()
    q_emb = embedder.encode([question], show_progress_bar=False).tolist()[0]
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[q_emb],
        limit=top_k,
        output_fields=["text"],
    )
    chunks = []
    for hit in (results[0] if results else []):
        ent = hit.get("entity") or hit
        t = ent.get("text")
        if t:
            chunks.append(t)
    return chunks


def build_entities_json(kpi_df: Any, retrieved_chunks: List[str]) -> dict:
    """Build JSON payload for LLM: kpis + retrieved_chunks."""
    kpis = []
    if kpi_df is not None and hasattr(kpi_df, "to_dict"):
        if not kpi_df.empty:
            kpis = kpi_df.to_dict(orient="records")
    return {
        "kpis": kpis,
        "retrieved_chunks": retrieved_chunks,
    }
