from fastapi import APIRouter

from app.api.v1 import audit, auth, commands, machines

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(machines.router)
api_router.include_router(commands.router)
api_router.include_router(audit.router)
