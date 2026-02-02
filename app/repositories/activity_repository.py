from app.models import Activity, Enrollment
from .base_repository import BaseRepository
from typing import List

class ActivityRepository(BaseRepository[Activity]):
    """
    Repository for Activity entity operations.
    """
    def __init__(self):
        super().__init__(Activity)

    def get_completed_by_event_and_user(self, event_id: int, user_cpf: str) -> List[Activity]:
        """
        Retrieves all activities for a specific event that a user has attended.
        """
        return self.model.query.join(Enrollment).filter(
            Enrollment.user_cpf == user_cpf,
            Enrollment.presente == True,
            Enrollment.event_id == event_id
        ).all()
