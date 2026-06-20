from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.calls import router as calls_router
from app.api.health import router as health_router
from app.api.messages import router as messages_router
from app.api.profiles import router as profiles_router
from app.api.transporter import router as transporter_router
from app.database import create_all
from app.webhooks.twilio import router as twilio_webhooks_router
from app.webhooks.twiml import router as twiml_router


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        create_all()
        yield

    app = FastAPI(
        title="Lumina WhatsApp Call Service",
        version="0.1.0",
        description="Twilio WhatsApp bot and scheduled outbound call microservice.",
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(messages_router)
    app.include_router(calls_router)
    app.include_router(profiles_router)
    app.include_router(transporter_router)
    app.include_router(twilio_webhooks_router)
    app.include_router(twiml_router)

    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(exist_ok=True)
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    return app


app = create_app()
