# File Management Module — Guide for Rasagyna

You own the **File Management** module. This lets users upload, download, and delete files, and create/rename/delete folders on the NAS.

## Getting Started

```bash
git clone https://github.com/ben-blake/linux-web-server.git
cd linux-web-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000`, login with `admin` / `admin`. Click "Files" in the sidebar — you'll see a placeholder page. That's what you're replacing.

## Your Files

You only need to edit these:

| File | What it does |
|------|-------------|
| `blueprints/files.py` | Your backend routes (Python) |
| `templates/files/index.html` | Your main page template (HTML) |
| `templates/files/*.html` | Any additional pages you need |

Don't touch other blueprints or `app.py` — your module is self-contained.

## Create a Feature Branch

```bash
git checkout -b feature/file-management
```

Work on this branch, commit often, and open a pull request when done.

## What to Build

### Routes

| Route | Method | What it does |
|-------|--------|-------------|
| `/files/` | GET | Browse files and folders (list contents of current directory) |
| `/files/upload` | POST | Upload a file to the current directory |
| `/files/download/<path>` | GET | Download a file |
| `/files/delete` | POST | Delete a file |
| `/files/mkdir` | POST | Create a new folder |
| `/files/rename` | POST | Rename a file or folder |

### How It Works

Files are stored on disk in a directory defined in `config.py`:

```python
import config
storage_path = config.NAS_STORAGE  # /srv/nas
```

File metadata (name, path, size, who uploaded it) gets saved to the `files` database table:

```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    size INTEGER,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Implementation Guide

Here's a skeleton for `blueprints/files.py`:

```python
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from database import get_db
from utils.decorators import login_required, permission_required
import config

files_bp = Blueprint('files', __name__, url_prefix='/files')


@files_bp.route('/')
@login_required
def index():
    """Browse files. Use ?path=subfolder to navigate into folders."""
    current_path = request.args.get('path', '')
    full_path = os.path.join(config.NAS_STORAGE, current_path)

    # Security: prevent directory traversal (../)
    full_path = os.path.realpath(full_path)
    if not full_path.startswith(os.path.realpath(config.NAS_STORAGE)):
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index'))

    # List directory contents
    items = []
    if os.path.isdir(full_path):
        for name in sorted(os.listdir(full_path)):
            item_path = os.path.join(full_path, name)
            items.append({
                'name': name,
                'is_dir': os.path.isdir(item_path),
                'size': os.path.getsize(item_path) if os.path.isfile(item_path) else None
            })

    return render_template('files/index.html',
        items=items,
        current_path=current_path
    )


@files_bp.route('/upload', methods=['POST'])
@login_required
@permission_required('write')
def upload():
    """Upload a file."""
    current_path = request.form.get('path', '')
    file = request.files.get('file')

    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('files.index', path=current_path))

    filename = secure_filename(file.filename)  # IMPORTANT: sanitize filename
    full_dir = os.path.join(config.NAS_STORAGE, current_path)
    os.makedirs(full_dir, exist_ok=True)
    filepath = os.path.join(full_dir, filename)
    file.save(filepath)

    # Save metadata to database
    db = get_db()
    db.execute(
        'INSERT INTO files (filename, filepath, size, uploaded_by) VALUES (?, ?, ?, ?)',
        (filename, os.path.join(current_path, filename), os.path.getsize(filepath), session['user_id'])
    )
    db.commit()
    db.close()

    flash(f'Uploaded {filename}.', 'success')
    return redirect(url_for('files.index', path=current_path))


@files_bp.route('/download/<path:filepath>')
@login_required
def download(filepath):
    """Download a file."""
    directory = os.path.join(config.NAS_STORAGE, os.path.dirname(filepath))
    filename = os.path.basename(filepath)
    return send_from_directory(directory, filename, as_attachment=True)


# Add delete, mkdir, rename routes following the same pattern
```

### Key Things to Remember

1. **Always use `secure_filename()`** on uploaded files — prevents malicious filenames
2. **Prevent directory traversal** — check that resolved paths stay inside `NAS_STORAGE`
3. **Use `@permission_required('write')`** on upload, delete, mkdir, rename (mutating actions)
4. **Use `@login_required`** on browse and download (read-only actions)
5. **Access the database** with `get_db()` from `database.py` — it returns an sqlite3 connection with Row factory

### Template Tips

Your `templates/files/index.html` extends `base.html`:

```html
{% extends "base.html" %}
{% block title %}Files — NAS Server{% endblock %}

{% block content %}
<h1>File Manager</h1>

<!-- Upload form -->
<form method="POST" action="{{ url_for('files.upload') }}" enctype="multipart/form-data">
    <input type="hidden" name="path" value="{{ current_path }}">
    <input type="file" name="file" required>
    <button type="submit" class="btn btn-primary">Upload</button>
</form>

<!-- File listing -->
<table>
    <thead>
        <tr><th>Name</th><th>Size</th><th>Actions</th></tr>
    </thead>
    <tbody>
        {% for item in items %}
        <tr>
            <td>
                {% if item.is_dir %}
                    <a href="{{ url_for('files.index', path=current_path + '/' + item.name) }}">{{ item.name }}/</a>
                {% else %}
                    {{ item.name }}
                {% endif %}
            </td>
            <td>{{ item.size or '-' }}</td>
            <td>
                {% if not item.is_dir %}
                    <a href="{{ url_for('files.download', filepath=current_path + '/' + item.name) }}">Download</a>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

## Testing

Run existing tests to make sure you didn't break anything:

```bash
python3 -m pytest tests/ -v
```

## When You're Done

```bash
git add blueprints/files.py templates/files/
git commit -m "feat: file management with upload, download, browse, delete"
git push origin feature/file-management
```

Then open a Pull Request on GitHub.
