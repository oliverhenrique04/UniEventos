from .extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(50), primary_key=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))
    nome = db.Column(db.String(100))
    cpf = db.Column(db.String(14), unique=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.username

    def to_dict(self):
        return {
            'username': self.username,
            'role': self.role,
            'nome': self.nome,
            'cpf': self.cpf
        }

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    owner_username = db.Column(db.String(50), db.ForeignKey('users.username'))
    nome = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    tipo = db.Column(db.String(20)) # 'PADRAO' or 'RAPIDO'
    data_inicio = db.Column(db.String(10))
    hora_inicio = db.Column(db.String(5))
    data_fim = db.Column(db.String(10))
    hora_fim = db.Column(db.String(5))
    token_publico = db.Column(db.String(50))
    status = db.Column(db.String(20), default='ABERTO')

    activities = db.relationship('Activity', backref='event', cascade="all, delete-orphan")

    def to_dict(self, current_user=None):
        return {
            'id': self.id,
            'owner': self.owner_username,
            'nome': self.nome,
            'descricao': self.descricao,
            'tipo': self.tipo,
            'data_inicio': self.data_inicio,
            'hora_inicio': self.hora_inicio,
            'data_fim': self.data_fim,
            'hora_fim': self.hora_fim,
            'token_publico': self.token_publico,
            'status': self.status,
            'atividades': [a.to_dict(current_user) for a in self.activities]
        }

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    nome = db.Column(db.String(100))
    palestrante = db.Column(db.String(100))
    local = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    data_atv = db.Column(db.String(10))
    hora_atv = db.Column(db.String(5))
    carga_horaria = db.Column(db.Integer)
    vagas = db.Column(db.Integer, default=-1)

    enrollments = db.relationship('Enrollment', backref='activity', cascade="all, delete-orphan")

    def to_dict(self, current_user=None):
        total_inscritos = len(self.enrollments)
        inscrito = False
        if current_user:
            # Check if user is enrolled (by cpf to match legacy logic, or username)
            # Legacy app stored 'cpf' in enrollment. Let's stick to that for now or link via FK.
            # I will assume Enrollment links to User.cpf or User.username.
            # Let's check the Enrollment model below.
            for e in self.enrollments:
                if e.user_cpf == current_user.cpf:
                    inscrito = True
                    break
        
        return {
            'id': self.id,
            'event_id': self.event_id,
            'nome': self.nome,
            'palestrante': self.palestrante,
            'local': self.local,
            'descricao': self.descricao,
            'data_atv': self.data_atv,
            'hora_atv': self.hora_atv,
            'carga_horaria': self.carga_horaria,
            'vagas': self.vagas,
            'total_inscritos': total_inscritos,
            'inscrito': inscrito
        }

class Enrollment(db.Model):
    __tablename__ = 'activity_enrollments'
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'))
    event_id = db.Column(db.Integer, db.ForeignKey('events.id')) # Redundant but kept for legacy compat if needed
    user_cpf = db.Column(db.String(14), db.ForeignKey('users.cpf'))
    nome = db.Column(db.String(100)) # Snapshot of name
    presente = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'activity_id': self.activity_id,
            'cpf': self.user_cpf,
            'nome': self.nome,
            'presente': self.presente
        }
