from .extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.types import TypeDecorator, String
from sqlalchemy.sql import operators
from app.utils import normalize_cpf


class CPFDigitsType(TypeDecorator):
    """Stores CPF as 11 digits and normalizes bound values for comparisons."""

    impl = String(11)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        normalized = normalize_cpf(value)
        if not normalized:
            return None
        if len(normalized) != 11:
            raise ValueError('CPF deve conter 11 digitos')
        return normalized

    def process_result_value(self, value, dialect):
        return value

    def coerce_compared_value(self, op, value):
        # Preserve wildcard semantics in LIKE/ILIKE operations.
        if op in (
            operators.like_op,
            operators.not_like_op,
            operators.ilike_op,
            operators.not_ilike_op,
        ):
            return String()
        return self


class User(UserMixin, db.Model):
    """Represents a user in the system.

    Attributes:
        username (str): Unique identifier for login.
        email (str): Email address for notifications.
        password_hash (str): Hashed password for security.
        role (str): Permissions level (admin, coordinator, teacher, student).
        nome (str): User's full name.
        cpf (str): Unique Brazilian document ID.
    """
    __tablename__ = 'users'

    username = db.Column(db.String(50), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True) # Added for notifications
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20))
    nome = db.Column(db.String(100))
    cpf = db.Column(CPFDigitsType(), unique=True)
    ra = db.Column(db.String(20), unique=True, nullable=True) # Added for academic tracking
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    can_create_events = db.Column(db.Boolean, default=False)

    course_obj = db.relationship('Course', backref='students')
    institutional_certificates = db.relationship('InstitutionalCertificate', backref='creator')
    institutional_recipient_links = db.relationship(
        'InstitutionalCertificateRecipient',
        back_populates='linked_user',
        foreign_keys='InstitutionalCertificateRecipient.user_username',
    )

    @property
    def curso(self):
        return self.course_obj.nome if self.course_obj else None

    @curso.setter
    def curso(self, value):
        if value is None:
            self.course_id = None
            return
        normalized = str(value).strip()
        if not normalized:
            self.course_id = None
            return

        course = Course.query.filter(Course.nome.ilike(normalized)).first()
        if course:
            self.course_id = course.id

    def set_password(self, password):
        """Sets the user's password hash.

        Args:
            password (str): The plain text password to hash.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the hash.

        Args:
            password (str): The password to verify.

        Returns:
            bool: True if passwords match, False otherwise.
        """
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """Returns the user identifier (username).

        Returns:
            str: The username.
        """
        return self.username

    def to_dict(self):
        """Serialize user data for API responses or tests."""
        return {
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'nome': self.nome,
            'cpf': self.cpf,
            'ra': self.ra,
            'curso': self.curso,
            'course_id': self.course_id,
            'can_create_events': self.can_create_events,
        }


class Course(db.Model):
    """Represents a Course/Major in the institution.
    
    Attributes:
        id (int): Primary key.
        nome (str): Course name (e.g., 'Ciência da Computação').
    """
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)


class Event(db.Model):
    """Represents an event in the domain.

    Attributes:
        id (int): Primary key.
        owner_username (str): Username of the event creator.
        nome (str): Event name.
        descricao (str): Event description.
        tipo (str): Event type (PADRAO or RAPIDO).
        token_publico (str): Public token for sharing.
        status (str): Event status (ABERTO, etc.).
        data_inicio (str): Start date (YYYY-MM-DD).
        hora_inicio (str): Start time (HH:MM).
        data_fim (str): End date (YYYY-MM-DD).
        hora_fim (str): End time (HH:MM).
        curso (str): Course associated with the event (for filtering).
        cert_bg_path (str): File path to certificate background image.
    """
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    owner_username = db.Column(db.String(50), db.ForeignKey('users.username'))
    nome = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    tipo = db.Column(db.String(20))  # 'PADRAO' or 'RAPIDO'
    data_inicio = db.Column(db.Date)
    hora_inicio = db.Column(db.Time)
    data_fim = db.Column(db.Date)
    hora_fim = db.Column(db.Time)
    token_publico = db.Column(db.String(50))
    status = db.Column(db.String(20), default='ABERTO')
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    
    # Geofencing Defaults
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Certificate Customization
    cert_bg_path = db.Column(db.String(200), nullable=True, default='file/fundo_padrao.png')
    cert_template_json = db.Column(db.Text, nullable=True) # JSON with positions of variables

    course_obj = db.relationship('Course', backref='events')
    activities = db.relationship('Activity', backref='event', cascade="all, delete-orphan")

    @property
    def curso(self):
        return self.course_obj.nome if self.course_obj else None

    @curso.setter
    def curso(self, value):
        if value is None:
            self.course_id = None
            return
        normalized = str(value).strip()
        if not normalized:
            self.course_id = None
            return

        course = Course.query.filter(Course.nome.ilike(normalized)).first()
        if course:
            self.course_id = course.id


