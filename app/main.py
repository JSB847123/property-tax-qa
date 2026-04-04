from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import register_startup
from app.routers.backup import router as backup_router
from app.routers.chat import router as chat_router
from app.routers.documents import router as documents_router
from app.routers.favorites import router as favorites_router
from app.routers.search import router as search_router
from app.routers.settings import router as settings_router


app = FastAPI(
    title="tax-rag",
    version="0.1.0",
    description="취득세·재산세 전문 RAG 시스템 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_startup(app)
app.include_router(documents_router)
app.include_router(backup_router)
app.include_router(chat_router)
app.include_router(search_router)
app.include_router(settings_router)
app.include_router(favorites_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
