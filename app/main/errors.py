from flask import Blueprint, render_template

bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    # db.session.rollback() # If we had db access here directly, but okay for now.
    return render_template('404.html'), 500 # Reusing 404 layout for now or create 500
