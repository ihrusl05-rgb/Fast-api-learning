from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from config import settings

app = FastAPI(title=settings.APP_TITLE)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE,
    same_site=settings.SESSION_SAME_SITE,
    https_only=settings.SESSION_HTTPS_ONLY,
)
