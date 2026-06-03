from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import (
    CATEGORY_ERROR_MESSAGES,
    build_admin_dashboard_context,
    build_category_form_context,
    fetch_category_or_404,
    format_validation_error,
    parse_checkbox,
    render_template,
    require_authenticated_user,
)
from app.database.database import get_db
from app.models.models import Category
from app.schemas.schemas import CategoryUpsert

router = APIRouter()


@router.get("/admin/categories/new", response_class=HTMLResponse)
async def admin_category_create_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    return render_template(
        request,
        "admin_category_form.html",
        {
            "username": user.username,
            "page_title": "Новый раздел",
            "submit_label": "Создать раздел",
            "form_action": "/admin/categories/new",
            **build_category_form_context(),
        },
    )


@router.post("/admin/categories/new", response_class=HTMLResponse)
async def admin_category_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    icon: str = Form(...),
    slug: str = Form(...),
    is_active: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    raw_form_data = {
        "name": name,
        "description": description,
        "icon": icon,
        "slug": slug,
        "is_active": parse_checkbox(is_active),
    }

    try:
        category_data = CategoryUpsert(**raw_form_data)
    except ValidationError as exc:
        return render_template(
            request,
            "admin_category_form.html",
            {
                "username": user.username,
                "page_title": "Новый раздел",
                "submit_label": "Создать раздел",
                "form_action": "/admin/categories/new",
                **build_category_form_context(
                    format_validation_error(exc, CATEGORY_ERROR_MESSAGES),
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    db.add(Category(**category_data.model_dump()))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return render_template(
            request,
            "admin_category_form.html",
            {
                "username": user.username,
                "page_title": "Новый раздел",
                "submit_label": "Создать раздел",
                "form_action": "/admin/categories/new",
                **build_category_form_context(
                    "Раздел с таким slug уже существует.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/categories/{category_id}/edit", response_class=HTMLResponse)
async def admin_category_edit_page(
    request: Request,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    category = await fetch_category_or_404(db, category_id)

    return render_template(
        request,
        "admin_category_form.html",
        {
            "username": user.username,
            "page_title": "Редактирование раздела",
            "submit_label": "Сохранить раздел",
            "form_action": f"/admin/categories/{category.id}/edit",
            "category": category,
            **build_category_form_context(category=category),
        },
    )


@router.post("/admin/categories/{category_id}/edit", response_class=HTMLResponse)
async def admin_category_edit(
    request: Request,
    category_id: int,
    name: str = Form(...),
    description: str = Form(""),
    icon: str = Form(...),
    slug: str = Form(...),
    is_active: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    category = await fetch_category_or_404(db, category_id)
    form_action = f"/admin/categories/{category.id}/edit"
    raw_form_data = {
        "name": name,
        "description": description,
        "icon": icon,
        "slug": slug,
        "is_active": parse_checkbox(is_active),
    }

    try:
        category_data = CategoryUpsert(**raw_form_data)
    except ValidationError as exc:
        return render_template(
            request,
            "admin_category_form.html",
            {
                "username": user.username,
                "page_title": "Редактирование раздела",
                "submit_label": "Сохранить раздел",
                "form_action": form_action,
                "category": category,
                **build_category_form_context(
                    format_validation_error(exc, CATEGORY_ERROR_MESSAGES),
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    for field_name, value in category_data.model_dump().items():
        setattr(category, field_name, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return render_template(
            request,
            "admin_category_form.html",
            {
                "username": user.username,
                "page_title": "Редактирование раздела",
                "submit_label": "Сохранить раздел",
                "form_action": form_action,
                **build_category_form_context(
                    "Раздел с таким slug уже существует.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/categories/{category_id}/delete", response_class=HTMLResponse)
async def admin_category_delete(
    request: Request,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    category = await fetch_category_or_404(db, category_id)
    if category.products:
        return render_template(
            request,
            "admin.html",
            await build_admin_dashboard_context(
                db,
                username=user.username,
                message="Нельзя удалить раздел, пока в нём есть карточки.",
            ),
            status_code=400,
        )

    await db.delete(category)
    await db.commit()
    return RedirectResponse(url="/admin", status_code=303)
