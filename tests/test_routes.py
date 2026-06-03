import pytest
from sqlalchemy.exc import IntegrityError

from app.consumers.kafka_events import decode_message_key, parse_payload
from app.core.security import hash_password, verify_password


pytestmark = pytest.mark.anyio


class StubScalars:
    def __init__(self, values=None):
        self.values = values or []

    def all(self):
        return self.values


class StubResult:
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = values or []

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return StubScalars(self.values)


class StubSession:
    def __init__(self, execute_results=None, scalar_results=None):
        self.execute_results = list(execute_results or [])
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.deleted = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, _query):
        if self.execute_results:
            return self.execute_results.pop(0)
        return StubResult()

    async def scalar(self, _query):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FailingCommitSession(StubSession):
    async def commit(self):
        self.committed = True
        raise IntegrityError("insert into categories", {}, Exception("duplicate key"))


class StubUser:
    def __init__(
        self,
        username,
        hashed_password="",
        email="user@example.com",
        is_active=True,
    ):
        self.username = username
        self.hashed_password = hashed_password
        self.email = email
        self.is_active = is_active


class StubCategory:
    def __init__(
        self,
        category_id=1,
        name="Еда",
        slug="food",
        icon="🍔",
        description="Скидки",
        is_active=True,
        products=None,
    ):
        self.id = category_id
        self.name = name
        self.slug = slug
        self.icon = icon
        self.description = description
        self.is_active = is_active
        self.products = products or []


class StubProduct:
    def __init__(
        self,
        product_id=1,
        category_id=1,
        name="Бургер",
        slug="burger",
        price="100.00",
        description="Вкусно",
        is_active=True,
        category=None,
    ):
        self.id = product_id
        self.category_id = category_id
        self.name = name
        self.slug = slug
        self.price = price
        self.description = description
        self.is_active = is_active
        self.category = category or StubCategory(category_id=category_id)


class StubEventLog:
    def __init__(
        self,
        topic="partner_changes",
        partition=1,
        offset=3,
        action="INSERT",
        table_name="products",
        payload='{"action":"INSERT"}',
        subject="partner_changes.partner_changes",
        created_at="2026-05-30 22:45:00",
    ):
        self.topic = topic
        self.partition = partition
        self.offset = offset
        self.action = action
        self.table_name = table_name
        self.payload = payload
        self.subject = subject
        self.created_at = created_at


async def test_login_page_opens(client):
    response = await client.get("/login")

    assert response.status_code == 200
    assert "Войти" in response.text


