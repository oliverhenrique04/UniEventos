from .extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.types import TypeDecorator, String
from sqlalchemy.sql import operators
from app.utils import normalize_cpf


EVENT_ALLOWED_ROLE_VALUES = ('participante', 'professor', 'coordenador', 'gestor')
DEFAULT_EVENT_ALLOWED_ROLES = EVENT_ALLOWED_ROLE_VALUES
DEFAULT_EVENT_REGISTRATION_CATEGORY_NAME = 'Geral'


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
    event_registrations = db.relationship(
        'EventRegistration',
        back_populates='user',
        foreign_keys='EventRegistration.user_cpf',
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
    allowed_roles = db.relationship(
        'EventAllowedRole',
        back_populates='event',
        cascade='all, delete-orphan',
        order_by='EventAllowedRole.role',
    )
    registration_categories = db.relationship(
        'EventRegistrationCategory',
        back_populates='event',
        cascade='all, delete-orphan',
        order_by='(EventRegistrationCategory.ordem, EventRegistrationCategory.id)',
    )
    registrations = db.relationship(
        'EventRegistration',
        back_populates='event',
        cascade='all, delete-orphan',
        order_by='EventRegistration.id',
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

    @property
    def allowed_roles_list(self):
        if self.allowed_roles:
            return [item.role for item in self.allowed_roles if item.role]
        return list(DEFAULT_EVENT_ALLOWED_ROLES)

    @property
    def registration_categories_list(self):
        return list(self.registration_categories or [])


class EventAllowedRole(db.Model):
    """Represents one authenticated profile allowed to enroll in an event."""
    __tablename__ = 'event_allowed_roles'

    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), primary_key=True)
    role = db.Column(db.String(20), primary_key=True)

    event = db.relationship('Event', back_populates='allowed_roles')

    __table_args__ = (
        db.CheckConstraint(
            "role in ('participante', 'professor', 'coordenador', 'gestor')",
            name='ck_event_allowed_role_value',
        ),
        db.Index('ix_event_allowed_roles_role', 'role'),
    )


class EventRegistrationCategory(db.Model):
    """Registration category with optional quota for one event."""
    __tablename__ = 'event_registration_categories'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    nome = db.Column(db.String(80), nullable=False)
    vagas = db.Column(db.Integer, nullable=False, default=-1)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship('Event', back_populates='registration_categories')
    registrations = db.relationship(
        'EventRegistration',
        back_populates='category',
        order_by='EventRegistration.id',
    )

    __table_args__ = (
        db.UniqueConstraint('event_id', 'nome', name='uq_event_registration_category_event_name'),
        db.Index('ix_event_registration_categories_event_id', 'event_id'),
        db.Index('ix_event_registration_categories_ordem', 'ordem'),
    )


class EventRegistration(db.Model):
    """Represents a unique user registration at the event level."""
    __tablename__ = 'event_registrations'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_cpf = db.Column(CPFDigitsType(), db.ForeignKey('users.cpf'), nullable=False)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registration_categories.id'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    event = db.relationship('Event', back_populates='registrations')
    user = db.relationship('User', back_populates='event_registrations', foreign_keys=[user_cpf])
    category = db.relationship('EventRegistrationCategory', back_populates='registrations')
    enrollments = db.relationship(
        'Enrollment',
        back_populates='event_registration',
        order_by='Enrollment.id',
    )

    __table_args__ = (
        db.UniqueConstraint('event_id', 'user_cpf', name='uq_event_registration_event_user'),
        db.Index('ix_event_registrations_event_id', 'event_id'),
        db.Index('ix_event_registrations_user_cpf', 'user_cpf'),
        db.Index('ix_event_registrations_category_id', 'category_id'),
    )


