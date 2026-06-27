from app.api.leagues import router as leagues_router
from app.api.teams import router as teams_router
from app.api.players import router as players_router
from app.api.matches import router as matches_router
from app.api.live import router as live_router
from app.api.data_sources import router as data_sources_router
from app.api.crawl import router as crawl_router

__all__ = ["leagues_router", "teams_router", "players_router",
           "matches_router", "live_router", "data_sources_router", "crawl_router"]
