from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # Groq LLM
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    llm_model: str = Field("llama-3.3-70b-versatile", env="LLM_MODEL")
    router_model: str = Field("llama-3.1-8b-instant", env="ROUTER_MODEL")

    # Local embeddings via sentence-transformers (no API key needed)
    embedding_model: str = Field("all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_dim: int = Field(384, env="EMBEDDING_DIM")

    # JWT Auth
    secret_key: str = Field("change-me-in-production", env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Storage
    faiss_index_path: str = Field("data/faiss_index", env="FAISS_INDEX_PATH")
    sqlite_db_path: str = Field("data/chatbot.db", env="SQLITE_DB_PATH")

    # Chunking
    chunk_size: int = Field(512, env="CHUNK_SIZE")
    chunk_overlap: int = Field(50, env="CHUNK_OVERLAP")

    # Retrieval
    top_k_retrieval: int = Field(20, env="TOP_K_RETRIEVAL")
    top_k_rerank: int = Field(5, env="TOP_K_RERANK")
    bm25_weight: float = Field(0.4, env="BM25_WEIGHT")
    semantic_weight: float = Field(0.6, env="SEMANTIC_WEIGHT")

    # Audit log retention (years)
    audit_retention_years: int = 7

    # API
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
