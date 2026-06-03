from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_categories import router as categories_router
from app.api.admin_products import router as products_router
from app.api.common import (
    build_admin_dashboard_context,
    render_template,
    require_authenticated_user,
)
from app.database.database import get_db
from app.models.models import EventLog

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    return render_template(
        request,
        "admin.html",
        await build_admin_dashboard_context(db, username=user.username),
    )


@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_authenticated_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    events_result = await db.execute(
        select(EventLog)
        .order_by(EventLog.id.desc())
        .limit(50)
    )
    events = list(events_result.scalars().all())

    return render_template(
        request,
        "events.html",
        {
            "username": user.username,
            "events": events,
            "events_count": len(events),
        },
    )


router.include_router(categories_router)
router.include_router(products_router)
