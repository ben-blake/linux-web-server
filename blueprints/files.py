from flask import Blueprint, render_template
from utils.decorators import login_required

files_bp = Blueprint('files', __name__, url_prefix='/files')


@files_bp.route('/')
@login_required
def index():
    return render_template('files/index.html')
