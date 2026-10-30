"""Transactions API + reports tests."""

import datetime as dt

from httpx import AsyncClient

from tests.helpers import auth_headers, create_category, create_transaction


async def test_create_and_list_transaction(client: AsyncClient):
    headers = await auth_headers(client)
    category_id = await create_category(client, headers, name="Еда")

    created = await create_transaction(client, headers, category_id, "123.45", "2026-10-05")
    assert created.status_code == 201
    body = created.json()
    assert float(body["amount"]) == 123.45
    assert body["category"]["name"] == "Еда"
    assert body["kind"] == "expense"  # наследуется от категории
    assert body["currency"] == "RUB"

    listing = await client.get("/api/v1/transactions", headers=headers)
    assert listing.status_code == 200
    page = listing.json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == body["id"]


async def test_transaction_with_foreign_category_rejected(client: AsyncClient):
    alice = await auth_headers(client, email="alice@test.dev", username="alice")
    bob = await auth_headers(client, email="bob@test.dev", username="bob")

    alice_category = await create_category(client, alice, name="Категория Алисы")
    response = await create_transaction(client, bob, alice_category, "10.00", "2026-10-01")
    assert response.status_code == 404


async def test_transaction_list_filters(client: AsyncClient):
    headers = await auth_headers(client)
    food = await create_category(client, headers, name="Еда")
    salary = await create_category(client, headers, name="Аванс", kind="income")

    await create_transaction(client, headers, food, "500.00", "2026-09-10")
    await create_transaction(client, headers, food, "300.00", "2026-10-02")
    await create_transaction(client, headers, salary, "50000.00", "2026-10-05")

    by_kind = await client.get("/api/v1/transactions?kind=income", headers=headers)
    assert by_kind.json()["total"] == 1
    assert by_kind.json()["items"][0]["amount"] != "0"

    by_category = await client.get(f"/api/v1/transactions?category_id={food}", headers=headers)
    assert by_category.json()["total"] == 2

    by_date = await client.get(
        "/api/v1/transactions?date_from=2026-10-01&date_to=2026-10-31", headers=headers
    )
    assert by_date.json()["total"] == 2


async def test_update_and_delete_transaction(client: AsyncClient):
    headers = await auth_headers(client)
    category_id = await create_category(client, headers)
    created = await create_transaction(client, headers, category_id, "100.00", "2026-10-01")
    tx_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"amount": "250.50", "note": "поправил сумму"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert float(updated.json()["amount"]) == 250.50
    assert updated.json()["note"] == "поправил сумму"

    deleted = await client.delete(f"/api/v1/transactions/{tx_id}", headers=headers)
    assert deleted.status_code == 204

    listing = await client.get("/api/v1/transactions", headers=headers)
    assert listing.json()["total"] == 0


async def test_summary_report(client: AsyncClient):
    headers = await auth_headers(client)
    food = await create_category(client, headers, name="Еда")
    salary = await create_category(client, headers, name="Аванс", kind="income")

    await create_transaction(client, headers, food, "1000.00", "2026-10-03")
    await create_transaction(client, headers, food, "500.50", "2026-10-12")
    await create_transaction(client, headers, salary, "5000.00", "2026-10-05")
    # транзакция другого месяца не должна попасть в сводку
    await create_transaction(client, headers, food, "999.00", "2026-09-20")

    response = await client.get("/api/v1/reports/summary?month=2026-10", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert float(body["expense_total"]) == 1500.50
    assert float(body["income_total"]) == 5000.00
    assert float(body["balance"]) == 3499.50
    assert len(body["by_category"]) == 2
    assert body["base_currency"] == "RUB"


async def test_summary_report_converts_usd(client: AsyncClient):
    headers = await auth_headers(client)
    food = await create_category(client, headers, name="Подписки")

    # В fallback-курсах 1 USD = 92 RUB
    await create_transaction(client, headers, food, "10.00", "2026-10-05", currency="USD")

    response = await client.get("/api/v1/reports/summary?month=2026-10", headers=headers)
    assert response.status_code == 200
    assert float(response.json()["expense_total"]) == 920.00


async def test_monthly_series(client: AsyncClient):
    headers = await auth_headers(client)
    food = await create_category(client, headers)
    salary = await create_category(client, headers, name="Аванс", kind="income")

    current = dt.date.today()
    await create_transaction(
        client,
        headers,
        food,
        "700.00",
        current.replace(day=min(5, 28)).isoformat(),
    )
    await create_transaction(
        client,
        headers,
        salary,
        "1000.00",
        current.replace(day=min(5, 28)).isoformat(),
    )

    response = await client.get("/api/v1/reports/monthly?months=3", headers=headers)
    assert response.status_code == 200
    series = response.json()
    assert len(series) == 3
    last = series[-1]
    assert last["month"] == f"{current.year}-{current.month:02d}"
    assert float(last["expense"]) == 700.00
    assert float(last["income"]) == 1000.00


async def test_csv_export(client: AsyncClient):
    headers = await auth_headers(client)
    category_id = await create_category(client, headers, name="Экспорт")
    await create_transaction(client, headers, category_id, "77.70", "2026-10-01")

    response = await client.get("/api/v1/reports/export.csv", headers=headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert "Экспорт" in response.text
    assert response.text.splitlines()[0].startswith("\ufeffdate;category;kind")
