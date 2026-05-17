from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router

app = FastAPI(
    title="AutoManual AI",
    description="API para consulta inteligente de manuais automotivos usando IA.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "AutoManual AI API is running",
    }


app.include_router(chat_router)
app.include_router(documents_router)
