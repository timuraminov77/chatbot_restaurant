import chromadb
from chromadb.utils import embedding_functions
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CHROMA_PATH, OPENAI_API_KEY, INFO_MD_PATH
from RAG.parser import parse_md_chunks


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    emb_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name="text-embedding-3-small"
    )

    collection = client.get_or_create_collection("restaurant", embedding_function=emb_fn)
    return collection


def populate_collection(collection):
    """Загружает чанки из info.md в ChromaDB (вызывать один раз)."""
    chunks = parse_md_chunks(INFO_MD_PATH)
    chunks = [c for c in chunks if c["metadata"]["section"] is not None]
    chunks = [c for c in chunks if len(c["content"]) > 50]

    collection.add(
        ids=[str(i) for i in range(len(chunks))],
        documents=[c["content"] for c in chunks],
        metadatas=[
            {k: (v if v is not None else "") for k, v in c["metadata"].items()}
            for c in chunks
        ]
    )
    print(f"Загружено {len(chunks)} чанков в ChromaDB")


def query_collection(collection, user_query: str, n_results: int = 3) -> list[str]:
    results = collection.query(
        query_texts=[user_query],
        n_results=n_results
    )
    return results["documents"][0]
