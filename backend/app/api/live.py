"""Live match endpoints backed by Redis with graceful degradation."""

from fastapi import APIRouter

from app.services.live_service import LiveService

router = APIRouter(tags=["live"])
live_service = LiveService()


@router.get("/")
async def list_live_matches():
    """Return live matches from cache for frontend fallback polling."""
    return await live_service.get_live_matches()


@router.get("/status")
async def get_live_status():
    """Return live-cache degradation status for frontend fallback logic."""
    return await live_service.check_degradation()


@router.get("/{match_id}")
async def get_live_match(match_id: int):
    """Return cached live data for a single match."""
    return await live_service.get_live_match(match_id)
