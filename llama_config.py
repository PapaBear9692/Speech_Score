# llama_config.py
import os
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"

# cache lines
CACHE_DIR = ROOT_DIR / "model_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

EMBED_MODEL_NAME = "abhinand/MedEmbed-base-v0.1"
EMBEDDING_DIM = 768

PINECONE_INDEX_NAME = "sqbot-data-index"
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"
PINECONE_NAMESPACE = None


def initialize_index():
    """Initialize embeddings and Pinecone vector store index."""
    # Load environment variables
    load_dotenv(ENV_PATH)

    pinecone_api_key = os.getenv("PINECONE_API_KEY")

    if not pinecone_api_key:
        raise ValueError("Missing PINECONE_API_KEY in .env")

    # Embedding model
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=EMBED_MODEL_NAME,
        device="cpu",  # change to "cuda" if you have GPU
        cache_folder=str(CACHE_DIR),
    )

    # Pinecone setup
    pc = Pinecone(api_key=pinecone_api_key)

    existing_indexes = pc.list_indexes().names()

    if PINECONE_INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION,
            ),
        )
    else:
        print(f"Using existing Pinecone index '{PINECONE_INDEX_NAME}'")

    pinecone_index = pc.Index(PINECONE_INDEX_NAME)

    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index,
        namespace=PINECONE_NAMESPACE,
    )

    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    return index

