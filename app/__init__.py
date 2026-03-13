from flask import Flask

from app.cli import register_cli
from app.extensions import db, login_manager, migrate
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.api import activities, admin, auth, certificates, courses, events, institutional_certificates, reports
    from app.main import errors, routes
    from app.models import User

    app.register_blueprint(auth.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(activities.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(certificates.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(institutional_certificates.bp)
    app.register_blueprint(routes.bp)
    app.register_blueprint(errors.bp)

    register_cli(app)

    @login_manager.user_loader
    def load_user(username):
        return db.session.get(User, username)

    return app