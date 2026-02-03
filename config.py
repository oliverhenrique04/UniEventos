import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave_mestra_v16_certificado_fix_secure'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'sistema_academico.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RABBITMQ_URL = os.environ.get('RABBITMQ_URL') or 'amqp://guest:guest@localhost:5672/'
    BASE_URL = os.environ.get('BASE_URL') or 'https://wqvkvg1m-5000.brs.devtunnels.ms/'

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False