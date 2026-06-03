# Партнерская система

Учебный проект партнёрской системы на `FastAPI`.

В приложении есть регистрация, вход через сессию, каталог предложений,
простая админка для разделов и карточек, а также страница с событиями из Kafka.
HTML рендерится через `Jinja2`, данные хранятся в PostgreSQL, миграции ведутся через
`Alembic`.

## Стек

- `FastAPI`
- `Jinja2`
- `SQLAlchemy 2.0`
- `Alembic`
- `Pydantic v2`
- `PostgreSQL`
- `Kafka`
- `pytest`

## Структура проекта

```text
app/
  api/
    routes.py          
    public.py         
    admin.py            
    admin_categories.py 
    admin_products.py   
    common.py           
  consumers/
    kafka_events.py    
  core/
    security.py         
  database/
    database.py         
    seed.py             
  models/
    models.py           
  schemas/
    schemas.py          
  static/
    css/style.css
  templates/
    *.html
alembic/
  versions/
tests/
main.py
config.py
docker-compose.yml
```

## Запуск через Docker

1. Создать `.env`:

```bash
cp .env.example .env
```

2. Запустить контейнеры:

```bash
docker compose up --build
```

3. Применить миграции:

```bash
docker compose exec app alembic upgrade head
```

4. Заполнить базу демо-данными:

```bash
docker compose exec app python -m app.database.seed
```

Приложение будет доступно на `http://127.0.0.1:8000`.
Kafka UI будет доступен на `http://127.0.0.1:8080`.

## Локальный запуск без Docker

Нужна запущенная PostgreSQL-база. Для базы из `docker-compose.yml` с хоста
используется порт `5433`.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.database.seed
uvicorn main:app --reload
```

## Переменные окружения

Основные переменные находятся в `.env.example`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/partner_db
POSTGRES_DB=partner_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
SECRET_KEY=change-me
SESSION_COOKIE_NAME=partner_session
SESSION_MAX_AGE=28800
SESSION_SAME_SITE=lax
SESSION_HTTPS_ONLY=false
SQL_ECHO=false
```

## Основные страницы

- `GET /login` - вход
- `GET /registration` - регистрация
- `GET /` - главная после входа
- `GET /sales` - каталог предложений
- `GET /sales/{product_slug}` - детальная страница предложения
- `GET /admin` - админка
- `GET /events` - последние события из Kafka
- `GET /logout` - выход

## Тесты

```bash
pytest -q
```

С покрытием:

```bash
coverage run -m pytest
coverage report -m

Покрытие 83%

```
