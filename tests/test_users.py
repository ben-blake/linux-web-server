import os

import config


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


def test_delete_user_nullifies_file_ownership(admin_client, app):
    """Deleting a user sets uploaded_by to NULL on their files rather than leaving a dangling FK."""
    admin_client.post('/users/create', data={
        'username': 'uploader',
        'password': 'pass',
        'role': 'user',
        'permissions': 'read,write',
    })
    with app.app_context():
        from database import get_db
        db = get_db()
        uploader = db.execute("SELECT id FROM users WHERE username = 'uploader'").fetchone()
        filepath = os.path.join(config.NAS_STORAGE, 'owned.txt')
        with open(filepath, 'wb') as f:
            f.write(b'x')
        db.execute(
            'INSERT INTO files (filename, filepath, size, uploaded_by) VALUES (?, ?, ?, ?)',
            ('owned.txt', filepath, 1, uploader['id']),
        )
        db.commit()
        user_id = uploader['id']
        db.close()

    admin_client.post(f'/users/{user_id}/delete', follow_redirects=True)

    with app.app_context():
        from database import get_db
        db = get_db()
        row = db.execute("SELECT uploaded_by FROM files WHERE filename = 'owned.txt'").fetchone()
        db.close()
    assert row is not None
    assert row['uploaded_by'] is None


def test_duplicate_username_rejected(admin_client):
    admin_client.post('/users/create', data={
        'username': 'dupeuser',
        'password': 'pass',
        'role': 'user',
        'permissions': 'read',
    })
    resp = admin_client.post('/users/create', data={
        'username': 'dupeuser',
        'password': 'pass',
        'role': 'user',
        'permissions': 'read',
    }, follow_redirects=True)
    assert b'already exists' in resp.data
