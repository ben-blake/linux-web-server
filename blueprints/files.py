import os
import shutil
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

import config
from database import get_db
from utils.decorators import permission_required

files_bp = Blueprint('files', __name__, url_prefix='/files')


def _storage_root():
    return os.path.realpath(os.path.abspath(config.NAS_STORAGE))


def _to_rel_display(abs_path):
    root = _storage_root()
    abs_path = os.path.realpath(os.path.abspath(abs_path))
    if abs_path == root:
        return ''
    prefix = root + os.sep
    if not abs_path.startswith(prefix):
        return None
    return abs_path[len(prefix):].replace(os.sep, '/')


def safe_join(relative):
    """Resolve a path under NAS_STORAGE; relative uses '/' segments from storage root."""
    root = _storage_root()
    if not relative:
        return root
    rel = (relative or '').replace('\\', '/').strip('/')
    if not rel:
        return root
    for part in rel.split('/'):
        if part in ('', '.', '..'):
            raise ValueError('Invalid path')
    candidate = os.path.realpath(os.path.join(root, *rel.split('/')))
    root_prefix = root if root.endswith(os.sep) else root + os.sep
    if candidate != root and not candidate.startswith(root_prefix):
        raise ValueError('Path outside storage')
    return candidate


def _disk_stats_for_storage():
    root = _storage_root()
    try:
        usage = shutil.disk_usage(root)
        total = usage.total
        if total <= 0:
            return None
        used = total - usage.free
        return {
            'free_gb': round(usage.free / (1024**3), 1),
            'total_gb': round(total / (1024**3), 1),
            'used_pct': round(100 * used / total, 1),
        }
    except OSError:
        return None


def _list_directory(abs_dir):
    entries = []
    try:
        names = sorted(os.listdir(abs_dir), key=lambda n: (not os.path.isdir(os.path.join(abs_dir, n)), n.lower()))
    except OSError:
        return entries
    for name in names:
        full = os.path.join(abs_dir, name)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        is_dir = os.path.isdir(full)
        rel = _to_rel_display(full)
        if rel is None:
            continue
        entries.append(
            {
                'name': name,
                'rel_path': rel,
                'is_dir': is_dir,
                'size': None if is_dir else stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            }
        )
    return entries


def _prune_missing_files(db):
    """Remove DB records for files that no longer exist on disk."""
    rows = db.execute('SELECT id, filepath FROM files').fetchall()
    for row in rows:
        if not os.path.isfile(row['filepath']):
            db.execute('DELETE FROM files WHERE id = ?', (row['id'],))
    db.commit()


def _remove_db_paths_for_prefix(db, prefix_abs):
    prefix_abs = os.path.realpath(prefix_abs)
    root_prefix = prefix_abs + os.sep
    rows = db.execute('SELECT id, filepath FROM files').fetchall()
    for row in rows:
        fp = os.path.realpath(row['filepath'])
        if fp == prefix_abs or fp.startswith(root_prefix):
            db.execute('DELETE FROM files WHERE id = ?', (row['id'],))


def _update_db_paths_after_rename(db, old_abs, new_abs):
    old_abs = os.path.realpath(old_abs)
    new_abs = os.path.realpath(new_abs)
    old_prefix = old_abs + os.sep
    rows = db.execute('SELECT id, filepath, filename FROM files').fetchall()
    for row in rows:
        fp = os.path.realpath(row['filepath'])
        if fp == old_abs:
            db.execute(
                'UPDATE files SET filepath = ?, filename = ? WHERE id = ?',
                (new_abs, os.path.basename(new_abs), row['id']),
            )
        elif fp.startswith(old_prefix):
            suffix = fp[len(old_prefix):]
            new_fp = os.path.join(new_abs, suffix)
            db.execute('UPDATE files SET filepath = ? WHERE id = ?', (new_fp, row['id']))


@files_bp.route('/')
@permission_required('read')
def index():
    rel = request.args.get('path', '').strip()
    try:
        current = safe_join(rel)
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index'))

    if not os.path.isdir(current):
        flash('Folder not found.', 'error')
        return redirect(url_for('files.index'))

    db = get_db()
    _prune_missing_files(db)
    db.close()

    entries = _list_directory(current)
    breadcrumbs = []
    if rel:
        acc = []
        for part in rel.replace('\\', '/').split('/'):
            if not part:
                continue
            acc.append(part)
            breadcrumbs.append({'name': part, 'path': '/'.join(acc)})

    perms = session.get('permissions', '').split(',')
    can_write = 'write' in perms
    can_edit = 'edit' in perms

    return render_template(
        'files/index.html',
        entries=entries,
        current_path=rel,
        breadcrumbs=breadcrumbs,
        can_write=can_write,
        can_edit=can_edit,
        entry_count=len(entries),
        storage_stats=_disk_stats_for_storage(),
    )


