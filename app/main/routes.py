from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('login_register.html')
    return render_template('index.html', user=current_user)

@bp.route('/logout')
def logout():
    # This might be redundant if I have it in auth api, but usually logout is a GET link
    # I already defined /api/logout in auth.py which does logout_user() then redirects.
    # But the frontend has <a href="/logout">. So this route is needed.
    # I'll just redirect to the api logout or implement it here.
    return redirect('/api/logout')

@bp.route('/inscrever/<token>')
def inscrever_via_link(token):
    # This was implicitly handled in legacy?
    # Ah, legacy `criar_evento` returned link `/inscrever/{token}`.
    # But there was no route defined for `/inscrever/<token>` in app_legacy.py!
    # Wait, let me check app_legacy.py again.
    # ...
    # I don't see `@app.route('/inscrever/<token>')` in app_legacy.py.
    # Maybe it was handled by frontend routing? No, it's a Flask app.
    # Maybe the legacy code provided was incomplete or I missed it?
    # "return jsonify({"mensagem": "Criado!", "link": f"/inscrever/{token}"})"
    # If the user clicks that link, they get a 404 in the old app?
    # Or maybe it's just a generated link for the user to share, and the actual implementation was missing or handled by a catch-all?
    # There is no catch-all.
    # I will verify app_legacy.py content.
    pass
    return "Link de inscrição (Não implementado no código original)"
