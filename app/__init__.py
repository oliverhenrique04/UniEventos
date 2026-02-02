from flask import Flask
from .models.database import init_db

def create_app():
    app = Flask(__name__)
    app.secret_key = "chave_mestra_mvc_final"

    # Inicializa o banco de dados
    init_db()

    # Registrar os Controllers (Blueprints)
    from .controllers.auth import auth_bp
    from .controllers.admin import admin_bp
    from .controllers.events import events_bp
    from .controllers.participant import participant_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(participant_bp)

    # Rota raiz (redirecionamento simples)
    from flask import session, render_template, redirect
    @app.route('/')
    def index():
        if 'user' not in session:
            return render_template('login.html')
        return render_template('dashboard.html', user=session['user'])

    return app