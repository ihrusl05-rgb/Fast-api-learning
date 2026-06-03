from collections import defaultdict

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Category, Product, User

templates = Jinja2Templates(directory="app/templates")

REGISTRATION_ERROR_MESSAGES = {
    "email": "Введите корректный email.",
    "username": "Username должен быть от 3 до 30 символов.",
    "password": "Пароль должен быть не короче 6 символов.",
}

CATEGORY_ERROR_MESSAGES = {
    "name": "Название раздела должно быть от 2 до 80 символов.",
    "description": "Описание раздела не должно быть длиннее 500 символов.",
    "icon": "Укажите короткую иконку раздела.",
    "slug": "Slug раздела должен быть в lowercase и через дефис.",
}

PRODUCT_ERROR_MESSAGES = {
    "category_id": "Выберите корректный раздел.",
    "name": "Название карточки должно быть от 2 до 120 символов.",
    "description": "Описание карточки не должно быть длиннее 1000 символов.",
    "price": "Цена должна быть положительным числом.",
    "image": "Ссылка на изображение не должна быть длиннее 255 символов.",
    "slug": "Slug карточки должен быть в lowercase и через дефис.",
}

PAGE_SIZE = 6


def render_template(
    request: Request,
    template_name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    template_context = {"request": request, **(context or {})}
    return templates.TemplateResponse(
        request,
        template_name,
        template_context,
        status_code=status_code,
    )


def get_current_username(request: Request) -> str | None:
    return request.session.get("username")


async def get_current_user(request: Request, db: AsyncSession) -> User | None:
    username = get_current_username(request)
    if not username:
        return None

    result = await db.execute(
        select(User).where(
            User.username == username,
            User.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


def format_validation_error(
    exc: ValidationError,
    error_messages: dict[str, str],
) -> str:
    messages = []
    for error in exc.errors():
        field_name = error["loc"][-1]
        message = error_messages.get(field_name)
        if message and message not in messages:
            messages.append(message)
    return " ".join(messages) or "Проверьте корректность введенных данных."


def build_registration_context(message: str | None = None, **form_data: str) -> dict:
    return {
        "message": message,
        "form_data": {
            "username": form_data.get("username", ""),
            "email": form_data.get("email", ""),
        },
    }


def build_category_form_context(
    message: str | None = None,
    *,
    category: Category | None = None,
    form_data: dict | None = None,
) -> dict:
    category_form_data = form_data or {
        "name": category.name if category else "",
        "description": category.description if category else "",
        "icon": category.icon if category else "📦",
        "slug": category.slug if category else "",
        "is_active": category.is_active if category else True,
    }
    return {"message": message, "form_data": category_form_data}


def build_product_form_context(
    categories: list[Category],
    message: str | None = None,
    *,
    product: Product | None = None,
    form_data: dict | None = None,
) -> dict:
    product_form_data = form_data or {
        "category_id": product.category_id if product else "",
        "name": product.name if product else "",
        "description": product.description if product else "",
        "price": str(product.price) if product else "",
        "image": product.image if product else "",
        "slug": product.slug if product else "",
        "is_active": product.is_active if product else True,
    }
    return {
        "message": message,
        "categories": categories,
        "form_data": product_form_data,
    }


async def build_admin_dashboard_context(
    db: AsyncSession,
    *,
    username: str,
    message: str | None = None,
) -> dict:
    categories_result = await db.execute(
        select(Category)
        .options(selectinload(Category.products))
        .order_by(Category.name.asc())
    )
    products_result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .order_by(Product.id.desc())
    )

    return {
        "username": username,
        "categories": categories_result.scalars().all(),
        "products": products_result.scalars().all(),
        "message": message,
    }


def group_products_by_category(
    categories: list[Category],
    products: list[Product],
) -> list[dict]:
    products_by_category: dict[int, list[Product]] = defaultdict(list)
    for product in products:
        products_by_category[product.category_id].append(product)

    return [
        {"category": category, "products": products_by_category[category.id]}
        for category in categories
        if products_by_category[category.id]
    ]


def parse_checkbox(value: str | None) -> bool:
    return value is not None


async def fetch_active_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.name.asc())
    )
    return list(result.scalars().all())


async def fetch_all_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(select(Category).order_by(Category.name.asc()))
    return list(result.scalars().all())


async def require_authenticated_user(
    request: Request,
    db: AsyncSession,
) -> User | RedirectResponse:
    user = await get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return user


async def fetch_category_or_404(db: AsyncSession, category_id: int) -> Category:
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.products))
        .where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    return category


async def fetch_product_or_404(db: AsyncSession, product_id: int) -> Product:
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    return product
