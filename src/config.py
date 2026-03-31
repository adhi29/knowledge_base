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

    # ── Enterprise Connectors ─────────────────────────────────────────────────
    # Confluence
    confluence_url: Optional[str] = Field(None, env="CONFLUENCE_URL")
    confluence_user: Optional[str] = Field(None, env="CONFLUENCE_USER")
    confluence_api_token: Optional[str] = Field(None, env="CONFLUENCE_API_TOKEN")

    # Jira
    jira_url: Optional[str] = Field(None, env="JIRA_URL")
    jira_user: Optional[str] = Field(None, env="JIRA_USER")
    jira_api_token: Optional[str] = Field(None, env="JIRA_API_TOKEN")

    # Microsoft Graph (Outlook + SharePoint)
    ms_tenant_id: Optional[str] = Field(None, env="MS_TENANT_ID")
    ms_client_id: Optional[str] = Field(None, env="MS_CLIENT_ID")
    ms_client_secret: Optional[str] = Field(None, env="MS_CLIENT_SECRET")
    ms_mailbox: Optional[str] = Field(None, env="MS_MAILBOX")
    ms_sharepoint_site_id: Optional[str] = Field(None, env="MS_SHAREPOINT_SITE_ID")
    ms_sharepoint_drive_id: Optional[str] = Field(None, env="MS_SHAREPOINT_DRIVE_ID")

    # ── Scheduler & notifications ───────────────────────────────────────────────
    sync_interval_hours: int = Field(6, env="SYNC_INTERVAL_HOURS")
    confluence_space_keys: str = Field("OPS", env="CONFLUENCE_SPACE_KEYS")  # comma-separated
    jira_project_keys: str = Field("", env="JIRA_PROJECT_KEYS")             # comma-separated
    slack_webhook_url: Optional[str] = Field(None, env="SLACK_WEBHOOK_URL")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
