import os
from pathlib import Path
from urllib.parse import quote_plus


BASE_DIR = Path(__file__).resolve().parent


def _load_local_env():
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


def _build_postgres_uri():
    direct_uri = os.environ.get('DATABASE_URL')
    if direct_uri:
        return direct_uri

    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    database = os.environ.get('DB_NAME', 'euro_eventos')
    username = quote_plus(os.environ.get('DB_USER', 'postgres'))
    password = quote_plus(os.environ.get('DB_PASSWORD', 'change-me'))

    return f'postgresql+psycopg://{username}:{password}@{host}:{port}/{database}'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-me')
    SQLALCHEMY_DATABASE_URI = _build_postgres_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }
    RABBITMQ_URL = os.environ.get('RABBITMQ_URL') or 'amqp://guest:guest@localhost:5672/'
    BASE_URL = os.environ.get('BASE_URL') or 'http://localhost:5000'
    BASE_PATH = (os.environ.get('BASE_PATH') or '').strip()
    CERTIFICATE_QR_DEFAULT_X_MM = float(os.environ.get('CERTIFICATE_QR_DEFAULT_X_MM', '12'))
    CERTIFICATE_QR_DEFAULT_Y_MM = float(os.environ.get('CERTIFICATE_QR_DEFAULT_Y_MM', '108'))
    CERTIFICATE_QR_DEFAULT_SIZE_MM = float(os.environ.get('CERTIFICATE_QR_DEFAULT_SIZE_MM', '36'))
    CERTIFICATE_HASH_DEFAULT_X_MM = float(os.environ.get('CERTIFICATE_HASH_DEFAULT_X_MM', '12'))
    CERTIFICATE_HASH_DEFAULT_Y_MM = float(os.environ.get('CERTIFICATE_HASH_DEFAULT_Y_MM', '150'))
    CERTIFICATE_DATE_DEFAULT_X_MM = float(os.environ.get('CERTIFICATE_DATE_DEFAULT_X_MM', '12'))
    CERTIFICATE_DATE_DEFAULT_Y_MM = float(os.environ.get('CERTIFICATE_DATE_DEFAULT_Y_MM', '195'))
    CHECKIN_RADIUS_METERS = int(os.environ.get('CHECKIN_RADIUS_METERS', '500'))
    MOODLE_LOGIN_ENABLED = os.environ.get('MOODLE_LOGIN_ENABLED', 'false').lower() == 'true'
    MOODLE_LOGIN_URL = os.environ.get('MOODLE_LOGIN_URL', '')
    MOODLE_TOOL_CONSUMER_KEY = os.environ.get('MOODLE_TOOL_CONSUMER_KEY', '')
    MOODLE_TOOL_SHARED_SECRET = os.environ.get('MOODLE_TOOL_SHARED_SECRET', '')
    MOODLE_ALLOWED_EMAIL_DOMAIN = os.environ.get('MOODLE_ALLOWED_EMAIL_DOMAIN', 'unieuro.edu.br').lower()
    MOODLE_CPF_FIELD = os.environ.get('MOODLE_CPF_FIELD', 'custom_cpf')


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
