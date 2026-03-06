from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .config import Settings, get_settings
from .models import AnalyzeRequest, AnalyzeResponse
from .orchestrator import MnaAnalyzer

app = FastAPI(
    title="European Public M&A Analyzer",
    version="0.1.0",
    description="Analyse d'opportunité d'acquisition entre deux sociétés cotées en Europe à partir de documents publics.",
)


@app.on_event("startup")
def validate_settings() -> None:
    # Fail fast on startup if required runtime configuration is missing.
    get_settings()


def get_analyzer(settings: Settings = Depends(get_settings)) -> MnaAnalyzer:
    return MnaAnalyzer(settings)


@app.get("/healthz")
def healthz(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "default_model": settings.openai_model,
        "extraction_model": settings.extraction_model,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalyzeRequest,
    analyzer: MnaAnalyzer = Depends(get_analyzer),
) -> AnalyzeResponse:
    try:
        return analyzer.analyze(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - integration boundary
        raise HTTPException(status_code=502, detail=f"Analysis pipeline failed: {exc}") from exc
