from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.market import router as market_router
from app.api.research import router as research_router
from app.api.user_state import router as user_state_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="ProfitForge Research API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(market_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(user_state_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "profitforge-research-api"}
