from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService
from flask import current_app
from datetime import datetime
from app.utils import normalize_cpf
from app.extensions import db
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import func

class AuthService:
    """
    Service layer for authentication and user management logic.
    """
    def __init__(self):
        self.user_repo = UserRepository()
        self.notifier = NotificationService()

    def authenticate_user(self, login, password):
        """
        Validates user credentials.
        
        Returns:
            User: The user object if credentials are valid, None otherwise.
        """
        user = None

        cpf_login = normalize_cpf(login)
        if cpf_login:
            user = self.user_repo.get_by_cpf(cpf_login)

        # Backward compatibility for internal users that may still log in by username.
        if not user and login:
            user = self.user_repo.get_by_username(login)

        if user and user.check_password(password):
            return user
        return None

    def authenticate_or_provision_from_moodle(self, cpf, nome=None, email=None):
        """Finds or creates a participant user based on CPF from Moodle launch."""
        normalized_cpf = normalize_cpf(cpf)
        if not normalized_cpf or len(normalized_cpf) != 11:
            return None

        user = self.user_repo.get_by_cpf(normalized_cpf)
        normalized_email = (email or '').strip().lower() or None
        normalized_nome = (nome or '').strip() or 'Comunidade Academica Unieuro'

        if user:
            updated = False
            if normalized_nome and (user.nome or '').strip() != normalized_nome:
                user.nome = normalized_nome
                updated = True
            if normalized_email and (user.email or '').strip().lower() != normalized_email:
                user.email = normalized_email
                updated = True
            if updated:
                db.session.commit()
            return user

        user = User(
            username=normalized_cpf,
            email=normalized_email,
            role='participante',
            nome=normalized_nome,
            cpf=normalized_cpf,
        )
        # Fallback password for first access; users can change it later if needed.
        user.set_password(normalized_cpf)
        return self.user_repo.save(user)

    def register_user(self, data):
        """
        Registers a new user in the system.
        
        Args:
            data (dict): User data containing 'username', 'email', 'password', 'nome', and 'cpf'.
            
        Returns:
            User: The newly created user instance.
            
        Raises:
            ValueError: If the username already exists in the database.
        """
        cpf = normalize_cpf(data.get('cpf'))
        if not cpf or len(cpf) != 11:
            raise ValueError("CPF inválido. Informe 11 dígitos.")

        username = cpf

        if self.user_repo.get_by_username(username) or self.user_repo.get_by_cpf(cpf):
            raise ValueError("Usuário já existe")
            
        user = User(
            username=username,
            email=data.get('email'),
            role='participante',
            nome=data.get('nome'),
            cpf=cpf
        )
        user.set_password(data.get('password') or cpf)
        saved_user = self.user_repo.save(user)
        
        # Send welcome email via RabbitMQ
        if saved_user.email:
            app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
            self.notifier.send_email_task(
                to_email=saved_user.email,
                subject="Bem-vindo ao EuroEventos!",
                template_name='welcome.html',
                template_data={
                    'user_name': saved_user.nome,
                    'email': saved_user.email,
                    'app_url': app_url,
                    'year': datetime.now().year,
                    'unsubscribe_url': f"{app_url}/unsubscribe/" if app_url else '',
                },
            )
        
        return saved_user

    def _password_reset_serializer(self):
        return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='password-reset')

    def _password_reset_max_age(self):
        return int(current_app.config.get('PASSWORD_RESET_MAX_AGE', 3600))

    def request_password_reset(self, email):
        """Triggers password reset email if the account exists."""
        normalized_email = (email or '').strip().lower()
        if not normalized_email:
            return False

        user = User.query.filter(func.lower(User.email) == normalized_email).first()
        if not user:
            return False

        serializer = self._password_reset_serializer()
        token = serializer.dumps({'username': user.username})

        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        if app_url:
            reset_url = f"{app_url}/resetar-senha/{token}"
        else:
            reset_url = f"/resetar-senha/{token}"

        return self.notifier.send_email_task(
            to_email=user.email,
            subject='Recuperação de senha - EuroEventos',
            template_name='password_reset.html',
            template_data={
                'user_name': user.nome,
                'reset_url': reset_url,
                'expires_minutes': int(self._password_reset_max_age() / 60),
                'year': datetime.now().year,
            },
        )

    def reset_password_with_token(self, token, new_password):
        if not token:
            return False, 'Token inválido.'

        if not new_password or len(new_password) < 6:
            return False, 'A nova senha deve ter pelo menos 6 caracteres.'

        serializer = self._password_reset_serializer()
        try:
            payload = serializer.loads(token, max_age=self._password_reset_max_age())
        except SignatureExpired:
            return False, 'Token expirado. Solicite uma nova recuperação de senha.'
        except BadSignature:
            return False, 'Token inválido.'

        username = payload.get('username')
        user = self.user_repo.get_by_username(username)
        if not user:
            return False, 'Usuário não encontrado.'

        user.set_password(new_password)
        db.session.commit()
        return True, 'Senha atualizada com sucesso.'

    def update_profile(self, user, nome, email):
        new_nome = (nome or '').strip()
        new_email = (email or '').strip().lower()

        if not new_nome:
            return False, 'Nome é obrigatório.'
        if not new_email:
            return False, 'E-mail é obrigatório.'

        existing = User.query.filter(func.lower(User.email) == new_email, User.username != user.username).first()
        if existing:
            return False, 'E-mail já está em uso por outro usuário.'

        old_nome = user.nome
        old_email = user.email

        changed_fields = []
        if (old_nome or '') != new_nome:
            changed_fields.append({
                'label': 'Nome',
                'old': old_nome or '-',
                'new': new_nome,
            })

        old_email_normalized = (old_email or '').strip().lower()
        if old_email_normalized != new_email:
            changed_fields.append({
                'label': 'E-mail',
                'old': old_email or '-',
                'new': new_email,
            })

        if not changed_fields:
            return True, 'Nenhuma alteração detectada.'

        user.nome = new_nome
        user.email = new_email
        db.session.commit()

        if user.email and changed_fields:
            self.notifier.send_email_task(
                to_email=user.email,
                subject='Confirmação de atualização de perfil - EuroEventos',
                template_name='profile_updated.html',
                template_data={
                    'user_name': user.nome,
                    'changed_fields': changed_fields,
                    'changed_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'year': datetime.now().year,
                },
            )
        return True, 'Perfil atualizado com sucesso.'

    def change_password(self, user, current_password, new_password):
        if not current_password:
            return False, 'Informe a senha atual.'
        if not user.check_password(current_password):
            return False, 'Senha atual inválida.'
        if not new_password or len(new_password) < 6:
            return False, 'A nova senha deve ter pelo menos 6 caracteres.'

        user.set_password(new_password)
        db.session.commit()

        if user.email:
            self.notifier.send_email_task(
                to_email=user.email,
                subject='Confirmação de alteração de senha - EuroEventos',
                template_name='password_changed.html',
                template_data={
                    'user_name': user.nome,
                    'changed_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'year': datetime.now().year,
                },
            )
        return True, 'Senha alterada com sucesso.'
