from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.db import init_db_schema

app = FastAPI(title="VPN Bot API", version="0.1.0")

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

# Include WebApp API router
try:
    from webapp.api import router as webapp_router
    app.include_router(webapp_router)
    # Mount static files for webapp
    app.mount("/static", StaticFiles(directory="app/webapp/static"), name="static")
except Exception as e:
    # Avoid crashing API if webapp not present in some builds
    pass

