"""Budgets API tests."""

import datetime as dt

from httpx import AsyncClient

from tests.helpers import auth_headers, create_category, create_transaction


async def test_set_budget_and_check_progress(client: AsyncClient):
    headers = await auth_headers(client)
    food = await create_category(client, headers, name="Еда")

    today = dt.date.today()
    await create_transaction(
        client, headers, food, "3000.00", today.replace(day=min(3, 28)).isoformat()
    )

    created = await client.put(
        f"/api/v1/budgets/{food}", json={"monthly_limit": "10000"}, headers=headers
    )
    assert created.status_code == 200
    body = created.json()
    assert float(body["monthly_limit"]) == 10000.0
    assert float(body["spent"]) == 3000.0
    assert float(body["remaining"]) == 7000.0
    assert body["percent"] == 30.0
    assert body["category"]["name"] == "Еда"


async def test_budget_upsert_and_delete(client: AsyncClient):
    headers = await auth_headers(client)
    food = await create_category(client, headers, name="Кафе")

    first = await client.put(
        f"/api/v1/budgets/{food}", json={"monthly_limit": "5000"}, headers=headers
    )
    assert first.status_code == 200

    second = await client.put(
        f"/api/v1/budgets/{food}", json={"monthly_limit": "7500"}, headers=headers
    )
    assert second.status_code == 200
    assert float(second.json()["monthly_limit"]) == 7500.0

    listing = await client.get("/api/v1/budgets", headers=headers)
    assert len(listing.json()) == 1  # upsert, не дубль

    deleted = await client.delete(f"/api/v1/budgets/{food}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/budgets", headers=headers)).json() == []


async def test_budget_only_for_expense_category(client: AsyncClient):
    headers = await auth_headers(client)
    salary = await create_category(client, headers, name="Фриланс", kind="income")

    response = await client.put(
        f"/api/v1/budgets/{salary}", json={"monthly_limit": "1000"}, headers=headers
    )
    assert response.status_code == 400


async def test_budget_unknown_category(client: AsyncClient):
    headers = await auth_headers(client)
    response = await client.put(
        "/api/v1/budgets/99999", json={"monthly_limit": "1000"}, headers=headers
    )
    assert response.status_code == 404
