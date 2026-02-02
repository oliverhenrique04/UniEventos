from app.models import Event
from .base_repository import BaseRepository
from typing import List, Optional

class EventRepository(BaseRepository[Event]):
    """
    Repository for Event entity operations.
    """
    def __init__(self):
        super().__init__(Event)

    def get_by_owner(self, owner_username: str) -> List[Event]:
        """
        Retrieves all events owned by a specific user.
        
        Args:
            owner_username (str): The owner's username.
            
        Returns:
            List[Event]: List of events.
        """
        return self.find_by(owner_username=owner_username)

    def get_by_token(self, token: str) -> Optional[Event]:
        """
        Retrieves an event by its public token.
        
        Args:
            token (str): The public token.
            
        Returns:
            Event: The event object or None.
        """
        return self.find_one_by(token_publico=token)
