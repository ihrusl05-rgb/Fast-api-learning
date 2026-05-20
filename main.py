from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router

app = FastAPI(title="Partner System")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)
