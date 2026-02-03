from app.repositories.event_repository import EventRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.user_repository import UserRepository

class ReportService:
    """Service layer for generating reports and certificates.
    
    This service orchestrates data retrieval for administrative reports
    and academic certificates, ensuring all business rules for 
    certification (e.g., minimum attendance) are respected.
    """
    def __init__(self):
        self.event_repo = EventRepository()
        self.activity_repo = ActivityRepository()
        self.user_repo = UserRepository()

    def get_event_enrollment_report_paginated(self, event_id: int, page=1, per_page=15, filter_nome=None):
        """Generates a paginated report of all enrollments for an event with eager loading."""
        from app.models import Enrollment, Activity
        from sqlalchemy.orm import joinedload
        
        query = Enrollment.query.filter(Enrollment.event_id == event_id).options(joinedload(Enrollment.activity))
        
        if filter_nome:
            query = query.filter(Enrollment.nome.ilike(f"%{filter_nome}%"))
            
        # Order by Activity name then Participant name
        query = query.join(Activity, Enrollment.activity_id == Activity.id).order_by(Activity.nome.asc(), Enrollment.nome.asc())
        
        return query.paginate(page=page, per_page=per_page, error_out=False)

    def get_event_enrollment_report(self, event_id: int):
        """Generates a structured report of enrollments for a specific event.
        
        Args:
            event_id (int): The unique identifier of the event.
            
        Returns:
            list: A list of dictionaries containing activity details and participant lists.
                  Returns None if the event is not found.
        """
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return None
        
        relatorio = []
        for atv in event.activities:
            inscritos = []
            for enroll in atv.enrollments:
                inscritos.append({
                    "nome": enroll.nome,
                    "cpf": enroll.user_cpf,
                    "presente": enroll.presente
                })
            relatorio.append({"atividade": atv.nome, "inscritos": inscritos})
            
        return relatorio

    def get_certificate_data(self, event_id: int, user_cpf: str):
        """Retrieves and calculates data necessary for academic certificate generation.
        
        Args:
            event_id (int): The unique identifier of the event.
            user_cpf (str): The participant's CPF.
            
        Returns:
            dict: A dictionary containing event metadata, user info, verified activities,
                  and calculated total workload. Returns None if requirements aren't met.
        """
        event = self.event_repo.get_by_id(event_id)
        user = self.user_repo.get_by_cpf(user_cpf)
        
        if not event or not user:
            return None
            
        activities = self.activity_repo.get_completed_by_event_and_user(event_id, user_cpf)
        
        if not activities:
            return None
            
        total_hours = sum([a.carga_horaria for a in activities])
        
        return {
            "event": event,
            "user": user,
            "activities": activities,
            "total_hours": total_hours
        }