class Activity(db.Model):
    """Represents an activity within an event.

    Attributes:
        id (int): Primary key.
        event_id (int): Foreign key to the event.
        nome (str): Activity name.
        palestrante (str): Speaker name.
        email_palestrante (str): Speaker email address.
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
    email_palestrante = db.Column(db.String(120), nullable=True)
    local = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    data_atv = db.Column(db.Date)
    hora_atv = db.Column(db.Time)
    carga_horaria = db.Column(db.Integer)
    vagas = db.Column(db.Integer, default=-1)
    
    # Geofencing for security
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    speakers = db.relationship(
        'ActivitySpeaker',
        back_populates='activity',
        cascade="all, delete-orphan",
        order_by='(ActivitySpeaker.ordem, ActivitySpeaker.id)',
    )
    enrollments = db.relationship('Enrollment', backref='activity', cascade="all, delete-orphan")

    def get_speakers_payload(self, include_emails=True):
        payload = []
        if self.speakers:
            for speaker in self.speakers:
                payload.append({
                    'id': speaker.id,
                    'nome': str(speaker.nome or ''),
                    'email': (str(speaker.email or '') if include_emails else None),
                    'ordem': int(speaker.ordem or 0),
                })

        if payload:
            return payload

        legacy_name = str(self.palestrante or '')
        legacy_email = str(self.email_palestrante or '') if include_emails else None
        if legacy_name.strip() or (legacy_email or '').strip():
            return [{
                'id': None,
                'nome': legacy_name,
                'email': legacy_email,
                'ordem': 0,
            }]

        return []

    def get_speaker_names(self):
        return [
            str(item.get('nome') or '').strip()
            for item in self.get_speakers_payload(include_emails=False)
            if str(item.get('nome') or '').strip()
        ]

    @property
    def palestrantes_payload(self):
        return self.get_speakers_payload(include_emails=True)

    @property
    def palestrantes_label(self):
        return ', '.join(self.get_speaker_names())

    @property
    def primary_speaker_name(self):
        names = self.get_speaker_names()
        if names:
            return names[0]
        return str(self.palestrante or '').strip()

    @property
    def primary_speaker_email(self):
        payload = self.get_speakers_payload(include_emails=True)
        if not payload:
            return None
        email = str(payload[0].get('email') or '').strip()
        return email or None

    def sync_legacy_speaker_fields(self):
        self.palestrante = self.primary_speaker_name or ''
        self.email_palestrante = self.primary_speaker_email


class ActivitySpeaker(db.Model):
    """Represents one speaker/facilitator linked to an activity."""
    __tablename__ = 'activity_speakers'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    activity = db.relationship('Activity', back_populates='speakers')

    __table_args__ = (
        db.Index('ix_activity_speakers_activity_id', 'activity_id'),
        db.Index('ix_activity_speakers_ordem', 'ordem'),
    )


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
    event_registration_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registrations.id'),
        nullable=True,
    )
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

    event_registration = db.relationship('EventRegistration', back_populates='enrollments')

    __table_args__ = (
        db.UniqueConstraint('activity_id', 'user_cpf', name='uq_activity_enrollment_user_activity'),
    )

    @property
    def registration_category(self):
        if self.event_registration and self.event_registration.category:
            return self.event_registration.category

        activity = getattr(self, 'activity', None)
        event = getattr(activity, 'event', None) if activity else None
        if not event:
            return None

        for registration in getattr(event, 'registrations', []) or []:
            if registration.user_cpf == self.user_cpf:
                return registration.category
        return None

    @property
    def registration_category_name(self):
        category = self.registration_category
        return category.nome if category else DEFAULT_EVENT_REGISTRATION_CATEGORY_NAME


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
        db.UniqueConstraint('certificate_id', 'user_username', name='uq_institutional_recipient_user_per_cert'),
        db.Index('ix_institutional_recipient_certificate_id', 'certificate_id'),
        db.Index('ix_institutional_recipient_user_username', 'user_username'),
        db.Index('ix_institutional_recipient_entregue', 'cert_entregue'),
        db.Index('ix_institutional_recipient_data_envio', 'cert_data_envio'),
    )
