"""Auth API tests."""

from httpx import AsyncClient

from tests.helpers import api_login, api_register, auth_headers


async def test_register_login_me_flow(client: AsyncClient):
    registered = await api_register(client)
    assert registered.status_code == 201
    body = registered.json()
    assert body["email"] == "user@test.dev"
    assert "password" not in body
    assert "hashed_password" not in body

    login = await api_login(client)
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@test.dev"


async def test_register_creates_default_categories(client: AsyncClient):
    headers = await auth_headers(client)
    response = await client.get("/api/v1/categories", headers=headers)
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert "Продукты" in names
    assert "Зарплата" in names
    assert len(response.json()) == 8


async def test_register_duplicate_email(client: AsyncClient):
    await api_register(client)
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@test.dev", "username": "other", "password": "password123"},
    )
    assert response.status_code == 409


async def test_register_weak_password_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@test.dev", "username": "weakling", "password": "123"},
    )
    assert response.status_code == 422


async def test_login_wrong_password(client: AsyncClient):
    await api_register(client)
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@test.dev", "password": "totally-wrong"},
    )
    assert response.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "ghost@test.dev", "password": "password123"},
    )
    assert response.status_code == 401


async def test_me_requires_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_garbage_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["components"]["database"] == "ok"
    assert body["components"]["redis"] == "ok"  # fakeredis
