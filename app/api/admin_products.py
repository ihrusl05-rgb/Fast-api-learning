from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import (
    PRODUCT_ERROR_MESSAGES,
    build_product_form_context,
    fetch_all_categories,
    fetch_product_or_404,
    format_validation_error,
    parse_checkbox,
    render_template,
    require_authenticated_user,
)
from app.database.database import get_db
from app.models.models import Category, Product
from app.schemas.schemas import ProductUpsert

router = APIRouter()


@router.get("/admin/products/new", response_class=HTMLResponse)
async def admin_product_create_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    categories = await fetch_all_categories(db)
    message = None
    if not categories:
        message = "Сначала создайте хотя бы один раздел для привязки карточки."

    return render_template(
        request,
        "admin_product_form.html",
        {
            "username": user.username,
            "page_title": "Новая карточка",
            "submit_label": "Создать карточку",
            "form_action": "/admin/products/new",
            **build_product_form_context(categories, message=message),
        },
    )


@router.post("/admin/products/new", response_class=HTMLResponse)
async def admin_product_create(
    request: Request,
    category_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    price: str = Form(...),
    image: str = Form(""),
    slug: str = Form(...),
    is_active: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    categories = await fetch_all_categories(db)
    raw_form_data = {
        "category_id": category_id,
        "name": name,
        "description": description,
        "price": price,
        "image": image,
        "slug": slug,
        "is_active": parse_checkbox(is_active),
    }

    if not categories:
        return render_product_form_error(
            request,
            user.username,
            "Новая карточка",
            "Создать карточку",
            "/admin/products/new",
            categories,
            "Сначала создайте хотя бы один раздел для привязки карточки.",
            raw_form_data,
        )

    try:
        product_data = ProductUpsert(**raw_form_data)
    except ValidationError as exc:
        return render_product_form_error(
            request,
            user.username,
            "Новая карточка",
            "Создать карточку",
            "/admin/products/new",
            categories,
            format_validation_error(exc, PRODUCT_ERROR_MESSAGES),
            raw_form_data,
        )

    category = await db.get(Category, product_data.category_id)
    if category is None:
        return render_product_form_error(
            request,
            user.username,
            "Новая карточка",
            "Создать карточку",
            "/admin/products/new",
            categories,
            "Выбранный раздел не найден.",
            raw_form_data,
        )

    db.add(Product(**product_data.model_dump()))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return render_product_form_error(
            request,
            user.username,
            "Новая карточка",
            "Создать карточку",
            "/admin/products/new",
            categories,
            "Карточка с таким slug уже существует.",
            raw_form_data,
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/products/{product_id}/edit", response_class=HTMLResponse)
async def admin_product_edit_page(
    request: Request,
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    product = await fetch_product_or_404(db, product_id)
    categories = await fetch_all_categories(db)

    return render_template(
        request,
        "admin_product_form.html",
        {
            "username": user.username,
            "page_title": "Редактирование карточки",
            "submit_label": "Сохранить карточку",
            "form_action": f"/admin/products/{product.id}/edit",
            "product": product,
            **build_product_form_context(categories, product=product),
        },
    )


@router.post("/admin/products/{product_id}/edit", response_class=HTMLResponse)
async def admin_product_edit(
    request: Request,
    product_id: int,
    category_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    price: str = Form(...),
    image: str = Form(""),
    slug: str = Form(...),
    is_active: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    product = await fetch_product_or_404(db, product_id)
    categories = await fetch_all_categories(db)
    form_action = f"/admin/products/{product.id}/edit"
    raw_form_data = {
        "category_id": category_id,
        "name": name,
        "description": description,
        "price": price,
        "image": image,
        "slug": slug,
        "is_active": parse_checkbox(is_active),
    }

    try:
        product_data = ProductUpsert(**raw_form_data)
    except ValidationError as exc:
        return render_product_form_error(
            request,
            user.username,
            "Редактирование карточки",
            "Сохранить карточку",
            form_action,
            categories,
            format_validation_error(exc, PRODUCT_ERROR_MESSAGES),
            raw_form_data,
            product=product,
        )

    category = await db.get(Category, product_data.category_id)
    if category is None:
        return render_product_form_error(
            request,
            user.username,
            "Редактирование карточки",
            "Сохранить карточку",
            form_action,
            categories,
            "Выбранный раздел не найден.",
            raw_form_data,
            product=product,
        )

    for field_name, value in product_data.model_dump().items():
        setattr(product, field_name, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return render_product_form_error(
            request,
            user.username,
            "Редактирование карточки",
            "Сохранить карточку",
            form_action,
            categories,
            "Карточка с таким slug уже существует.",
            raw_form_data,
            product=product,
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/products/{product_id}/delete", response_class=HTMLResponse)
async def admin_product_delete(
    request: Request,
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    product = await fetch_product_or_404(db, product_id)
    await db.delete(product)
    await db.commit()
    return RedirectResponse(url="/admin", status_code=303)


def render_product_form_error(
    request: Request,
    username: str,
    page_title: str,
    submit_label: str,
    form_action: str,
    categories: list[Category],
    message: str,
    form_data: dict,
    *,
    product: Product | None = None,
) -> HTMLResponse:
    return render_template(
        request,
        "admin_product_form.html",
        {
            "username": username,
            "page_title": page_title,
            "submit_label": submit_label,
            "form_action": form_action,
            "product": product,
            **build_product_form_context(
                categories,
                message,
                form_data=form_data,
            ),
        },
        status_code=400,
    )
