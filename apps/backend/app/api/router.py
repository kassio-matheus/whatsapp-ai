from fastapi import APIRouter, Depends

from app.modules.ai.router import router as ai_router
from app.modules.ai_whatsapp.router import router as ai_whatsapp_router
from app.modules.auth.router import router as auth_router
from app.modules.companies.router import router as companies_router
from app.modules.health.router import router as health_router
from app.modules.notifications.router import router as notifications_router
from app.modules.whatsapp.router import (
    router as whatsapp_router,
)
from app.modules.whatsapp.router import (
    webhook_router as whatsapp_webhook_router,
)
from app.utils.deps import require_auth

api_router = APIRouter()

api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
)
api_router.include_router(
    ai_router,
    prefix="/ai",
    tags=["AI Chat"],
    dependencies=[Depends(require_auth)],
)
api_router.include_router(
    companies_router,
    prefix="/companies",
    tags=["Companies"],
    dependencies=[Depends(require_auth)],
)
api_router.include_router(
    whatsapp_router,
    prefix="/whatsapp",
    tags=["WhatsApp"],
    dependencies=[Depends(require_auth)],
)
api_router.include_router(
    ai_whatsapp_router,
    prefix="/whatsapp",
    tags=["WhatsApp AI"],
    dependencies=[Depends(require_auth)],
)
api_router.include_router(
    whatsapp_webhook_router,
    prefix="/whatsapp",
    tags=["WhatsApp Webhooks"]
)
api_router.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[Depends(require_auth)],
)
api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)
