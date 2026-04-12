import os
<<<<<<< HEAD
import shutil
=======
>>>>>>> origin/main
import tempfile
import pytest
from app import create_app
from database import get_db, init_db


@pytest.fixture
def app():
    """Create a test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp()
<<<<<<< HEAD
    storage_dir = tempfile.mkdtemp()

    import config
    config.DATABASE = db_path
    config.NAS_STORAGE = storage_dir
=======

    import config
    config.DATABASE = db_path
>>>>>>> origin/main

    test_app = create_app()
    test_app.config['TESTING'] = True

    yield test_app

    os.close(db_fd)
    os.unlink(db_path)
<<<<<<< HEAD
    shutil.rmtree(storage_dir, ignore_errors=True)
=======
>>>>>>> origin/main


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    """A test client already logged in as admin."""
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    return client


@pytest.fixture
def user_client(client, admin_client):
    """Create a regular user and return a client logged in as that user."""
    admin_client.post('/users/create', data={
        'username': 'testuser',
        'password': 'testpass',
        'role': 'user',
        'permissions': 'read'
    })
    client.get('/logout')
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'})
    return client