async def test_sales_redirects_if_user_not_logged_in(client):
    response = await client.get("/sales", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_admin_redirects_if_user_not_logged_in(client):
    response = await client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_events_redirect_if_user_not_logged_in(client):
    response = await client.get("/events", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_login_with_wrong_data_returns_error(client, override_db):
    override_db(StubSession(execute_results=[StubResult()]))

    response = await client.post(
        "/login",
        data={"username": "user_that_does_not_exist", "password": "wrong_password"},
    )

    assert response.status_code == 400
    assert "Неверное имя пользователя или пароль" in response.text


async def test_login_with_correct_data_redirects_to_index(client, override_db):
    user = StubUser(
        username="test_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    response = await client.post(
        "/login",
        data={"username": "test_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "partner_session=" in response.headers["set-cookie"]


async def test_login_with_inactive_user_returns_error(client, override_db):
    user = StubUser(
        username="blocked_user",
        hashed_password=hash_password("strong_password"),
        is_active=False,
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    response = await client.post(
        "/login",
        data={"username": "blocked_user", "password": "strong_password"},
    )

    assert response.status_code == 400
    assert "Неверное имя пользователя или пароль" in response.text


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {
                "username": "ab",
                "email": "valid@example.com",
                "password": "123456",
            },
            "Username должен быть от 3 до 30 символов.",
        ),
        (
            {
                "username": "valid_user",
                "email": "invalid-email",
                "password": "123456",
            },
            "Введите корректный email.",
        ),
        (
            {
                "username": "valid_user",
                "email": "valid@example.com",
                "password": "123",
            },
            "Пароль должен быть не короче 6 символов.",
        ),
    ],
)
async def test_registration_validation_messages(
    client,
    payload,
    expected_message,
):
    response = await client.post("/registration", data=payload)

    assert response.status_code == 400
    assert expected_message in response.text


async def test_registration_page_opens(client):
    response = await client.get("/registration")

    assert response.status_code == 200
    assert "Создать аккаунт" in response.text


async def test_registration_success_redirects_and_creates_user(client, override_db):
    session = StubSession(execute_results=[StubResult(values=[])])
    override_db(session)

    response = await client.post(
        "/registration",
        data={
            "username": "  valid_user  ",
            "email": "USER@EXAMPLE.COM",
            "password": "123456",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert session.committed is True
    assert len(session.added) == 1
    assert session.added[0].username == "valid_user"
    assert session.added[0].email == "user@example.com"


async def test_registration_duplicate_username_returns_error(client, override_db):
    existing_user = StubUser(username="taken_user", email="other@example.com")
    override_db(StubSession(execute_results=[StubResult(values=[existing_user])]))

    response = await client.post(
        "/registration",
        data={
            "username": "taken_user",
            "email": "new@example.com",
            "password": "123456",
        },
    )

    assert response.status_code == 400
    assert "Пользователь с таким username уже существует" in response.text


async def test_registration_duplicate_email_returns_error(client, override_db):
    existing_user = StubUser(username="other_user", email="taken@example.com")
    override_db(StubSession(execute_results=[StubResult(values=[existing_user])]))

    response = await client.post(
        "/registration",
        data={
            "username": "new_user",
            "email": "taken@example.com",
            "password": "123456",
        },
    )

    assert response.status_code == 400
    assert "Пользователь с таким email уже существует" in response.text


async def test_logout_redirects_user(client):
    response = await client.get("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


async def test_sales_page_shows_products_for_logged_user(client, override_db):
    user = StubUser(
        username="sales_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "sales_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    category = StubCategory(name="Еда", slug="food")
    product = StubProduct(name="Бургер", slug="burger", category=category)
    session = StubSession(
        execute_results=[
            StubResult(value=user),
            StubResult(values=[category]),
            StubResult(values=[product]),
        ],
        scalar_results=[1],
    )
    override_db(session)

    response = await client.get("/sales")

    assert response.status_code == 200
    assert "Витрина партнёрских товаров" in response.text
    assert "Бургер" in response.text
    assert "Еда" in response.text


async def test_offer_detail_returns_404_for_unknown_slug(client, override_db):
    user = StubUser(
        username="detail_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "detail_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    override_db(
        StubSession(
            execute_results=[
                StubResult(value=user),
                StubResult(),
            ]
        )
    )

    response = await client.get("/sales/unknown-offer")

    assert response.status_code == 404


async def test_admin_category_create_redirects_and_saves_category(client, override_db):
    user = StubUser(
        username="admin_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "admin_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    session = StubSession(execute_results=[StubResult(value=user)])
    override_db(session)

    response = await client.post(
        "/admin/categories/new",
        data={
            "name": "Еда",
            "description": "Скидки и промо",
            "icon": "🍔",
            "slug": "food",
            "is_active": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert session.committed is True
    assert len(session.added) == 1
    assert session.added[0].slug == "food"
    assert session.added[0].is_active is True


async def test_admin_category_create_duplicate_slug_returns_validation_error(client, override_db):
    user = StubUser(
        username="admin_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "admin_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    session = FailingCommitSession(execute_results=[StubResult(value=user)])
    override_db(session)

    response = await client.post(
        "/admin/categories/new",
        data={
            "name": "Еда",
            "description": "Скидки и промо",
            "icon": "🍔",
            "slug": "food",
            "is_active": "on",
        },
    )

    assert response.status_code == 400
    assert "Раздел с таким slug уже существует." in response.text
    assert session.rolled_back is True


async def test_admin_product_delete_redirects_and_deletes_product(client, override_db):
    user = StubUser(
        username="admin_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "admin_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    product = StubProduct(product_id=10)
    session = StubSession(
        execute_results=[StubResult(value=user), StubResult(value=product)]
    )
    override_db(session)

    response = await client.post(
        "/admin/products/10/delete",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert session.committed is True
    assert session.deleted == [product]


async def test_admin_category_delete_with_products_returns_error(client, override_db):
    user = StubUser(
        username="admin_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "admin_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    category = StubCategory(category_id=2, products=[StubProduct(product_id=11)])
    dashboard_category = StubCategory(category_id=2, products=[StubProduct(product_id=11)])
    dashboard_product = StubProduct(product_id=11, category=dashboard_category)
    session = StubSession(
        execute_results=[
            StubResult(value=user),
            StubResult(value=category),
            StubResult(values=[dashboard_category]),
            StubResult(values=[dashboard_product]),
        ]
    )
    override_db(session)

    response = await client.post("/admin/categories/2/delete")

    assert response.status_code == 400
    assert "Нельзя удалить раздел, пока в нём есть карточки." in response.text
    assert session.deleted == []


async def test_events_page_shows_saved_event(client, override_db):
    user = StubUser(
        username="event_user",
        hashed_password=hash_password("strong_password"),
    )
    override_db(StubSession(execute_results=[StubResult(value=user)]))

    login_response = await client.post(
        "/login",
        data={"username": "event_user", "password": "strong_password"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303

    event = StubEventLog()
    override_db(
        StubSession(
            execute_results=[StubResult(value=user), StubResult(values=[event])]
        )
    )

    response = await client.get("/events")

    assert response.status_code == 200
    assert "Лента событий изменений" in response.text
    assert "products" in response.text
    assert "partner_changes" in response.text


def test_password_hash_can_be_verified():
    hashed_password = hash_password("strong_password")

    assert hashed_password != "strong_password"
    assert verify_password("strong_password", hashed_password) is True
    assert verify_password("wrong_password", hashed_password) is False


def test_decode_message_key():
    assert decode_message_key(None) is None
    assert decode_message_key(b"partner-key") == "partner-key"


def test_parse_payload_from_json():
    payload, subject, action, table_name = parse_payload(
        b'{"subject":"partner_changes.products","action":"INSERT","table":"products"}'
    )

    assert subject == "partner_changes.products"
    assert action == "INSERT"
    assert table_name == "products"
    assert '"action": "INSERT"' in payload


def test_parse_payload_keeps_plain_text():
    payload, subject, action, table_name = parse_payload(b"not-json")

    assert payload == "not-json"
    assert subject is None
    assert action is None
    assert table_name is None
