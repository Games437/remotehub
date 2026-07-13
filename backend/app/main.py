from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import Base, engine
from app.websocket.agent_ws import router as agent_ws_router

# Import models so they register on Base.metadata before create_all runs.
from app import models  # noqa: F401

app = FastAPI(title=settings.APP_NAME)

# Layer 1 — HTTPS is terminated at the reverse proxy (nginx/Caddy) in front
# of this service in production; see deployment/nginx.conf. Locally we run
# over plain HTTP for convenience.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(agent_ws_router)


@app.on_event("startup")
def on_startup() -> None:
    # For a real deployment, replace this with Alembic migrations
    # (`alembic upgrade head`) run as a separate release step.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
