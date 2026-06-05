from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.processing_jobs import router as processing_jobs_router
from app.api.routes.themes import router as themes_router
from app.api.routes.usage_logs import router as usage_logs_router
from app.config import get_settings

settings = get_settings()
origins = [
    origin.strip()
    for origin in settings.frontend_origins.split(",")
    if origin.strip()
]

app = FastAPI(
    title="SmartDocs IA",
    description="API para consulta inteligente de documentos em PDF usando IA.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "SmartDocs IA API is running",
    }


app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(health_router)
app.include_router(themes_router)
app.include_router(processing_jobs_router)
app.include_router(usage_logs_router)
app.include_router(auth_router)
