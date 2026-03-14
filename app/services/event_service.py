from app.repositories.event_repository import EventRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.enrollment_repository import EnrollmentRepository
from app.services.notification_service import NotificationService
from app.models import Event, Activity, Enrollment, Course, User, db
import secrets
from datetime import datetime, date
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app.utils import normalize_cpf

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

    @staticmethod
    def _parse_date(value):
        if value in (None, ''):
            return None
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day') and not hasattr(value, 'hour'):
            return value
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_time(value):
        if value in (None, ''):
            return None
        if hasattr(value, 'hour') and hasattr(value, 'minute') and hasattr(value, 'second'):
            return value
        for fmt in ('%H:%M', '%H:%M:%S'):
            try:
                return datetime.strptime(str(value), fmt).time()
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _parse_fast_event_hours(value):
        raw = str(value).strip() if value is not None else ''
        if not raw:
            raise ValueError('Carga horária é obrigatória para Evento Rápido.')
        try:
            hours = int(raw)
        except (ValueError, TypeError):
            raise ValueError('Carga horária inválida para Evento Rápido.')
        if hours <= 0:
            raise ValueError('Carga horária do Evento Rápido deve ser maior que zero.')
        return hours

    @staticmethod
    def can_view_event(user, event):
        if not user or not event:
            return False
        if user.role == 'admin':
            return True
        if user.role == 'gestor':
            return True
        if user.role == 'professor':
            return event.owner_username == user.username
        if user.role == 'coordenador':
            return bool(user.course_id and event.course_id and user.course_id == event.course_id)
        return False

    @staticmethod
    def can_manage_event(user, event):
        if not user or not event:
            return False
        if user.role == 'admin':
            return True
        if user.role == 'professor':
            return event.owner_username == user.username
        if user.role == 'coordenador':
            return bool(user.course_id and event.course_id and user.course_id == event.course_id)
        if user.role == 'gestor':
            return bool(user.course_id and event.course_id and user.course_id == event.course_id)
        return False

    def create_event(self, owner_username, data):
        """Creates a new event and its associated activities."""
        is_rapido = bool(data.get('is_rapido'))
        fast_event_hours = self._parse_fast_event_hours(data.get('carga_horaria_rapida')) if is_rapido else None
        token = secrets.token_urlsafe(12)
        data_inicio = self._parse_date(data.get('data_inicio'))
        data_fim = self._parse_date(data.get('data_fim'))

        # Fast events must always have at least the creation date.
        if is_rapido and not data_inicio:
            data_inicio = date.today()
        if is_rapido and not data_fim:
            data_fim = data_inicio
        
        # Safe coordinate parsing
        try:
            lat = float(data.get('latitude')) if data.get('latitude') else None
            lon = float(data.get('longitude')) if data.get('longitude') else None
        except (ValueError, TypeError):
            lat, lon = None, None

        event = Event(
            owner_username=owner_username,
            nome=data.get('nome'),
            descricao=data.get('descricao'),
            curso=data.get('curso'),
            cert_bg_path='file/fundo_padrao.png',
            latitude=lat,
            longitude=lon,
            tipo='RAPIDO' if is_rapido else 'PADRAO',
            data_inicio=data_inicio,
            hora_inicio=self._parse_time(data.get('hora_inicio')),
            data_fim=data_fim,
            hora_fim=self._parse_time(data.get('hora_fim')),
            token_publico=token,
            status='ABERTO'
        )
        self.event_repo.save(event)
        
        if is_rapido:
            self._create_default_checkin_activity(event, fast_event_hours)
        else:
            self._create_activities(event, data.get('atividades', []))

        self._notify_owner_event_created(event)
            
        return event

    def _notify_owner_event_created(self, event):
        """Sends an email confirmation to the event owner when an event is created."""
        owner = User.query.filter_by(username=event.owner_username).first()
        if not owner or not owner.email:
            return

        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        event_link = f"{app_url}/inscrever/{event.token_publico}" if app_url else f"/inscrever/{event.token_publico}"
        manage_link = f"{app_url}/eventos_admin" if app_url else '/eventos_admin'
        event_date = event.data_inicio.strftime('%d/%m/%Y') if event.data_inicio else '-'
        event_time = event.hora_inicio.strftime('%H:%M') if event.hora_inicio else '-'

        self.notification_service.send_email_task(
            to_email=owner.email,
            subject=f"Evento criado: {event.nome}",
            template_name='event_created_owner.html',
            template_data={
                'user_name': owner.nome or owner.username,
                'event_name': event.nome,
                'event_type': event.tipo,
                'event_date': event_date,
                'event_time': event_time,
                'event_status': event.status,
                'event_link': event_link,
                'manage_link': manage_link,
                'year': datetime.now().year,
            },
        )

    def _notify_owner_event_updated(self, event):
        """Sends an email confirmation to the event owner when an event is updated."""
        owner = User.query.filter_by(username=event.owner_username).first()
        if not owner or not owner.email:
            return

        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        event_link = f"{app_url}/editar_evento/{event.id}" if app_url else f"/editar_evento/{event.id}"
        manage_link = f"{app_url}/eventos_admin" if app_url else '/eventos_admin'
        event_date = event.data_inicio.strftime('%d/%m/%Y') if event.data_inicio else '-'
        event_time = event.hora_inicio.strftime('%H:%M') if event.hora_inicio else '-'

        self.notification_service.send_email_task(
            to_email=owner.email,
            subject=f"Evento atualizado: {event.nome}",
            template_name='event_updated_owner.html',
            template_data={
                'user_name': owner.nome or owner.username,
                'event_name': event.nome,
                'event_type': event.tipo,
                'event_date': event_date,
                'event_time': event_time,
                'event_status': event.status,
                'event_link': event_link,
                'manage_link': manage_link,
                'changed_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'year': datetime.now().year,
            },
        )

    def _notify_owner_event_deleted(self, owner_username, event_name, event_type, event_date, event_time):
        """Sends an email confirmation to the event owner when an event is deleted."""
        owner = User.query.filter_by(username=owner_username).first()
        if not owner or not owner.email:
            return

        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        manage_link = f"{app_url}/eventos_admin" if app_url else '/eventos_admin'

        self.notification_service.send_email_task(
            to_email=owner.email,
            subject=f"Evento excluído: {event_name}",
            template_name='event_deleted_owner.html',
            template_data={
                'user_name': owner.nome or owner.username,
                'event_name': event_name,
                'event_type': event_type,
                'event_date': event_date,
                'event_time': event_time,
                'manage_link': manage_link,
                'changed_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'year': datetime.now().year,
            },
        )

    def update_event(self, event_id, user, data):
        """Updates an existing event's information and its associated activities.
        
        Args:
            event_id (int): ID of the event to update.
            user (User): Current authenticated user attempting the update.
            data (dict): Dictionary containing the updated event data.
            
        Returns:
            tuple: (Updated event object or None, success/error message).
        """
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return None, "Evento não encontrado"
            
        # Security check: Only the owner or an admin can modify an event.
        if not self.can_manage_event(user, event):
            return None, "Sem permissão para editar este evento"

        is_rapido = bool(data.get('is_rapido'))
        fast_event_hours = self._parse_fast_event_hours(data.get('carga_horaria_rapida')) if is_rapido else None
            
        # Safe coordinate parsing to prevent crashes on invalid input
        try:
            lat = float(data.get('latitude')) if data.get('latitude') else None
            lon = float(data.get('longitude')) if data.get('longitude') else None
        except (ValueError, TypeError):
            lat, lon = None, None

        # Update basic event fields
        event.nome = data.get('nome', event.nome)
        event.descricao = data.get('descricao', event.descricao)
        event.curso = data.get('curso', event.curso)
        event.latitude = lat
        event.longitude = lon
        event.data_inicio = self._parse_date(data.get('data_inicio', event.data_inicio))
        event.hora_inicio = self._parse_time(data.get('hora_inicio', event.hora_inicio))
        event.data_fim = self._parse_date(data.get('data_fim', event.data_fim))
        event.hora_fim = self._parse_time(data.get('hora_fim', event.hora_fim))
        
        # Non-destructive activity synchronization
        if 'atividades' in data or is_rapido:
            if is_rapido:
                # For fast events, check if default activity exists before recreating
                has_checkin = any(a.nome == "Check-in Presença" for a in event.activities)
                if not has_checkin:
                    # Only clear if changing from PADRAO to RAPIDO
                    for activity in event.activities:
                        self.activity_repo.delete(activity)
                    self._create_default_checkin_activity(event, fast_event_hours)
                else:
                    # Update existing check-in activity with new event details
                    checkin = next(a for a in event.activities if a.nome == "Check-in Presença")
                    checkin.data_atv = event.data_inicio
                    checkin.hora_atv = event.hora_inicio
                    checkin.carga_horaria = fast_event_hours
                    checkin.latitude = event.latitude
                    checkin.longitude = event.longitude
                    self.activity_repo.save(checkin)
            else:
                self._sync_activities(event, data.get('atividades', []))
            
        self.event_repo.save(event)
        self._notify_owner_event_updated(event)
        return event, "Evento atualizado com sucesso!"

    def _sync_activities(self, event, activities_data):
        """Synchronizes activities without losing existing enrollments.
        
        Updates existing activities, creates new ones, and removes missing ones.
        """
        existing_ids = {a.id: a for a in event.activities}
        incoming_ids = set()
        
        for atv_data in activities_data:
            atv_id = atv_data.get('id')
            
            # Safe numeric parsing
            try:
                horas = int(atv_data.get('horas', 0)) if atv_data.get('horas') else 0
                vagas = int(atv_data.get('vagas', -1)) if atv_data.get('vagas') else -1
            except (ValueError, TypeError):
                horas, vagas = 0, -1

            if atv_id and int(atv_id) in existing_ids:
                # Update existing activity
                activity = existing_ids[int(atv_id)]
                activity.nome = atv_data['nome']
                activity.palestrante = atv_data['palestrante']
                activity.local = atv_data['local']
                activity.descricao = atv_data.get('descricao', '')
                activity.data_atv = self._parse_date(atv_data.get('data_atv'))
                activity.hora_atv = self._parse_time(atv_data.get('hora_atv'))
                activity.carga_horaria = horas
                activity.vagas = vagas
                activity.latitude = event.latitude
                activity.longitude = event.longitude
                self.activity_repo.save(activity)
                incoming_ids.add(int(atv_id))
            else:
                # Create new activity
                new_atv = Activity(
                    event_id=event.id,
                    nome=atv_data['nome'],
                    palestrante=atv_data['palestrante'],
                    local=atv_data['local'],
                    descricao=atv_data.get('descricao', ''),
                    data_atv=self._parse_date(atv_data.get('data_atv')),
                    hora_atv=self._parse_time(atv_data.get('hora_atv')),
                    carga_horaria=horas,
                    vagas=vagas,
                    latitude=event.latitude,
                    longitude=event.longitude
                )
                self.activity_repo.save(new_atv)
        
        # Remove activities that are no longer in the list
        for aid, activity in existing_ids.items():
            if aid not in incoming_ids:
                # Warning: This will still delete enrollments due to cascade.
                # However, it only happens if the user explicitly removes the activity from the UI.
                self.activity_repo.delete(activity)

    def get_events_for_user_paginated(self, user, page=1, per_page=12, filters=None):
        """Lists events visible to a specific user with chronological sorting and filters."""
        query = Event.query
        if user.role == 'participante':
            query = query.filter(Event.status == 'ABERTO')
        elif user.role == 'professor':
            query = query.filter_by(owner_username=user.username)
        elif user.role == 'coordenador':
            if user.course_id:
                query = query.filter(Event.course_id == user.course_id)
            else:
                query = query.filter(Event.id == -1)
        elif user.role == 'gestor':
            # Gestor can consult events across courses.
            pass
        elif user.role != 'admin':
            query = query.filter(Event.id == -1)
        
        if filters:
            if filters.get('nome'):
                query = query.filter(Event.nome.ilike(f"%{filters['nome']}%"))
            if filters.get('data'):
                parsed_date = self._parse_date(filters['data'])
                if parsed_date:
                    query = query.filter(Event.data_inicio == parsed_date)
            if filters.get('curso'):
                query = query.join(Course, Event.course_id == Course.id, isouter=True)
                query = query.filter(Course.nome.ilike(f"%{filters['curso']}%"))

        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def list_events_paginated(self, user, page=1, per_page=10, filters=None):
        """Retrieves a paginated list of events with chronological sorting and filters."""
        query = Event.query

        if user.role == 'professor':
            query = query.filter(Event.owner_username == user.username)
        elif user.role == 'coordenador':
            if user.course_id:
                query = query.filter(Event.course_id == user.course_id)
            else:
                query = query.filter(Event.id == -1)
        elif user.role == 'gestor':
            # Gestor can consult all events; edition constraints are enforced elsewhere.
            pass
        elif user.role != 'admin':
            query = query.filter(Event.id == -1)

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
                query = query.join(Course, Event.course_id == Course.id, isouter=True)
                query = query.filter(Course.nome.ilike(f"%{filters['curso']}%"))
            if filters.get('data'):
                parsed_date = self._parse_date(filters['data'])
                if parsed_date:
                    query = query.filter(Event.data_inicio == parsed_date)

        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_event_participants_paginated(self, event_id, page=1, per_page=10, filters=None):
        """Retrieves a paginated list of participants enrolled in an event."""
        query = Enrollment.query.join(Activity, Enrollment.activity_id == Activity.id).filter(Activity.event_id == event_id)
        if filters:
            if filters.get('nome'):
                query = query.filter(Enrollment.nome.ilike(f"%{filters['nome']}%"))
            if filters.get('cpf'):
                    cpf_digits = normalize_cpf(filters['cpf'])
                    if cpf_digits:
                        query = query.filter(Enrollment.user_cpf.ilike(f"%{cpf_digits}%"))
            if filters.get('activity_id'):
                query = query.filter(Enrollment.activity_id == filters['activity_id'])
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

    def notify_all_participants(self, event_id, subject, body):
        """Sends a broadcast email to all unique participants of an event.
        
        Uses RabbitMQ for asynchronous processing of email tasks.
        """
        from app.models import User
        # Get unique user CPFs enrolled in any activity of this event
        enrollments = Enrollment.query.join(Activity, Enrollment.activity_id == Activity.id).filter(Activity.event_id == event_id).all()
        cpfs = set([e.user_cpf for e in enrollments])
        
        count = 0
        event = self.event_repo.get_by_id(event_id)
        event_name = event.nome if event else 'Evento'
        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        for cpf in cpfs:
            user = User.query.filter_by(cpf=cpf).first()
            if user and user.email:
                self.notification_service.send_email_task(
                    to_email=user.email,
                    subject=subject,
                    template_name='event_broadcast.html',
                    template_data={
                        'subject': subject,
                        'event_name': event_name,
                        'user_name': user.nome,
                        'message_text': body,
                        'app_url': app_url,
                    },
                )
                count += 1
        return count

    def get_event_by_id(self, event_id):
        return self.event_repo.get_by_id(event_id)

    def delete_event(self, event_id, user):
        event = self.event_repo.get_by_id(event_id)
        if not event: return False, "Evento não encontrado"
        if not self.can_manage_event(user, event):
            return False, "Permissão negada"

        event_name = event.nome
        event_type = event.tipo
        event_date = event.data_inicio.strftime('%d/%m/%Y') if event.data_inicio else '-'
        event_time = event.hora_inicio.strftime('%H:%M') if event.hora_inicio else '-'
        event_owner = event.owner_username

        self.event_repo.delete(event)
        self._notify_owner_event_deleted(event_owner, event_name, event_type, event_date, event_time)
        return True, "Evento removido com sucesso."

    def get_activity(self, activity_id):
        return self.activity_repo.get_by_id(activity_id)

    def get_enrollment(self, activity_id, user_cpf):
        return self.enrollment_repo.get_by_user_and_activity(user_cpf, activity_id)

    def toggle_enrollment(self, user, activity_id, action):
        """Handles user enrollment and disenrollment logic."""
        activity = self.activity_repo.get_by_id(activity_id)
        if not activity: return None, "Atividade não encontrada"
        existing = self.get_enrollment(activity_id, user.cpf)

        if action == 'inscrever':
            if existing: return existing, "Já inscrito"
            current_count = len(activity.enrollments)
            if activity.vagas != -1 and current_count >= activity.vagas:
                return None, "Lotado!"
            
            enrollment = Enrollment(activity_id=activity_id, user_cpf=user.cpf, nome=user.nome, presente=False)
            try:
                saved = self.enrollment_repo.save(enrollment)
            except IntegrityError:
                # Covers concurrent insert attempts after uniqueness hardening.
                existing = self.get_enrollment(activity_id, user.cpf)
                if existing:
                    return existing, "Já inscrito"
                raise
            if user.email:
                app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
                event_date = activity.event.data_inicio.strftime('%d/%m/%Y') if activity.event and activity.event.data_inicio else ''
                event_time = activity.hora_atv.strftime('%H:%M') if activity.hora_atv else ''
                self.notification_service.send_email_task(
                    to_email=user.email,
                    subject=f"Inscrição Confirmada: {activity.nome}",
                    template_name='enrollment_confirmation.html',
                    template_data={
                        'user_name': user.nome,
                        'event_name': activity.event.nome if activity.event else activity.nome,
                        'event_date': event_date,
                        'event_time': event_time,
                        'event_location': activity.local or '-',
                        'event_type': 'Atividade',
                        'event_description': activity.descricao or '',
                        'event_details_url': app_url,
                        'my_events_url': f"{app_url}/meus-eventos" if app_url else '',
                        'cancel_url': '',
                    },
                )
            return saved, "Inscrição Realizada!"
        elif action == 'sair':
            if existing: self.enrollment_repo.delete(existing)
            return None, "Desinscrição realizada."
        return None, "Ação inválida"

    def confirm_attendance(self, user, activity_id, event_id, lat=None, lon=None):
        activity = self.get_activity(activity_id)
        if not activity: return False, "Atividade não encontrada", None
        enrollment = self.get_enrollment(activity_id, user.cpf)

        if not enrollment:
            if activity.nome == "Check-in Presença":
                enrollment = Enrollment(activity_id=activity_id, user_cpf=user.cpf, nome=user.nome, presente=True, lat_checkin=lat, lon_checkin=lon)
                self.enrollment_repo.save(enrollment)
            else:
                return False, "Você não se inscreveu nesta atividade.", None
        else:
            enrollment.presente = True
            enrollment.lat_checkin = lat
            enrollment.lon_checkin = lon
            self.enrollment_repo.save(enrollment)

        if user.email:
            app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
            self.notification_service.send_email_task(
                to_email=user.email,
                subject=f"Presença Confirmada: {activity.nome}",
                template_name='presence_confirmation.html',
                template_data={
                    'user_name': user.nome,
                    'event_name': activity.event.nome if activity.event else '-',
                    'activity_name': activity.nome,
                    'app_url': f"{app_url}/meus-eventos" if app_url else '',
                },
            )
        return True, "Presença confirmada!", enrollment

    def get_user_events_paginated(self, user_cpf, page=1, per_page=10, filters=None):
        query = Event.query.join(Activity, Event.id == Activity.event_id).join(Enrollment, Enrollment.activity_id == Activity.id).filter(Enrollment.user_cpf == user_cpf).distinct()
        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_user_activities_paginated(self, user_cpf, page=1, per_page=10):
        query = Enrollment.query.filter_by(user_cpf=user_cpf).join(Activity)
        return query.order_by(Activity.data_atv.asc(), Activity.hora_atv.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_user_certificates_paginated(self, user_cpf, page=1, per_page=12):
        query = Enrollment.query.filter_by(user_cpf=user_cpf, presente=True).filter(Enrollment.cert_hash.isnot(None)).join(Activity)
        return query.order_by(Activity.data_atv.asc(), Activity.hora_atv.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def _create_default_checkin_activity(self, event, workload_hours):
        activity = Activity(event_id=event.id, nome="Check-in Presença", palestrante="", local="", descricao="Registro de presença.", data_atv=event.data_inicio, hora_atv=event.hora_inicio, carga_horaria=workload_hours, vagas=-1, latitude=event.latitude, longitude=event.longitude)
        self.activity_repo.save(activity)

    def _create_activities(self, event, activities_data):
        for atv in activities_data:
            # Safe numeric parsing for activities
            try:
                horas = int(atv.get('horas', 0)) if atv.get('horas') else 0
            except (ValueError, TypeError):
                horas = 0
                
            try:
                vagas = int(atv.get('vagas', -1)) if atv.get('vagas') else -1
            except (ValueError, TypeError):
                vagas = -1

            activity = Activity(event_id=event.id, nome=atv['nome'], palestrante=atv['palestrante'], local=atv['local'], descricao=atv.get('descricao', ''), data_atv=self._parse_date(atv.get('data_atv')), hora_atv=self._parse_time(atv.get('hora_atv')), carga_horaria=horas, vagas=vagas, latitude=event.latitude, longitude=event.longitude)
            self.activity_repo.save(activity)
