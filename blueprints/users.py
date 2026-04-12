from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from utils.decorators import login_required, admin_required

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/')
@admin_required
def list_users():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('users/list.html', users=users)


@users_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role']
        permissions = ','.join(request.form.getlist('permissions')) or 'read'

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('users/create.html')

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            db.close()
            flash('Username already exists.', 'error')
            return render_template('users/create.html')

        db.execute(
            'INSERT INTO users (username, password_hash, role, permissions) VALUES (?, ?, ?, ?)',
            (username, generate_password_hash(password, method='pbkdf2:sha256'), role, permissions)
        )
        db.commit()
        db.close()
        flash(f'User "{username}" created.', 'success')
        return redirect(url_for('users.list_users'))

    return render_template('users/create.html')


@users_bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    db = get_db()

    if request.method == 'POST':
        role = request.form['role']
        permissions = ','.join(request.form.getlist('permissions')) or 'read'
        db.execute('UPDATE users SET role = ?, permissions = ? WHERE id = ?', (role, permissions, user_id))
        db.commit()
        db.close()
        flash('User updated.', 'success')
        return redirect(url_for('users.list_users'))

    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()

    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('users.list_users'))

    return render_template('users/edit.html', user=user)


@users_bp.route('/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    db = get_db()
    db.execute('UPDATE files SET uploaded_by = NULL WHERE uploaded_by = ?', (user_id,))
    db.execute('UPDATE backups SET created_by = NULL WHERE created_by = ?', (user_id,))
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    db.close()
    flash('User deleted.', 'success')
    return redirect(url_for('users.list_users'))


@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        if not check_password_hash(user['password_hash'], current_password):
            db.close()
            flash('Current password is incorrect.', 'error')
            return render_template('profile.html')

        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (generate_password_hash(new_password, method='pbkdf2:sha256'), session['user_id']))
        db.commit()
        db.close()
        flash('Password updated.', 'success')
        return redirect(url_for('users.profile'))

    return render_template('profile.html')
