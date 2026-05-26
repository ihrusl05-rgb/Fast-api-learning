import pytest

from app.core.security import hash_password


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
        self.committed = False

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

    async def commit(self):
        self.committed = True


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


async def test_login_page_opens(client):
    response = await client.get("/login")

    assert response.status_code == 200
    assert "Войти" in response.text


async def test_sales_redirects_if_user_not_logged_in(client):
    response = await client.get("/sales", follow_redirects=False)

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


async def test_logout_redirects_user(client):
    response = await client.get("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
