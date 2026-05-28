from collections import defaultdict

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.database.database import get_db
from app.models.models import Category, Product, User
from app.schemas.schemas import CategoryUpsert, ProductUpsert, UserCreate

router = APIRouter()
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

    if not user or not user.is_active or not verify_password(
        password,
        user.hashed_password,
    ):
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
        return render_template(
            request,
            "registration.html",
            build_registration_context(
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


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

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

    return render_template(
        request,
        "admin.html",
        {
            "username": user.username,
            "categories": categories_result.scalars().all(),
            "products": products_result.scalars().all(),
        },
    )


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
                "form_action": f"/admin/categories/{category.id}/edit",
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
                "form_action": f"/admin/categories/{category.id}/edit",
                "category": category,
                **build_category_form_context(
                    "Раздел с таким slug уже существует.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/admin/products/new", response_class=HTMLResponse)
async def admin_product_create_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    categories = await fetch_all_categories(db)
    return render_template(
        request,
        "admin_product_form.html",
        {
            "username": user.username,
            "page_title": "Новая карточка",
            "submit_label": "Создать карточку",
            "form_action": "/admin/products/new",
            **build_product_form_context(
                categories,
                message=None
                if categories
                else "Сначала создайте хотя бы один раздел для привязки карточки.",
            ),
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
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Новая карточка",
                "submit_label": "Создать карточку",
                "form_action": "/admin/products/new",
                **build_product_form_context(
                    categories,
                    "Сначала создайте хотя бы один раздел для привязки карточки.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    try:
        product_data = ProductUpsert(**raw_form_data)
    except ValidationError as exc:
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Новая карточка",
                "submit_label": "Создать карточку",
                "form_action": "/admin/products/new",
                **build_product_form_context(
                    categories,
                    format_validation_error(exc, PRODUCT_ERROR_MESSAGES),
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    category = await db.get(Category, product_data.category_id)
    if category is None:
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Новая карточка",
                "submit_label": "Создать карточку",
                "form_action": "/admin/products/new",
                **build_product_form_context(
                    categories,
                    "Выбранный раздел не найден.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    db.add(Product(**product_data.model_dump()))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Новая карточка",
                "submit_label": "Создать карточку",
                "form_action": "/admin/products/new",
                **build_product_form_context(
                    categories,
                    "Карточка с таким slug уже существует.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
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
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Редактирование карточки",
                "submit_label": "Сохранить карточку",
                "form_action": f"/admin/products/{product.id}/edit",
                "product": product,
                **build_product_form_context(
                    categories,
                    format_validation_error(exc, PRODUCT_ERROR_MESSAGES),
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    category = await db.get(Category, product_data.category_id)
    if category is None:
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Редактирование карточки",
                "submit_label": "Сохранить карточку",
                "form_action": f"/admin/products/{product.id}/edit",
                "product": product,
                **build_product_form_context(
                    categories,
                    "Выбранный раздел не найден.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    for field_name, value in product_data.model_dump().items():
        setattr(product, field_name, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return render_template(
            request,
            "admin_product_form.html",
            {
                "username": user.username,
                "page_title": "Редактирование карточки",
                "submit_label": "Сохранить карточку",
                "form_action": f"/admin/products/{product.id}/edit",
                "product": product,
                **build_product_form_context(
                    categories,
                    "Карточка с таким slug уже существует.",
                    form_data=raw_form_data,
                ),
            },
            status_code=400,
        )

    return RedirectResponse(url="/admin", status_code=303)
