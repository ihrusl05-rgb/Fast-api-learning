from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.common import (PAGE_SIZE, REGISTRATION_ERROR_MESSAGES, build_registration_context, fetch_active_categories, format_validation_error, group_products_by_category, render_template, require_authenticated_user)
from app.core.security import hash_password, verify_password
from app.database.database import get_db
from app.models.models import Category, Product, User
from app.schemas.schemas import UserCreate

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    categories_count = await db.scalar(
        select(func.count()).select_from(Category).where(Category.is_active.is_(True))
    )
    offers_count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    )
    featured_categories_result = await db.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.name.asc())
        .limit(3)
    )
    featured_offers_result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.is_active.is_(True))
        .order_by(Product.id.desc())
        .limit(3)
    )

    return render_template(
        request,
        "index.html",
        {
            "username": user.username,
            "stats": {
                "categories": categories_count or 0,
                "offers": offers_count or 0,
            },
            "featured_categories": featured_categories_result.scalars().all(),
            "featured_offers": featured_offers_result.scalars().all(),
        },
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    normalized_username = username.strip()

    result = await db.execute(select(User).where(User.username == normalized_username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(password,user.hashed_password):
        return render_template(
            request,
            "login.html",
            {
                "message": "Неверное имя пользователя или пароль",
                "form_data": {"username": normalized_username},
            },
            status_code=400,
        )

    request.session["username"] = user.username
    return RedirectResponse(url="/", status_code=303)


@router.get("/registration", response_class=HTMLResponse)
async def registration_page(request: Request):
    return render_template(
        request,
        "registration.html",
        build_registration_context(),
    )


@router.post("/registration", response_class=HTMLResponse)
async def registration_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    raw_username = username.strip()
    raw_email = email.strip()

    try:
        user_data = UserCreate(email=raw_email, username=raw_username, password=password)
    except ValidationError as exc:
        return render_template(request, "registration.html", build_registration_context(
                format_validation_error(exc, REGISTRATION_ERROR_MESSAGES),
                username=raw_username,
                email=raw_email,
            ),
            status_code=400,
        )

    result = await db.execute(
        select(User).where(
            or_(
                User.username == user_data.username,
                User.email == user_data.email,
            )
        )
    )
    existing_users = result.scalars().all()

    if existing_users:
        duplicate_message = "Пользователь с таким username или email уже существует"
        if any(user.username == user_data.username for user in existing_users):
            duplicate_message = "Пользователь с таким username уже существует"
        elif any(user.email == user_data.email for user in existing_users):
            duplicate_message = "Пользователь с таким email уже существует"

        return render_template(
            request,
            "registration.html",
            build_registration_context(
                duplicate_message,
                username=user_data.username,
                email=user_data.email,
            ),
            status_code=400,
        )

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    await db.commit()

    return RedirectResponse(url="/login", status_code=303)


@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/sales", response_class=HTMLResponse)
async def sales(
    request: Request,
    category_id: int | None = None,
    q: str | None = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    categories = await fetch_active_categories(db)

    products_query = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.is_active.is_(True))
        .order_by(Product.category_id.asc(), Product.name.asc())
    )

    if category_id is not None:
        products_query = products_query.where(Product.category_id == category_id)

    search_query = (q or "").strip()
    if search_query:
        if search_query.isdigit() and len(search_query) <= 5:
            products_query = products_query.where(Product.id == int(search_query))
        else:
            products_query = products_query.where(
                or_(
                    Product.name.ilike(f"%{search_query}%"),
                    Product.description.ilike(f"%{search_query}%"),
                )
            )

    page = max(page, 1)
    total_products = await db.scalar(
        select(func.count()).select_from(products_query.subquery())
    )
    total_pages = max(((total_products or 0) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    current_page = min(page, total_pages)

    paginated_query = products_query.offset((current_page - 1) * PAGE_SIZE).limit(
        PAGE_SIZE
    )
    products_result = await db.execute(paginated_query)
    products = list(products_result.scalars().all())
    sections = group_products_by_category(categories, products)

    return render_template(
        request,
        "sales.html",
        {
            "username": user.username,
            "categories": categories,
            "products": products,
            "sections": sections,
            "selected_category_id": category_id,
            "search_query": search_query,
            "page": current_page,
            "total_pages": total_pages,
            "has_previous": current_page > 1,
            "has_next": current_page < total_pages,
            "total_products": total_products or 0,
        },
    )


@router.get("/sales/{product_slug}", response_class=HTMLResponse)
async def offer_detail(
    request: Request,
    product_slug: str,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(
            Product.slug == product_slug,
            Product.is_active.is_(True),
        )
    )
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(status_code=404, detail="Предложение не найдено")

    related_result = await db.execute(
        select(Product)
        .where(
            Product.category_id == product.category_id,
            Product.id != product.id,
            Product.is_active.is_(True),
        )
        .order_by(Product.name.asc())
        .limit(3)
    )

    return render_template(
        request,
        "offer_detail.html",
        {
            "username": user.username,
            "product": product,
            "related_products": related_result.scalars().all(),
        },
    )
