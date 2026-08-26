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
    assert "91.7%" not in page
    assert "42 units" not in page
