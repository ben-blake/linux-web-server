def test_admin_can_view_user_list(admin_client):
    resp = admin_client.get('/users/')
    assert resp.status_code == 200
    assert b'admin' in resp.data


def test_regular_user_cannot_view_user_list(user_client):
    resp = user_client.get('/users/')
    assert resp.status_code == 403


def test_admin_can_create_user(admin_client):
    resp = admin_client.post('/users/create', data={
        'username': 'newuser',
        'password': 'newpass',
        'role': 'user',
        'permissions': 'read,write'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'newuser' in resp.data


def test_admin_can_edit_user(admin_client):
    admin_client.post('/users/create', data={
        'username': 'editme',
        'password': 'pass',
        'role': 'user',
        'permissions': 'read'
    })
    from database import get_db
    db = get_db()
    user = db.execute('SELECT id FROM users WHERE username = ?', ('editme',)).fetchone()
    db.close()

    resp = admin_client.post(f'/users/{user["id"]}/edit', data={
        'role': 'admin',
        'permissions': 'read,write,edit,admin'
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_admin_can_delete_user(admin_client):
    admin_client.post('/users/create', data={
        'username': 'deleteme',
        'password': 'pass',
        'role': 'user',
        'permissions': 'read'
    })
    from database import get_db
    db = get_db()
    user = db.execute('SELECT id FROM users WHERE username = ?', ('deleteme',)).fetchone()
    db.close()

    resp = admin_client.post(f'/users/{user["id"]}/delete', follow_redirects=True)
    assert resp.status_code == 200
    assert b'User deleted.' in resp.data

    # Verify user is actually gone from the database
    db = get_db()
    deleted = db.execute('SELECT id FROM users WHERE username = ?', ('deleteme',)).fetchone()
    db.close()
    assert deleted is None


def test_user_can_change_own_password(user_client):
    resp = user_client.post('/users/profile', data={
        'current_password': 'testpass',
        'new_password': 'newpassword'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'updated' in resp.data.lower()
