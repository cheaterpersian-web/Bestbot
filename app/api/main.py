from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from core.config import settings
from core.db import init_db_schema

app = FastAPI(title="VPN Bot API", version="0.1.0")
BASE_DIR = Path(__file__).resolve().parent.parent  # /app/api -> /app
WEBAPP_STATIC_DIR = BASE_DIR / "webapp" / "static"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env}


@app.on_event("startup")
async def _startup():
    # Ensure schema exists in case Alembic didn't run
    try:
        await init_db_schema()
    except Exception:
        pass

# Serve WebApp index at root
@app.get("/", response_class=HTMLResponse)
async def root_index():
    index_file = WEBAPP_STATIC_DIR / "index.html"
    return FileResponse(str(index_file))

# Include WebApp API router
try:
    from webapp.api import router as webapp_router
    app.include_router(webapp_router)
    # Mount static files for webapp
    if WEBAPP_STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(WEBAPP_STATIC_DIR)), name="static")
except Exception:
    # Avoid crashing API if webapp not present in some builds
    pass

