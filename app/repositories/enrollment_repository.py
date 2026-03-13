from app.models import Enrollment, Activity
from .base_repository import BaseRepository
from typing import Optional, List

class EnrollmentRepository(BaseRepository[Enrollment]):
    """
    Repository for Enrollment entity operations.
    """
    def __init__(self):
        super().__init__(Enrollment)

    def get_by_user_and_activity(self, user_cpf: str, activity_id: int) -> Optional[Enrollment]:
        """
        Retrieves a specific enrollment record.
        
        Args:
            user_cpf (str): The user's CPF.
            activity_id (int): The activity ID.
            
        Returns:
            Enrollment: The enrollment object or None.
        """
        return self.find_one_by(user_cpf=user_cpf, activity_id=activity_id)

    def get_confirmed_by_user_and_event(self, user_cpf: str, event_id: int) -> List[Enrollment]:
        """
        Retrieves confirmed enrollments for a user in an event.
        
        Args:
            user_cpf (str): The user's CPF.
            event_id (int): The event ID.
            
        Returns:
            List[Enrollment]: List of confirmed enrollments.
        """
        return self.model.query.join(Activity, Enrollment.activity_id == Activity.id).filter(
            Enrollment.user_cpf == user_cpf,
            Enrollment.presente == True,
            Activity.event_id == event_id,
        ).all()
