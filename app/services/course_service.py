from app.models import Course
from app.repositories.course_repository import CourseRepository

class CourseService:
    """
    Service layer for Course management logic.
    """
    def __init__(self):
        self.course_repo = CourseRepository()

    def list_all(self):
        """Returns all courses ordered by name."""
        return self.course_repo.get_all_ordered()

    def create_course(self, data):
        """
        Creates a new course.
        Args:
            data (dict): {'nome': str}
        Returns:
            Course, str: The created course and a message, or None and error message.
        """
        nome = data.get('nome')
        if not nome:
            return None, "Nome do curso é obrigatório."
        
        if self.course_repo.get_by_name(nome):
            return None, "Curso já existe."
            
        course = Course(nome=nome)
        saved = self.course_repo.save(course)
        return saved, "Curso criado com sucesso."

    def update_course(self, course_id, data):
        """
        Updates an existing course.
        """
        course = self.course_repo.get(course_id)
        if not course:
            return None, "Curso não encontrado."
            
        nome = data.get('nome')
        if nome:
            existing = self.course_repo.get_by_name(nome)
            if existing and existing.id != course.id:
                return None, "Já existe um curso com este nome."
            course.nome = nome
            
        self.course_repo.update()
        return course, "Curso atualizado com sucesso."

    def delete_course(self, course_id):
        """
        Deletes a course.
        """
        if self.course_repo.delete(course_id):
            return True, "Curso removido com sucesso."
        return False, "Falha ao remover curso."
