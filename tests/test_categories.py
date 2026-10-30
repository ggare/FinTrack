"""Categories API tests."""

from httpx import AsyncClient

from tests.helpers import auth_headers


async def test_create_category(client: AsyncClient):
    headers = await auth_headers(client)
    response = await client.post(
        "/api/v1/categories",
        json={"name": "Кофе с собой", "kind": "expense", "color": "#8b5cf6"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Кофе с собой"
    assert body["kind"] == "expense"
    assert body["color"] == "#8b5cf6"
    assert body["id"] > 0


async def test_duplicate_category_name_conflict(client: AsyncClient):
    headers = await auth_headers(client)
    payload = {"name": "Дубликат", "kind": "expense"}
    first = await client.post("/api/v1/categories", json=payload, headers=headers)
    second = await client.post("/api/v1/categories", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 409


async def test_update_and_delete_category(client: AsyncClient):
    headers = await auth_headers(client)
    created = await client.post(
        "/api/v1/categories", json={"name": "Старое имя", "kind": "expense"}, headers=headers
    )
    category_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/categories/{category_id}",
        json={"name": "Новое имя", "color": "#ff0000"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Новое имя"
    assert updated.json()["color"] == "#ff0000"

    deleted = await client.delete(f"/api/v1/categories/{category_id}", headers=headers)
    assert deleted.status_code == 204

    listing = await client.get("/api/v1/categories", headers=headers)
    names = {c["name"] for c in listing.json()}
    assert "Новое имя" not in names


async def test_categories_are_isolated_between_users(client: AsyncClient):
    alice = await auth_headers(client, email="alice@test.dev", username="alice")
    bob = await auth_headers(client, email="bob@test.dev", username="bob")

    created = await client.post(
        "/api/v1/categories", json={"name": "Личное Алисы", "kind": "expense"}, headers=alice
    )
    category_id = created.json()["id"]

    # Боб не видит и не может изменить категорию Алисы
    bob_list = await client.get("/api/v1/categories", headers=bob)
    assert "Личное Алисы" not in {c["name"] for c in bob_list.json()}

    patched = await client.patch(
        f"/api/v1/categories/{category_id}", json={"name": "Взломано"}, headers=bob
    )
    assert patched.status_code == 404

    deleted = await client.delete(f"/api/v1/categories/{category_id}", headers=bob)
    assert deleted.status_code == 404


async def test_delete_category_with_transactions_requires_force(client: AsyncClient):
    headers = await auth_headers(client)
    created = await client.post(
        "/api/v1/categories", json={"name": "Напитки", "kind": "expense"}, headers=headers
    )
    category_id = created.json()["id"]
    await client.post(
        "/api/v1/transactions",
        json={"category_id": category_id, "amount": "100.00"},
        headers=headers,
    )

    blocked = await client.delete(f"/api/v1/categories/{category_id}", headers=headers)
    assert blocked.status_code == 400

    forced = await client.delete(f"/api/v1/categories/{category_id}?force=true", headers=headers)
    assert forced.status_code == 204

    listing = await client.get("/api/v1/categories", headers=headers)
    assert "Напитки" not in {c["name"] for c in listing.json()}
