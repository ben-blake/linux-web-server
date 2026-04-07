from flask import Blueprint, render_template
from utils.decorators import login_required

monitor_bp = Blueprint('monitor', __name__, url_prefix='/monitor')


@monitor_bp.route('/')
@login_required
def index():
    return render_template('monitor/index.html')
