import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave_mestra_v16_certificado_fix_secure'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'sistema_academico.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
