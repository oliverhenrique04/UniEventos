from app.models import Course
from .base_repository import BaseRepository
from typing import Optional, List

class CourseRepository(BaseRepository[Course]):
    """
    Repository for Course entity operations.
    """
    def __init__(self):
        super().__init__(Course)

    def get_by_name(self, nome: str) -> Optional[Course]:
        """
        Retrieves a course by its name.
        """
        return self.find_one_by(nome=nome)

    def get_all_ordered(self) -> List[Course]:
        """
        Returns all courses ordered by name.
        """
        return Course.query.order_by(Course.nome).all()
