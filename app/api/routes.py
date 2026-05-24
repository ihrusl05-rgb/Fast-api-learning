from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.security import hash_password, verify_password
from app.models.models import Category, Product, User
from sqlalchemy import select
from app.schemas.schemas import UserCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "username": user.username})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/registration", response_class=HTMLResponse)
async def registration_page(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})


@router.post("/login", response_class=HTMLResponse,)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "message": "Неверное имя пользователя или пароль",
            },
            status_code=400,
        )
    request.session["username"] = user.username
    return RedirectResponse(url="/", status_code=303)



@router.post("/registration", response_class=HTMLResponse)
async def registration_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    if not username or not password:
        return templates.TemplateResponse(
            "registration.html",
            {"request": request, "message": "Username и password обязательны"},
            status_code=400,
        )
    
    user_data = UserCreate(
        email=email,
        username=username,
        password=password
    )


    query = select(User).where((User.username == user_data.username) | (User.email == user_data.email))
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        return templates.TemplateResponse(
            "registration.html",
            {"request": request, "message": "Пользователь с таким username или email уже существует"},
            status_code=400,
        )
    
    new_user = User(email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password)
    )
    db.add(new_user)
    await db.commit()

    return RedirectResponse(url="/login", status_code=303)


@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/sales", response_class=HTMLResponse)
async def sales(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    query = select(Category).where(Category.is_active.is_(True))
    result = await db.execute(query)
    categories = result.scalars().all()

    query = select(Product).where(Product.is_active.is_(True))
    result = await db.execute(query)
    products = result.scalars().all()

 

    return templates.TemplateResponse("section.html", {"request": request, "username": user.username, "categories": categories, "products": products})






def get_current_username(request: Request):
    return request.session.get("username")

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    username = get_current_username(request)
    if not username:
        return None
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()