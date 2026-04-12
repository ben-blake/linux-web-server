def test_login_page_loads(client):
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b'Login' in resp.data


def test_login_with_valid_credentials(client):
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data


def test_login_with_invalid_credentials(client):
    resp = client.post('/login', data={'username': 'admin', 'password': 'wrong'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Invalid' in resp.data


def test_logout(admin_client):
    resp = admin_client.get('/logout', follow_redirects=True)
    assert b'Login' in resp.data


def test_protected_route_redirects_when_not_logged_in(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_login_with_empty_username(client):
    resp = client.post('/login', data={'username': '', 'password': 'admin'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'required' in resp.data


def test_login_with_empty_password(client):
    resp = client.post('/login', data={'username': 'admin', 'password': ''}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'required' in resp.data


def test_login_with_whitespace_username(client):
    resp = client.post('/login', data={'username': '   ', 'password': 'admin'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'required' in resp.data
