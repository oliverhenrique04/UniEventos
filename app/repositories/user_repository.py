from app.models import User
from .base_repository import BaseRepository
from typing import Optional

class UserRepository(BaseRepository[User]):
    """
    Repository for User entity operations.
    """
    def __init__(self):
        super().__init__(User)

    def get_by_username(self, username: str) -> Optional[User]:
        """
        Retrieves a user by their username.
        
        Args:
            username (str): The username to search for.
            
        Returns:
            User: The user object or None.
        """
        return self.find_one_by(username=username)

    def get_by_cpf(self, cpf: str) -> Optional[User]:
        """
        Retrieves a user by their CPF.
        
        Args:
            cpf (str): The CPF to search for.
            
        Returns:
            User: The user object or None.
        """
        return self.find_one_by(cpf=cpf)