class Activity(db.Model):
    """Represents an activity within an event.

    Attributes:
        id (int): Primary key.
        event_id (int): Foreign key to the event.
        nome (str): Activity name.
        palestrante (str): Speaker name.
        local (str): Location of the activity.
        descricao (str): Description.
        data_atv (str): Date of activity.
        hora_atv (str): Time of activity.
        carga_horaria (int): Duration/Workload in hours.
        vagas (int): Number of available spots (-1 for unlimited).
    """
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    nome = db.Column(db.String(100))
    palestrante = db.Column(db.String(100))
    local = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    data_atv = db.Column(db.Date)
    hora_atv = db.Column(db.Time)
    carga_horaria = db.Column(db.Integer)
    vagas = db.Column(db.Integer, default=-1)
    
    # Geofencing for security
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    enrollments = db.relationship('Enrollment', backref='activity', cascade="all, delete-orphan")


class Enrollment(db.Model):
    """Represents a user's enrollment in an activity.

    Attributes:
        id (int): Primary key.
        activity_id (int): Foreign key to activity.
        user_cpf (str): Foreign key to user CPF.
        nome (str): Snapshot of user name at enrollment time.
        presente (bool): Attendance status.
    """
    __tablename__ = 'activity_enrollments'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'))
    user_cpf = db.Column(CPFDigitsType(), db.ForeignKey('users.cpf'))
    nome = db.Column(db.String(100))  # Snapshot of name
    presente = db.Column(db.Boolean, default=False)
    cert_hash = db.Column(db.String(64), unique=True, nullable=True) # For validation
    
    # Certificate Delivery Tracking
    cert_entregue = db.Column(db.Boolean, default=False)
    cert_data_envio = db.Column(db.DateTime, nullable=True)
    cert_email_alternativo = db.Column(db.String(120), nullable=True)

    # Location Capture for Audit
    lat_checkin = db.Column(db.Float, nullable=True)
    lon_checkin = db.Column(db.Float, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('activity_id', 'user_cpf', name='uq_activity_enrollment_user_activity'),
    )


class InstitutionalCertificate(db.Model):
    """Certificate batch for institutional (non-event) use cases."""
    __tablename__ = 'institutional_certificates'

    id = db.Column(db.Integer, primary_key=True)
    created_by_username = db.Column(db.String(50), db.ForeignKey('users.username'), nullable=False)
    titulo = db.Column(db.String(140), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('institutional_certificate_categories.id'), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    data_emissao = db.Column(db.String(10), nullable=False)
    signer_name = db.Column(db.String(120), nullable=True)
    cert_bg_path = db.Column(db.String(200), nullable=True, default='file/fundo_padrao.png')
    cert_template_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='RASCUNHO')
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    recipients = db.relationship(
        'InstitutionalCertificateRecipient',
        backref='certificate',
        cascade='all, delete-orphan'
    )
    category = db.relationship('InstitutionalCertificateCategory', backref='certificates')

    @property
    def categoria(self):
        return self.category.nome if self.category else None

    __table_args__ = (
        db.CheckConstraint("status in ('RASCUNHO', 'ENVIADO', 'ARQUIVADO')", name='ck_institutional_certificate_status'),
        db.Index('ix_institutional_cert_created_by', 'created_by_username'),
        db.Index('ix_institutional_cert_status', 'status'),
        db.Index('ix_institutional_cert_category_id', 'category_id'),
    )


class InstitutionalCertificateCategory(db.Model):
    """Normalized lookup table for institutional certificate categories."""
    __tablename__ = 'institutional_certificate_categories'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)


class InstitutionalCertificateRecipient(db.Model):
    """Recipient row for institutional certificate delivery and tracking."""
    __tablename__ = 'institutional_certificate_recipients'

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey('institutional_certificates.id'), nullable=False)
    user_username = db.Column(db.String(50), db.ForeignKey('users.username'), nullable=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    cpf = db.Column(CPFDigitsType(), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    cert_hash = db.Column(db.String(16), unique=True, nullable=True)
    cert_entregue = db.Column(db.Boolean, default=False)
    cert_data_envio = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    linked_user = db.relationship(
        'User',
        back_populates='institutional_recipient_links',
        foreign_keys=[user_username],
    )

    __table_args__ = (
        db.UniqueConstraint('certificate_id', 'email', name='uq_institutional_recipient_email_per_cert'),
        db.UniqueConstraint('certificate_id', 'cpf', name='uq_institutional_recipient_cpf_per_cert'),
        db.Index('ix_institutional_recipient_certificate_id', 'certificate_id'),
        db.Index('ix_institutional_recipient_user_username', 'user_username'),
        db.Index('ix_institutional_recipient_entregue', 'cert_entregue'),
        db.Index('ix_institutional_recipient_data_envio', 'cert_data_envio'),
    )

