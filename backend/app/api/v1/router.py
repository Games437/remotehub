from fastapi import APIRouter

from app.api.v1 import audit, auth, chat, commands, machines

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(machines.router)
api_router.include_router(commands.router)
api_router.include_router(audit.router)
api_router.include_router(chat.router)
api_router.include_router(chat.agent_router)
