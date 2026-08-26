def test_root_redirects_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_page_contains_real_auth_form_and_shared_assets(client):
    response = client.get("/login")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-auth-form="login"' in page
    assert 'name="email"' in page
    assert 'name="password"' in page
    assert "/static/css/main.css" in page
    assert "/static/js/api.js" in page
    assert "/static/js/auth.js" in page


def test_register_page_fields_match_backend_contract(client):
    response = client.get("/register")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-auth-form="register"' in page
    for field in ("business_name", "name", "email", "password"):
        assert f'name="{field}"' in page
    assert 'name="business_id"' not in page


def test_dashboard_serves_authenticated_shell_without_fake_data(client):
    response = client.get("/dashboard")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="app-sidebar"' in page
    assert "Stock Intelligence" in page
    assert "Anomalies" in page
    assert "Analytics" in page
    assert 'data-logout' in page
    assert "/static/js/app.js" in page
    assert "/static/js/charts.js" in page
    assert "/static/js/dashboard.js" in page
    assert "data-dashboard-metrics" in page
    assert "data-dashboard-sales" in page
    assert "data-dashboard-forecast" in page
    assert "Dashboard analytics arrive in a later frontend pass" not in page
    assert "Forecast Accuracy" not in page
    assert "91.7%" not in page
    assert "42 units" not in page


def test_operational_frontend_pages_render_with_shared_authenticated_shell(client):
    pages = {
        "/uploads": ("data-upload-form", "/static/js/uploads.js"),
        "/forecasts": ("data-forecast-form", "/static/js/forecasts.js"),
        "/inventory": ("data-inventory-form", "/static/js/inventory.js"),
        "/stock-intelligence": ("data-stock-form", "/static/js/stock_intelligence.js"),
        "/anomalies": ("data-anomaly-form", "/static/js/anomalies.js"),
    }

    for path, (marker, script) in pages.items():
        response = client.get(path)
        page = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'id="app-sidebar"' in page
        assert "data-page-content" in page
        assert marker in page
        assert script in page
        assert "/static/js/app.js" in page
        assert "/static/js/workspace.js" in page
        assert "91.7%" not in page


def test_operational_navigation_links_to_real_pages(client):
    page = client.get("/uploads").get_data(as_text=True)

    for path in (
        "/uploads",
        "/forecasts",
        "/inventory",
        "/stock-intelligence",
        "/anomalies",
        "/analytics",
    ):
        assert f'href="{path}"' in page

    assert 'data-unavailable-view="Analytics"' not in page


def test_analytics_page_renders_filters_charts_and_active_navigation(client):
    response = client.get("/analytics")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-analytics-upload' in page
    assert 'data-analytics-family' in page
    assert 'data-analytics-forecast-select' in page
    assert 'data-analytics-sales' in page
    assert 'data-analytics-categories' in page
    assert 'data-analytics-stock' in page
    assert 'data-analytics-anomalies' in page
    assert "/static/js/charts.js" in page
    assert "/static/js/analytics.js" in page
    assert 'href="/analytics" aria-current="page"' in page
    assert "Forecast Accuracy" not in page
    assert "revenue" not in page.lower()


def test_chart_pages_pin_chartjs_without_frontend_build_tooling(client):
    for path in ("/dashboard", "/analytics"):
        page = client.get(path).get_data(as_text=True)

        assert "chart.js@4.4.7" in page
        assert "node_modules" not in page


def test_upload_page_documents_the_real_csv_contract(client):
    page = client.get("/uploads").get_data(as_text=True)

    for column in ("date", "family", "sales", "onpromotion"):
        assert f"<code>{column}</code>" in page
    assert "Maximum 10 MB" in page


def test_operational_pages_include_important_interpretation_limits(client):
    forecast_page = client.get("/forecasts").get_data(as_text=True)
    stock_page = client.get("/stock-intelligence").get_data(as_text=True)
    anomaly_page = client.get("/anomalies").get_data(as_text=True)

    assert "does not represent measured horizon accuracy" in forecast_page
    assert "prototype overstock rule" in stock_page
    assert "do not establish a cause" in anomaly_page
