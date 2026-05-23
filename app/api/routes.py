from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/registration", response_class=HTMLResponse)
async def registration_page(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "message": f"Форма логина отправлена для пользователя {username}",
        },
    )


@router.post("/registration", response_class=HTMLResponse)
async def registration_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if not username or not password:
        return templates.TemplateResponse(
            "registration.html",
            {"request": request, "message": "Username и password обязательны"},
            status_code=400,
        )

    return RedirectResponse(url="/login", status_code=303)
