"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import config, pipeline, transactions

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