@files_bp.route('/download')
@permission_required('read')
def download():
    rel = request.args.get('path', '').strip()
    try:
        target = safe_join(rel)
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index'))

    if not os.path.isfile(target):
        flash('File not found.', 'error')
        return redirect(url_for('files.index'))

    return send_file(target, as_attachment=True, download_name=os.path.basename(target))


@files_bp.route('/upload', methods=['POST'])
@permission_required('write')
def upload():
    rel = request.form.get('path', '').strip()
    try:
        folder = safe_join(rel)
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index'))

    if not os.path.isdir(folder):
        flash('Invalid upload folder.', 'error')
        return redirect(url_for('files.index', path=rel))

    file = request.files.get('file')
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('files.index', path=rel))

    name = secure_filename(file.filename)
    if not name:
        flash('Invalid file name.', 'error')
        return redirect(url_for('files.index', path=rel))

    dest = os.path.join(folder, name)
    file.save(dest)
    dest = os.path.realpath(dest)
    size = os.path.getsize(dest)

    db = get_db()
    existing = db.execute('SELECT id FROM files WHERE filepath = ?', (dest,)).fetchone()
    if existing:
        db.execute('UPDATE files SET size = ?, uploaded_by = ? WHERE filepath = ?',
                   (size, session['user_id'], dest))
    else:
        db.execute(
            'INSERT INTO files (filename, filepath, size, uploaded_by) VALUES (?, ?, ?, ?)',
            (name, dest, size, session['user_id']),
        )
    db.commit()
    db.close()

    flash(f'Uploaded "{name}".', 'success')
    return redirect(url_for('files.index', path=rel))


@files_bp.route('/mkdir', methods=['POST'])
@permission_required('write')
def mkdir():
    rel = request.form.get('path', '').strip()
    name = secure_filename(request.form.get('name', '').strip())
    try:
        parent = safe_join(rel)
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index'))

    if not name:
        flash('Folder name is required.', 'error')
        return redirect(url_for('files.index', path=rel))

    if not os.path.isdir(parent):
        flash('Parent folder not found.', 'error')
        return redirect(url_for('files.index', path=rel))

    new_dir = os.path.join(parent, name)
    if os.path.exists(new_dir):
        flash('A file or folder with that name already exists.', 'error')
        return redirect(url_for('files.index', path=rel))

    try:
        os.mkdir(new_dir)
    except (FileExistsError, OSError) as e:
        flash(f'Could not create folder: {e}', 'error')
        return redirect(url_for('files.index', path=rel))
    flash(f'Created folder "{name}".', 'success')
    return redirect(url_for('files.index', path=rel))


@files_bp.route('/rename', methods=['POST'])
@permission_required('edit')
def rename_item():
    old_rel = request.form.get('path', '').strip()
    new_name = secure_filename(request.form.get('new_name', '').strip())
    parent_rel = request.form.get('parent_path', '').strip()

    try:
        old_abs = safe_join(old_rel)
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    if not new_name:
        flash('New name is required.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    if not os.path.exists(old_abs):
        flash('Item not found.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    parent_dir = os.path.dirname(old_abs)
    new_abs = os.path.join(parent_dir, new_name)
    if os.path.realpath(old_abs) == os.path.realpath(new_abs):
        return redirect(url_for('files.index', path=parent_rel))

    if os.path.exists(new_abs):
        flash('Target name already exists.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    os.rename(old_abs, new_abs)

    db = get_db()
    _update_db_paths_after_rename(db, old_abs, new_abs)
    db.commit()
    db.close()

    flash('Renamed successfully.', 'success')
    return redirect(url_for('files.index', path=parent_rel))


@files_bp.route('/delete', methods=['POST'])
@permission_required('write')
def delete_item():
    rel = request.form.get('path', '').strip()
    parent_rel = request.form.get('parent_path', '').strip()
    try:
        target = safe_join(rel)
    except ValueError:
        flash('Invalid path.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    root = _storage_root()
    if os.path.realpath(target) == root:
        flash('Cannot delete the storage root.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    if not os.path.exists(target):
        flash('Item not found.', 'error')
        return redirect(url_for('files.index', path=parent_rel))

    db = get_db()
    if os.path.isdir(target):
        shutil.rmtree(target)
        _remove_db_paths_for_prefix(db, target)
    else:
        os.remove(target)
        db.execute('DELETE FROM files WHERE filepath = ?', (os.path.realpath(target),))
    db.commit()
    db.close()

    flash('Deleted.', 'success')
    return redirect(url_for('files.index', path=parent_rel))
