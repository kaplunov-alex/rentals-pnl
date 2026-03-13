"""FastAPI application entry point."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import config, pipeline, transactions

# Load secrets for local development — tries config_secrets.env first, then .env
# (no-op if vars already set via environment, e.g. in Docker/Cloud Run)
load_dotenv("config_secrets.env")
load_dotenv()

app = FastAPI(
    title="Rental P&L API",
    description="Backend for the Rental Property P&L automation web app.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router, prefix="/api", tags=["transactions"])
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
app.include_router(config.router, prefix="/api", tags=["config"])


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}


# Serve the React SPA — only mounted if the frontend has been built (i.e. in Docker)
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all: serve file if it exists, else index.html (SPA routing)."""
        candidate = _FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
