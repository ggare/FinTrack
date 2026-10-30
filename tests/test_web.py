"""Web UI tests: pages, cookie authentication, HTMX endpoints."""

from httpx import AsyncClient


async def _web_register(client: AsyncClient, email="webby@test.dev", username="webby"):
    return await client.post(
        "/register",
        data={"username": username, "email": email, "password": "password123"},
        follow_redirects=False,
    )


async def test_login_page_renders(client: AsyncClient):
    response = await client.get("/login")
    assert response.status_code == 200
    assert "FinTrack" in response.text
    assert "demo@fintrack.dev" in response.text


async def test_index_redirects(client: AsyncClient):
    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


async def test_dashboard_requires_auth(client: AsyncClient):
    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


async def test_web_register_login_logout_flow(client: AsyncClient):
    registered = await _web_register(client)
    assert registered.status_code == 303
    assert "access_token" in registered.cookies

    dashboard = await client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Financial overview" in dashboard.text

    logout = await client.get("/logout", follow_redirects=False)
    assert logout.status_code == 303

    after_logout = await client.get("/dashboard", follow_redirects=False)
    assert after_logout.status_code == 307


async def test_web_login_wrong_password(client: AsyncClient):
    await _web_register(client)
    response = await client.post(
        "/login", data={"email": "webby@test.dev", "password": "wrong-password"}
    )
    assert response.status_code == 400
    assert "Invalid email or password" in response.text


async def test_htmx_add_transaction_returns_row(client: AsyncClient):
    await _web_register(client)

    # The web-registration cookie also works in the API (shared auth mechanism)
    created = await client.post("/api/v1/categories", json={"name": "HTMX test", "kind": "expense"})
    assert created.status_code == 201
    category_id = created.json()["id"]

    response = await client.post(
        "/transactions",
        data={
            "category_id": str(category_id),
            "amount": "42.50",
            "currency": "RUB",
            "happened_at": "",
            "note": "from HTMX",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert response.text.strip().startswith("<tr")
    assert "HTMX test" in response.text


async def test_web_delete_transaction(client: AsyncClient):
    await _web_register(client, email="deleter@test.dev", username="deleter")
    created = await client.post("/api/v1/categories", json={"name": "Deletable", "kind": "expense"})
    category_id = created.json()["id"]
    tx = await client.post(
        "/api/v1/transactions",
        json={"category_id": category_id, "amount": "10.00"},
    )
    tx_id = tx.json()["id"]

    response = await client.delete(f"/transactions/{tx_id}")
    assert response.status_code == 200

    listing = await client.get("/api/v1/transactions")
    assert listing.json()["total"] == 0


async def test_transactions_and_budgets_pages_render(client: AsyncClient):
    await _web_register(client, email="pages@test.dev", username="pages")
    created = await client.post("/api/v1/categories", json={"name": "Render", "kind": "expense"})
    category_id = created.json()["id"]
    await client.post("/api/v1/transactions", json={"category_id": category_id, "amount": "150.00"})
    await client.put(f"/api/v1/budgets/{category_id}", json={"monthly_limit": "5000"})

    transactions_page = await client.get("/transactions")
    assert transactions_page.status_code == 200
    assert "Render" in transactions_page.text
    assert "150.00" in transactions_page.text

    budgets_page = await client.get("/budgets")
    assert budgets_page.status_code == 200
    assert "Budgets" in budgets_page.text
    assert "5,000.00" in budgets_page.text

    dashboard = await client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "chart-box" in dashboard.text
