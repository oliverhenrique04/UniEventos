import os
from flask import Flask
from .extensions import db, login_manager
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    from app.api import auth, events, activities, admin, reports, certificates
    from app.main import routes, errors

    app.register_blueprint(auth.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(activities.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(certificates.bp)
    app.register_blueprint(routes.bp)
    app.register_blueprint(errors.bp)

    # Load User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(username):
        return User.query.get(username)

    # Initialize DB (Simple check for dev purposes, similar to legacy)
    with app.app_context():
        # Check if DB needs init
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if not os.path.exists(db_path) and ':memory:' not in db_path:
             init_db()

    return app

def init_db():
    db.create_all()
    
    from app.models import User
    # Seed default users
    if not User.query.filter_by(username='admin').first():
        u_admin = User(username='admin', email='admin@example.com', role='admin', nome='Super Admin', cpf='000.000.000-00', ra='ADMIN-001', curso='TI')
        u_admin.set_password('admin')
        
        u_prof = User(username='prof', email='prof@example.com', role='professor', nome='Prof. Pardal', cpf='111.111.111-11', ra='PROF-001', curso='Engenharia')
        u_prof.set_password('1234')
        
        u_aluno = User(username='aluno', email='aluno@example.com', role='participante', nome='Lucas Aluno', cpf='222.222.222-22', ra='20260001', curso='Direito')
        u_aluno.set_password('1234')
        
        db.session.add_all([u_admin, u_prof, u_aluno])
        db.session.commit()