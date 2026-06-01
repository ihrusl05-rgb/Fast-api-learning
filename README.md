# Partner System

Демо-проект партнёрской системы на `FastAPI` с серверным рендерингом через `Jinja2`, асинхронным доступом к БД через `SQLAlchemy Async` и миграциями `Alembic`.

Проект показывает базовый пользовательский поток:
- регистрация пользователя;
- авторизация через сессию;
- дашборд после входа;
- просмотр каталога партнёрских товаров;
- фильтрация по категориям;
- поиск по названию, описанию и `id`;
- постраничная навигация;
- детальная страница предложения.

## Стек

- `FastAPI`
- `Jinja2`
- `SQLAlchemy 2.0 Async`
- `Alembic`
- `Pydantic v2`
- `SQLite` по умолчанию
- `pytest`

## Структура проекта

```text
app/
  api/
    routes.py           # HTTP-роуты и orchestration-логика
  core/
    security.py         # Хеширование и проверка пароля
  database/
    database.py         # Engine, session factory, dependency
    seed.py             # Заполнение демо-данными
  models/
    models.py           # SQLAlchemy модели
  schemas/
    schemas.py          # Pydantic-схемы и валидация
  static/
    css/style.css       # Стили интерфейса
  templates/
    *.html              # Jinja2 шаблоны
alembic/
  versions/             # Миграции
tests/
  conftest.py
  test_routes.py
main.py                 # Инициализация FastAPI приложения
config.py               # Настройки приложения
```

## Быстрый запуск

1. Создать виртуальное окружение и установить зависимости:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Создать `.env` на основе примера:

```bash
cp .env.example .env
```

3. Применить миграции:

```bash
alembic upgrade head
```

4. Заполнить БД демо-данными:

```bash
python -m app.database.seed
```

5. Запустить приложение:

```bash
uvicorn main:app --reload
```

## Переменные окружения

Пример в `.env.example`:

```env
DATABASE_URL=spostgresql+asyncpg://user:password@localhost:5432/partner_db
SECRET_KEY=change-me
SESSION_COOKIE_NAME=partner_session
SESSION_MAX_AGE=28800
SESSION_SAME_SITE=lax
SESSION_HTTPS_ONLY=false
SQL_ECHO=false
```

## Основные маршруты

- `GET /login` — страница входа
- `POST /login` — авторизация
- `GET /registration` — страница регистрации
- `POST /registration` — создание пользователя
- `GET /` — пользовательский дашборд
- `GET /sales` — каталог товаров
- `GET /sales/{product_slug}` — детальная страница оффера
- `GET /logout` — очистка сессии

## Что улучшено в текущей версии

- добавлен аккуратный конфиг для сессий и БД;
- убран deprecated-вызов `TemplateResponse`;
- регистрация теперь нормализует `username` и `email`;
- сообщения об ошибках валидации централизованы;
- при ошибке формы сохраняются введённые пользователем значения;
- на главной странице появился дашборд с метриками;
- в каталоге есть фильтрация, поиск, пагинация и деталка оффера;
- сиды исправлены и расширены, чтобы демонстрировать пагинацию;
- тесты покрывают ключевые сценарии логина и регистрации.

## Тесты

Запуск тестов:

```bash
pytest -q
```

Покрытие:

```bash
coverage run -m pytest
coverage report -m
```

## Дальнейшие шаги

Если развивать проект дальше до более приближённого к продакшену состояния, можно добавить:

- роли пользователя (`admin`, `partner`, `client`);
- CRUD для категорий и товаров через админку;
- отдельный сервисный слой и репозитории;
- flash-сообщения и CSRF-защиту для форм;
- Docker и `docker-compose`;
- PostgreSQL как основную БД;
- CI с автозапуском тестов и линтеров;
- API-слой помимо HTML-интерфейса.
