"""Shared helpers for tests."""

from httpx import AsyncClient


async def api_register(
    client: AsyncClient,
    email: str = "user@test.dev",
    username: str = "user1",
    password: str = "password123",
):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )


async def api_login(
    client: AsyncClient,
    email: str = "user@test.dev",
    password: str = "password123",
):
    return await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


async def auth_headers(
    client: AsyncClient,
    email: str = "user@test.dev",
    username: str = "user1",
    password: str = "password123",
) -> dict:
    await api_register(client, email, username, password)  # a 409 on repeat is fine
    response = await api_login(client, email, password)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_category(
    client: AsyncClient,
    headers: dict,
    name: str = "Food",
    kind: str = "expense",
) -> int:
    response = await client.post(
        "/api/v1/categories",
        json={"name": name, "kind": kind},
        headers=headers,
    )
    return response.json()["id"]


async def create_transaction(
    client: AsyncClient,
    headers: dict,
    category_id: int,
    amount: str,
    happened_at: str,
    currency: str = "RUB",
):
    return await client.post(
        "/api/v1/transactions",
        json={
            "category_id": category_id,
            "amount": amount,
            "currency": currency,
            "happened_at": happened_at,
        },
        headers=headers,
    )
