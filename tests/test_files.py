import io
import os


def test_files_index_requires_login(client):
    resp = client.get('/files/')
    assert resp.status_code == 302


def test_read_only_user_can_browse_files(user_client):
    resp = user_client.get('/files/')
    assert resp.status_code == 200
    assert b'File Management' in resp.data
    assert b'NAS vault' in resp.data


def test_read_only_user_cannot_upload(user_client):
    data = {
        'path': '',
        'file': (io.BytesIO(b'hello'), 'note.txt'),
    }
    resp = user_client.post(
        '/files/upload',
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert resp.status_code == 403


def test_admin_can_upload_and_download(admin_client):
    data = {
        'path': '',
        'file': (io.BytesIO(b'hello nas'), 'note.txt'),
    }
    resp = admin_client.post(
        '/files/upload',
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b'Uploaded' in resp.data or b'note.txt' in resp.data

    import config

    disk_path = os.path.join(config.NAS_STORAGE, 'note.txt')
    assert os.path.isfile(disk_path)

    resp = admin_client.get('/files/download?path=note.txt')
    assert resp.status_code == 200
    assert resp.data == b'hello nas'


def test_admin_can_mkdir_rename_delete(admin_client):
    import config

    admin_client.post('/files/mkdir', data={'path': '', 'name': 'work'}, follow_redirects=True)
    assert os.path.isdir(os.path.join(config.NAS_STORAGE, 'work'))

    admin_client.post(
        '/files/rename',
        data={'path': 'work', 'new_name': 'projects', 'parent_path': ''},
        follow_redirects=True,
    )
    assert os.path.isdir(os.path.join(config.NAS_STORAGE, 'projects'))
    assert not os.path.exists(os.path.join(config.NAS_STORAGE, 'work'))

    admin_client.post(
        '/files/delete',
        data={'path': 'projects', 'parent_path': ''},
        follow_redirects=True,
    )
    assert not os.path.exists(os.path.join(config.NAS_STORAGE, 'projects'))


def test_path_traversal_blocked(admin_client):
    resp = admin_client.get('/files/?path=..%2fetc', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Invalid path' in resp.data
