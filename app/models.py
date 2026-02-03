from .extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


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
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))
    nome = db.Column(db.String(100))
    cpf = db.Column(db.String(14), unique=True)
    ra = db.Column(db.String(20), unique=True, nullable=True) # Added for academic tracking
    curso = db.Column(db.String(100), nullable=True) # Added for filtering

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
    data_inicio = db.Column(db.String(10))
    hora_inicio = db.Column(db.String(5))
    data_fim = db.Column(db.String(10))
    hora_fim = db.Column(db.String(5))
    token_publico = db.Column(db.String(50))
    status = db.Column(db.String(20), default='ABERTO')
    curso = db.Column(db.String(100), nullable=True) # Added for filtering
    
    # Geofencing Defaults
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Certificate Customization
    cert_bg_path = db.Column(db.String(200), nullable=True)
    cert_template_json = db.Column(db.Text, nullable=True) # JSON with positions of variables

    activities = db.relationship('Activity', backref='event', cascade="all, delete-orphan")


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
    data_atv = db.Column(db.String(10))
    hora_atv = db.Column(db.String(5))
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
        event_id (int): Foreign key to event (legacy/redundant).
        user_cpf (str): Foreign key to user CPF.
        nome (str): Snapshot of user name at enrollment time.
        presente (bool): Attendance status.
    """
    __tablename__ = 'activity_enrollments'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'))
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))  # Redundant but kept for legacy compat if needed
    user_cpf = db.Column(db.String(14), db.ForeignKey('users.cpf'))
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

