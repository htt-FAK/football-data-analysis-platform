"""FastAPI application entrypoint."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import (
    crawl_router,
    data_sources_router,
    leagues_router,
    live_router,
    matches_router,
    players_router,
    predict_router,
    teams_router,
    worldcup_router,
)
from app.api.websocket import ws_router
from app.config import APP_HOST, APP_PORT, DEBUG, ENABLE_SCHEDULER
from app.services.text_repair import repair_payload

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop background scheduler with the app lifecycle."""
    if ENABLE_SCHEDULER:
        from app.scheduler.jobs import shutdown_scheduler, start_scheduler

        start_scheduler()
        yield
        shutdown_scheduler()
        return

    yield


app = FastAPI(
    title="Football Data Analysis Platform API",
    description="Automated football data collection, normalization, analysis, and reporting API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def repair_json_text_middleware(request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    if not body:
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    try:
        payload = json.loads(body)
    except Exception:
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    repaired = repair_payload(payload)
    content = json.dumps(repaired, ensure_ascii=False).encode("utf-8")
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return Response(
        content=content,
        status_code=response.status_code,
        headers=headers,
        media_type="application/json",
    )

# Resource prefixes are mounted here to keep endpoint paths stable and explicit.
app.include_router(leagues_router, prefix="/api/v1/leagues")
app.include_router(teams_router, prefix="/api/v1/teams")
app.include_router(players_router, prefix="/api/v1/players")
app.include_router(matches_router, prefix="/api/v1/matches")
app.include_router(live_router, prefix="/api/v1/live")
app.include_router(data_sources_router, prefix="/api/v1/data-sources")
app.include_router(crawl_router, prefix="/api/v1/crawl")
app.include_router(worldcup_router, prefix="/api/v1/worldcup")
app.include_router(predict_router, prefix="/api/v1/predict")
app.include_router(ws_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/v1/health", tags=["system"])
async def health_check():
    """Application health check."""
    return {"status": "ok", "service": "sports-analytics", "version": "1.0.0"}


@app.get("/", tags=["system"])
async def root():
    """Root endpoint."""
    return {
        "message": "Football Data Analysis Platform API",
        "docs": "/docs",
        "worldcup": "/worldcup",
    }


@app.get("/worldcup", tags=["system"])
async def worldcup_page():
    """Serve the built-in World Cup presentation page."""
    return FileResponse(STATIC_DIR / "worldcup.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=DEBUG)
