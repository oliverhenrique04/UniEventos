from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService

class AuthService:
    """
    Service layer for authentication and user management logic.
    """
    def __init__(self):
        self.user_repo = UserRepository()
        self.notifier = NotificationService()

    def authenticate_user(self, username, password):
        """
        Validates user credentials.
        
        Returns:
            User: The user object if credentials are valid, None otherwise.
        """
        user = self.user_repo.get_by_username(username)
        if user and user.check_password(password):
            return user
        return None

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
        if self.user_repo.get_by_username(data.get('username')):
            raise ValueError("Usuário já existe")
            
        user = User(
            username=data.get('username'),
            email=data.get('email'),
            role='participante',
            nome=data.get('nome'),
            cpf=data.get('cpf')
        )
        user.set_password(data.get('password'))
        saved_user = self.user_repo.save(user)
        
        # Send welcome email via RabbitMQ
        if saved_user.email:
            self.notifier.send_email_task(
                to_email=saved_user.email,
                subject="Bem-vindo ao UniEventos!",
                body=f"Olá {saved_user.nome}, seu cadastro foi realizado com sucesso. Aproveite os eventos!"
            )
        
        return saved_user
