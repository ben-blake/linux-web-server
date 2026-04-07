from flask import Blueprint, render_template
from utils.decorators import admin_required

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')


@backup_bp.route('/')
@admin_required
def index():
    return render_template('backup/index.html')
