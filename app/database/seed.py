import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.database.database import engine, new_session
from app.models.models import Category, Product


async def seed_data() -> None:
    async with new_session() as session:
        existing_category = await session.scalar(select(Category.id).limit(1))
        if existing_category is not None:
            return

        categories = [
            Category(
                name="Еда",
                description="Скидки на доставку, наборы и комбо-предложения.",
                slug="food",
                icon="🍔",
            ),
            Category(
                name="Красота",
                description="Промо на услуги салонов, студий и онлайн-запись.",
                slug="beauty",
                icon="💄",
            ),
            Category(
                name="Спорт",
                description="Абонементы, персональные занятия и wellness-услуги.",
                slug="sport",
                icon="🏋️",
            ),
        ]
        session.add_all(categories)
        await session.flush()

        products = [
            Product(
                category_id=categories[0].id,
                name="Сет роллов",
                description="Скидка 20% на большой сет роллов по промокоду.",
                price=Decimal("1290.00"),
                slug="roll-set",
            ),
            Product(
                category_id=categories[0].id,
                name="Бургер-комбо",
                description="Комбо с напитком и картофелем по специальной цене.",
                price=Decimal("490.00"),
                slug="burger-combo",
            ),
            Product(
                category_id=categories[0].id,
                name="Семейная пицца",
                description="Большая пицца и напиток по партнёрской цене.",
                price=Decimal("890.00"),
                slug="family-pizza",
            ),
            Product(
                category_id=categories[1].id,
                name="Маникюр с покрытием",
                description="Скидка для новых клиентов на первое посещение.",
                price=Decimal("1500.00"),
                slug="manicure",
            ),
            Product(
                category_id=categories[1].id,
                name="Уход за волосами",
                description="Комплексный уход и укладка со скидкой 15%.",
                price=Decimal("2200.00"),
                slug="hair-care",
            ),
            Product(
                category_id=categories[1].id,
                name="SPA-программа",
                description="Расслабляющий уход для постоянных клиентов партнёра.",
                price=Decimal("3100.00"),
                slug="spa-program",
            ),
            Product(
                category_id=categories[2].id,
                name="Абонемент в зал",
                description="Месячный доступ в фитнес-клуб по акционной цене.",
                price=Decimal("2990.00"),
                slug="gym-pass",
            ),
            Product(
                category_id=categories[2].id,
                name="Персональная тренировка",
                description="Первая тренировка с персональным тренером дешевле.",
                price=Decimal("1800.00"),
                slug="personal-training",
            ),
            Product(
                category_id=categories[2].id,
                name="Йога-утро",
                description="Пробное занятие в студии с welcome-скидкой 25%.",
                price=Decimal("990.00"),
                slug="yoga-morning",
            ),
        ]
        session.add_all(products)
        await session.commit()


async def main() -> None:
    try:
        await seed_data()
        print("Seed completed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
