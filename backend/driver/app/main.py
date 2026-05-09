from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Driver Service", lifespan=lifespan)
app.include_router(router, prefix="/drivers")
