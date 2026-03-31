"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.storage.database import init_db
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.admin import router as admin_router
from src.api.routes.chat_history import router as chat_history_router

logger = logging.getLogger(__name__)


def _run_scheduled_sync():
    """
    Background job: syncs all configured live connectors.
    Only runs if credentials are present in .env.
    Skips silently if a connector isn't configured.
    """
    from src.config import settings
    from src.ingestion.pipeline import IngestionPipeline
    from src.ingestion.connectors.live_connectors import ConfluenceConnector, JiraConnector
    from src.storage.database import set_connector_sync_state

    connectors = []

    if settings.confluence_url and settings.confluence_user and settings.confluence_api_token:
        # Read space keys from env (comma-separated), default to 'OPS'
        space_keys = getattr(settings, 'confluence_space_keys', 'OPS').split(',')
        for space_key in [s.strip() for s in space_keys if s.strip()]:
            connectors.append(ConfluenceConnector(space_key=space_key))
            logger.info("Scheduler: queued Confluence sync for space '%s'", space_key)

    if settings.jira_url and settings.jira_user and settings.jira_api_token:
        project_keys = getattr(settings, 'jira_project_keys', '').split(',')
        for pk in [p.strip() for p in project_keys if p.strip()]:
            connectors.append(JiraConnector(project_key=pk))
            logger.info("Scheduler: queued Jira sync for project '%s'", pk)

    if not connectors:
        logger.debug("Scheduler: no connectors configured, skipping run")
        return

    try:
        pipeline = IngestionPipeline(connectors=connectors)
        summary = pipeline.run()
        for c in connectors:
            source_type = type(c).__name__.replace('Connector', '').lower()
            source_key = getattr(c, 'space_key', None) or getattr(c, 'project_key', 'default')
            set_connector_sync_state(
                source_key=f"{source_type}:{source_key}",
                source_type=source_type,
                docs_synced=summary.get('documents_processed', 0),
                status='success',
            )
        logger.info("Scheduler: sync complete — %d docs, %d new chunks",
                    summary['documents_processed'], summary['chunks_created'])
    except Exception as exc:
        logger.error("Scheduler: sync failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start background scheduler on startup."""
    init_db()
    logger.info("✓ Database initialized")
    print("✓ Database initialized")

    # ── Start APScheduler for auto-sync ─────────────────────────────────────────
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.config import settings
        sync_interval_hours = getattr(settings, 'sync_interval_hours', 6)

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            _run_scheduled_sync,
            trigger="interval",
            hours=sync_interval_hours,
            id="live_connector_sync",
            replace_existing=True,
            max_instances=1,          # never overlap
        )
        scheduler.start()
        logger.info("✓ Auto-sync scheduler started (every %dh)", sync_interval_hours)
        print(f"✓ Auto-sync scheduler started (every {sync_interval_hours}h)")
    except ImportError:
        logger.warning("APScheduler not installed — auto-sync disabled. Run: pip install apscheduler")
    except Exception as exc:
        logger.warning("Scheduler failed to start: %s", exc)

    yield  # App is running

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


app = FastAPI(
    title="Banking Knowledge Chatbot API",
    description="AI-powered RAG chatbot for Citi Banking Operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(chat_history_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "banking-chatbot-poc"}
