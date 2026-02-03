from app.repositories.event_repository import EventRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.enrollment_repository import EnrollmentRepository
from app.services.notification_service import NotificationService
from app.models import Event, Activity, Enrollment, db
import secrets

class EventService:
    """
    Service layer for managing events, activities, and enrollments.
    Encapsulates business logic and orquestrates repository calls.
    """
    def __init__(self):
        self.event_repo = EventRepository()
        self.activity_repo = ActivityRepository()
        self.enrollment_repo = EnrollmentRepository()
        self.notification_service = NotificationService()

    def create_event(self, owner_username, data):
        """Creates a new event and its associated activities."""
        is_rapido = data.get('is_rapido')
        token = secrets.token_urlsafe(12)
        
        event = Event(
            owner_username=owner_username,
            nome=data.get('nome'),
            descricao=data.get('descricao'),
            curso=data.get('curso'),
            tipo='RAPIDO' if is_rapido else 'PADRAO',
            data_inicio=data.get('data_inicio'),
            hora_inicio=data.get('hora_inicio'),
            data_fim=data.get('data_fim'),
            hora_fim=data.get('hora_fim'),
            token_publico=token,
            status='ABERTO'
        )
        self.event_repo.save(event)
        
        if is_rapido:
            self._create_default_checkin_activity(event)
        else:
            self._create_activities(event, data.get('atividades', []))
            
        return event

    def update_event(self, event_id, owner_username, role, data):
        """Updates an existing event and its activities."""
        event = self.event_repo.get_by_id(event_id)
        if not event: return None, "Evento não encontrado"
            
        if role != 'admin' and event.owner_username != owner_username:
            return None, "Sem permissão"
            
        event.nome = data.get('nome')
        event.descricao = data.get('descricao')
        event.curso = data.get('curso')
        event.data_inicio = data.get('data_inicio')
        event.hora_inicio = data.get('hora_inicio')
        event.data_fim = data.get('data_fim')
        event.hora_fim = data.get('hora_fim')
        
        for activity in event.activities:
            self.activity_repo.delete(activity)
            
        self._create_activities(event, data.get('atividades', []))
        self.event_repo.save(event)
        return event, "Atualizado!"

    def get_events_for_user_paginated(self, user, page=1, per_page=10, filters=None):
        """Lists events visible to a specific user with chronological sorting and filters."""
        query = Event.query
        if user.role not in ['admin', 'participante']:
            query = query.filter_by(owner_username=user.username)
        
        if filters:
            if filters.get('nome'):
                query = query.filter(Event.nome.ilike(f"%{filters['nome']}%"))
            if filters.get('data'):
                query = query.filter(Event.data_inicio == filters['data'])
            if filters.get('curso'):
                query = query.filter(Event.curso.ilike(f"%{filters['curso']}%"))

        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def list_events_paginated(self, page=1, per_page=10, filters=None):
        """Retrieves a paginated list of events with chronological sorting and filters."""
        query = Event.query
        if filters:
            if filters.get('nome'):
                query = query.filter(Event.nome.ilike(f"%{filters['nome']}%"))
            if filters.get('tipo'):
                query = query.filter(Event.tipo == filters['tipo'])
            if filters.get('status'):
                query = query.filter(Event.status == filters['status'])
            if filters.get('owner'):
                query = query.filter(Event.owner_username.ilike(f"%{filters['owner']}%"))
            if filters.get('curso'):
                query = query.filter(Event.curso.ilike(f"%{filters['curso']}%"))
            if filters.get('data'):
                query = query.filter(Event.data_inicio == filters['data'])

        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_event_participants_paginated(self, event_id, page=1, per_page=10, filters=None):
        """Retrieves a paginated list of participants enrolled in an event."""
        query = Enrollment.query.filter_by(event_id=event_id)
        if filters:
            if filters.get('nome'):
                query = query.filter(Enrollment.nome.ilike(f"%{filters['nome']}%"))
            if filters.get('cpf'):
                query = query.filter(Enrollment.user_cpf.ilike(f"%{filters['cpf']}%"))
            if filters.get('presente') is not None:
                query = query.filter(Enrollment.presente == filters['presente'])

        return query.paginate(page=page, per_page=per_page, error_out=False)

    def toggle_attendance_manual(self, enrollment_id, status):
        """Manually forces the attendance status of a participant."""
        enrollment = self.enrollment_repo.get_by_id(enrollment_id)
        if not enrollment: return False, "Matrícula não encontrada"
        enrollment.presente = status
        self.enrollment_repo.save(enrollment)
        return True, "Presença atualizada com sucesso!"

    def get_event_by_id(self, event_id):
        return self.event_repo.get_by_id(event_id)

    def delete_event(self, event_id, owner_username, role):
        event = self.event_repo.get_by_id(event_id)
        if not event: return False, "Evento não encontrado"
        if role != 'admin' and event.owner_username != owner_username:
            return False, "Permissão negada"
        self.event_repo.delete(event)
        return True, "Evento removido com sucesso."

    def get_activity(self, activity_id):
        return self.activity_repo.get_by_id(activity_id)

    def get_enrollment(self, activity_id, user_cpf):
        return self.enrollment_repo.get_by_user_and_activity(user_cpf, activity_id)

    def toggle_enrollment(self, user, activity_id, action):
        """
        Handles user enrollment and disenrollment logic.
        """
        activity = self.activity_repo.get_by_id(activity_id)
        if not activity: return None, "Atividade não encontrada"

        existing = self.enrollment_repo.get_by_user_and_activity(user.cpf, activity_id)

        if action == 'inscrever':
            if existing: return existing, "Já inscrito"
            
            # Check capacity
            current_count = len(activity.enrollments)
            if activity.vagas != -1 and current_count >= activity.vagas:
                return None, "Lotado!"
            
            enrollment = Enrollment(
                activity_id=activity_id,
                event_id=activity.event_id,
                user_cpf=user.cpf,
                nome=user.nome,
                presente=False
            )
            saved = self.enrollment_repo.save(enrollment)
            
            # Notify on enrollment
            if user.email:
                self.notification_service.send_email_task(
                    user.email,
                    f"Inscrição Confirmada: {activity.nome}",
                    f"Olá {user.nome}, sua inscrição na atividade {activity.nome} do evento {activity.event.nome} foi confirmada!"
                )
            
            return saved, "Inscrição Realizada!"

        elif action == 'sair':
            if existing: self.enrollment_repo.delete(existing)
            return None, "Desinscrição realizada."
        
        return None, "Ação inválida"

    def confirm_attendance(self, user, activity_id, event_id):
        activity = self.get_activity(activity_id)
        if not activity: return False, "Atividade não encontrada", None
        enrollment = self.get_enrollment(activity_id, user.cpf)

        if not enrollment:
            if activity.nome == "Check-in Presença":
                enrollment = Enrollment(activity_id=activity_id, event_id=event_id, user_cpf=user.cpf, nome=user.nome, presente=True)
                self.enrollment_repo.save(enrollment)
            else:
                return False, "Você não se inscreveu nesta atividade.", None
        else:
            enrollment.presente = True
            self.enrollment_repo.save(enrollment)

        if user.email:
            self.notification_service.send_email_task(user.email, f"Presença Confirmada: {activity.nome}", f"Parabéns {user.nome}! Sua presença na atividade {activity.nome} foi registrada com sucesso.")
        return True, "Presença confirmada!", enrollment

    def get_user_events_paginated(self, user_cpf, page=1, per_page=10):
        query = Event.query.join(Enrollment, Event.id == Enrollment.event_id).filter(Enrollment.user_cpf == user_cpf).distinct()
        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_user_activities_paginated(self, user_cpf, page=1, per_page=10):
        query = Enrollment.query.filter_by(user_cpf=user_cpf).join(Activity)
        return query.order_by(Activity.data_atv.asc(), Activity.hora_atv.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_user_certificates_paginated(self, user_cpf, page=1, per_page=10):
        query = Enrollment.query.filter_by(user_cpf=user_cpf, presente=True).join(Activity)
        return query.order_by(Activity.data_atv.asc(), Activity.hora_atv.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def _create_default_checkin_activity(self, event):
        activity = Activity(event_id=event.id, nome="Check-in Presença", palestrante="", local="", descricao="Registro de presença.", data_atv=event.data_inicio, hora_atv=event.hora_inicio, carga_horaria=0, vagas=-1)
        self.activity_repo.save(activity)

    def _create_activities(self, event, activities_data):
        for atv in activities_data:
            activity = Activity(event_id=event.id, nome=atv['nome'], palestrante=atv['palestrante'], local=atv['local'], descricao=atv.get('descricao', ''), data_atv=atv.get('data_atv'), hora_atv=atv.get('hora_atv'), carga_horaria=int(atv.get('horas', 0)), vagas=int(atv.get('vagas', -1)))
            self.activity_repo.save(activity)