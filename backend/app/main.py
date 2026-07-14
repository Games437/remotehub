from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

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
    expose_headers=["X-Total-Count"],  # so the frontend can read pagination totals cross-origin
)

app.include_router(api_router)
app.include_router(agent_ws_router)


def _sync_command_type_enum() -> None:
    """`Base.metadata.create_all()` only creates missing tables/types — it
    never ALTERs an existing Postgres enum when the Python `CommandType`
    enum gains a new member. Without this, every new command type needs a
    manual `ALTER TYPE commandtype ADD VALUE ...` run by hand against each
    database (local, Render, ...), which is exactly the recurring problem
    that's bitten this project several times already. Do it here instead,
    every startup, reading the required values straight from the Python
    enum — one source of truth, self-healing on every deploy.

    ADD VALUE can't run inside an ordinary transaction block in Postgres,
    so this uses an autocommit connection; each ALTER TYPE commits on its
    own immediately.
    """
    from app.models.command import CommandType

    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        for value in CommandType:
            conn.execute(text(f"ALTER TYPE commandtype ADD VALUE IF NOT EXISTS '{value.value}'"))


@app.on_event("startup")
def on_startup() -> None:
    # For a real deployment, replace this with Alembic migrations
    # (`alembic upgrade head`) run as a separate release step.
    Base.metadata.create_all(bind=engine)
    _sync_command_type_enum()

    # A fresh process has zero live agent connections by definition — any
    # machine row still marked "online" from before this restart is stale
    # (the previous process was killed before its websocket cleanup ran).
    # Reset it here so nothing shows a false "online" badge before the
    # agent reconnects.
    from sqlalchemy.orm import Session
    from app.models.machine import Machine, MachineStatus

    with Session(engine) as db:
        db.query(Machine).filter(Machine.status == MachineStatus.online).update(
            {Machine.status: MachineStatus.offline}
        )
        db.commit()


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
