from contextlib import asynccontextmanager

from app.database.database import create_tables
from app.models import models
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield
app = FastAPI(title="Partner System", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)

