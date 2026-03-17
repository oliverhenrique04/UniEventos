from app.repositories.event_repository import EventRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.enrollment_repository import EnrollmentRepository
from app.services.notification_service import NotificationService
from app.models import (
    Activity,
    ActivitySpeaker,
    Course,
    DEFAULT_EVENT_ALLOWED_ROLES,
    DEFAULT_EVENT_REGISTRATION_CATEGORY_NAME,
    Enrollment,
    Event,
    EventAllowedRole,
    EventRegistration,
    EventRegistrationCategory,
    User,
    db,
)
import secrets
from datetime import datetime, date
from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
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
    def _normalize_optional_email(value):
        raw = str(value or '').strip()
        return raw or None

    def _normalize_speakers_payload(self, activity_data):
        payload = []
        raw_speakers = activity_data.get('palestrantes')

        if isinstance(raw_speakers, list):
            for idx, item in enumerate(raw_speakers):
                if not isinstance(item, dict):
                    continue

                speaker_name = str(item.get('nome') or '').strip() or None
                speaker_email = self._normalize_optional_email(item.get('email'))
                if not speaker_name and not speaker_email:
                    continue

                try:
                    order = int(item.get('ordem')) if item.get('ordem') is not None and str(item.get('ordem')).strip() != '' else idx
                except (TypeError, ValueError):
                    order = idx

                payload.append({
                    'nome': speaker_name,
                    'email': speaker_email,
                    'ordem': order,
                })

        if payload:
            payload.sort(key=lambda item: (item.get('ordem', 0), str(item.get('nome') or '').lower()))
            return payload

        legacy_name = str(activity_data.get('palestrante') or '').strip() or None
        legacy_email = self._normalize_optional_email(activity_data.get('email_palestrante'))
        if legacy_name or legacy_email:
            return [{
                'nome': legacy_name,
                'email': legacy_email,
                'ordem': 0,
            }]

        return []

    def _sync_activity_speakers(self, activity, activity_data):
        normalized_speakers = self._normalize_speakers_payload(activity_data or {})
        activity.speakers.clear()

        for idx, speaker in enumerate(normalized_speakers):
            activity.speakers.append(ActivitySpeaker(
                nome=speaker.get('nome'),
                email=speaker.get('email'),
                ordem=int(speaker.get('ordem', idx) or 0),
            ))

        activity.sync_legacy_speaker_fields()

    @staticmethod
    def _normalize_allowed_roles_payload(raw_roles, default_if_missing=False):
        if raw_roles is None:
            return list(DEFAULT_EVENT_ALLOWED_ROLES) if default_if_missing else None

        normalized = []
        seen = set()
        for raw_role in raw_roles:
            role = str(raw_role or '').strip().lower()
            if not role:
                continue
            if role not in DEFAULT_EVENT_ALLOWED_ROLES:
                raise ValueError(f'Perfil de inscrição inválido: {role}.')
            if role not in seen:
                seen.add(role)
                normalized.append(role)

        if not normalized:
            raise ValueError('Selecione ao menos um perfil habilitado para inscrição.')

        return [role for role in DEFAULT_EVENT_ALLOWED_ROLES if role in seen]

    @staticmethod
    def _normalize_category_quota(value):
        raw = str(value).strip() if value is not None else ''
        if not raw:
            return -1

        try:
            vagas = int(raw)
        except (TypeError, ValueError):
            raise ValueError('Quantidade de vagas inválida para a categoria de inscrição.')

        if vagas == -1:
            return -1
        if vagas <= 0:
            raise ValueError('A quantidade de vagas da categoria deve ser maior que zero ou ilimitada.')
        return vagas

    def _normalize_registration_categories_payload(self, raw_categories, default_if_missing=False):
        if raw_categories is None:
            if not default_if_missing:
                return None
            raw_categories = [{'nome': DEFAULT_EVENT_REGISTRATION_CATEGORY_NAME, 'vagas': -1, 'ordem': 0}]

        normalized = []
        seen = set()
        for idx, raw_category in enumerate(raw_categories):
            if not isinstance(raw_category, dict):
                continue

            nome = str(raw_category.get('nome') or '').strip()
            if not nome:
                continue

            normalized_name = nome.casefold()
            if normalized_name in seen:
                raise ValueError(f'A categoria de inscrição "{nome}" está duplicada.')
            seen.add(normalized_name)

            try:
                category_id = int(raw_category.get('id')) if raw_category.get('id') not in (None, '') else None
            except (TypeError, ValueError):
                category_id = None

            normalized.append({
                'id': category_id,
                'nome': nome,
                'vagas': self._normalize_category_quota(raw_category.get('vagas', -1)),
                'ordem': idx,
            })

        if not normalized:
            raise ValueError('Cadastre ao menos uma categoria de inscrição.')

        return normalized

    @staticmethod
    def get_event_allowed_roles(event):
        if not event:
            return list(DEFAULT_EVENT_ALLOWED_ROLES)
        if getattr(event, 'allowed_roles', None):
            roles = [item.role for item in event.allowed_roles if item.role]
            if roles:
                return roles
        return list(DEFAULT_EVENT_ALLOWED_ROLES)

    @staticmethod
    def can_self_enroll(user):
        if not user:
            return False
        if user.role in ['admin', 'extensao']:
            return True
        return bool(getattr(user, 'role', None) in DEFAULT_EVENT_ALLOWED_ROLES)

    def is_event_role_allowed_for_user(self, event, user):
        if not event or not user or not getattr(user, 'role', None):
            return False
        return user.role in set(self.get_event_allowed_roles(event))

    def ensure_event_registration_defaults(self, event):
        if not event:
            return event

        changed = False
        if not getattr(event, 'allowed_roles', None):
            for role in DEFAULT_EVENT_ALLOWED_ROLES:
                event.allowed_roles.append(EventAllowedRole(role=role))
            changed = True

        if not getattr(event, 'registration_categories', None):
            event.registration_categories.append(EventRegistrationCategory(
                nome=DEFAULT_EVENT_REGISTRATION_CATEGORY_NAME,
                vagas=-1,
                ordem=0,
            ))
            changed = True

        if changed:
            db.session.flush()

        return event

    def get_event_registration(self, event_id, user_cpf):
        normalized_cpf = normalize_cpf(user_cpf)
        if not normalized_cpf:
            return None
        return EventRegistration.query.filter_by(event_id=event_id, user_cpf=normalized_cpf).first()

    def get_event_registration_for_user(self, event, user):
        if not event or not user or not getattr(user, 'cpf', None):
            return None
        return self.get_event_registration(event.id, user.cpf)

    def user_has_event_enrollment(self, event_id, user_cpf):
        normalized_cpf = normalize_cpf(user_cpf)
        if not normalized_cpf:
            return False
        return (
            Enrollment.query
            .join(Activity, Enrollment.activity_id == Activity.id)
            .filter(Activity.event_id == event_id, Enrollment.user_cpf == normalized_cpf)
            .first()
            is not None
        )

    def get_event_category_occupancy(self, category):
        if not category or not getattr(category, 'id', None):
            return 0
        return (
            db.session.query(db.func.count(EventRegistration.id))
            .filter(EventRegistration.category_id == category.id)
            .scalar()
            or 0
        )

    def get_event_categories(self, event, ensure_defaults=False):
        if ensure_defaults:
            self.ensure_event_registration_defaults(event)

        categories = list(getattr(event, 'registration_categories', []) or [])
        if categories:
            return categories

        return [EventRegistrationCategory(
            id=None,
            event_id=getattr(event, 'id', None),
            nome=DEFAULT_EVENT_REGISTRATION_CATEGORY_NAME,
            vagas=-1,
            ordem=0,
        )]

    def resolve_registration_category(self, event, category_id=None, ensure_defaults=False):
        categories = self.get_event_categories(event, ensure_defaults=ensure_defaults)

        if category_id not in (None, ''):
            try:
                category_id = int(category_id)
            except (TypeError, ValueError):
                return None

            for category in categories:
                if category.id == category_id:
                    return category
            return None

        if len(categories) == 1:
            return categories[0]
        return None

    def can_user_access_open_event(self, user, event):
        if not user or not event:
            return False
        if user.role in ['admin', 'extensao']:
            return True
        if self.get_event_registration_for_user(event, user):
            return True
        if self.user_has_event_enrollment(event.id, user.cpf):
            return True
        return self.is_event_role_allowed_for_user(event, user)

    def can_user_start_event_registration(self, event, subject_user, actor_user=None):
        if not event or not subject_user:
            return False
        if self.get_event_registration_for_user(event, subject_user):
            return True
        if self.user_has_event_enrollment(event.id, subject_user.cpf):
            return True
        if actor_user and actor_user.username == subject_user.username and actor_user.role in ['admin', 'extensao']:
            return True
        return self.is_event_role_allowed_for_user(event, subject_user)

    def ensure_event_registration(self, event, subject_user, category_id=None, actor_user=None):
        if not event or not subject_user:
            return None, 'Evento ou usuário inválido.'

        self.ensure_event_registration_defaults(event)

        existing_registration = self.get_event_registration_for_user(event, subject_user)
        if existing_registration:
            return existing_registration, None

        if self.user_has_event_enrollment(event.id, subject_user.cpf):
            category = self.resolve_registration_category(event, category_id, ensure_defaults=True)
            if not category:
                category = self.resolve_registration_category(event, ensure_defaults=True)
            if not category:
                return None, 'Selecione uma categoria de inscrição.'

            registration = EventRegistration(
                event_id=event.id,
                user_cpf=subject_user.cpf,
                category_id=category.id,
            )
            saved_registration = db.session.merge(registration)
            db.session.flush()
            return saved_registration, None

        if not self.can_user_start_event_registration(event, subject_user, actor_user=actor_user):
            return None, 'Seu perfil não está habilitado para este evento.'

        category = self.resolve_registration_category(event, category_id, ensure_defaults=True)
        if category_id not in (None, '') and not category:
            return None, 'Categoria de inscrição inválida.'
        if not category:
            return None, 'Selecione uma categoria de inscrição.'

        occupancy = self.get_event_category_occupancy(category)
        if category.vagas != -1 and occupancy >= category.vagas:
            return None, 'Categoria de inscrição lotada.'

        registration = EventRegistration(
            event_id=event.id,
            user_cpf=subject_user.cpf,
            category_id=category.id,
        )
        db.session.add(registration)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            existing_registration = self.get_event_registration(event.id, subject_user.cpf)
            if existing_registration:
                return existing_registration, None
            raise

        return registration, None

    def cleanup_event_registration_if_empty(self, event, user):
        if not event or not user or not getattr(user, 'cpf', None):
            return

        registration = self.get_event_registration_for_user(event, user)
        if not registration:
            return

        remaining_enrollments = (
            Enrollment.query
            .join(Activity, Enrollment.activity_id == Activity.id)
            .filter(Activity.event_id == event.id, Enrollment.user_cpf == user.cpf)
            .count()
        )
        if remaining_enrollments == 0:
            db.session.delete(registration)
            db.session.commit()

    def _sync_event_allowed_roles(self, event, allowed_roles):
        current_roles = {item.role: item for item in event.allowed_roles}
        incoming_roles = set(allowed_roles or [])

        for role, role_obj in current_roles.items():
            if role not in incoming_roles:
                db.session.delete(role_obj)

        for role in DEFAULT_EVENT_ALLOWED_ROLES:
            if role in incoming_roles and role not in current_roles:
                event.allowed_roles.append(EventAllowedRole(role=role))

    def _sync_event_registration_categories(self, event, categories_data):
        existing_categories = {category.id: category for category in event.registration_categories if category.id}
        incoming_ids = set()

        for position, category_data in enumerate(categories_data):
            category_id = category_data.get('id')
            nome = category_data.get('nome')
            vagas = category_data.get('vagas', -1)

            if category_id and category_id in existing_categories:
                category = existing_categories[category_id]
                occupancy = self.get_event_category_occupancy(category)
                if vagas != -1 and vagas < occupancy:
                    raise ValueError(
                        f'Não é possível reduzir as vagas da categoria "{category.nome}" abaixo da ocupação atual ({occupancy}).'
                    )
                category.nome = nome
                category.vagas = vagas
                category.ordem = position
                incoming_ids.add(category_id)
            else:
                event.registration_categories.append(EventRegistrationCategory(
                    nome=nome,
                    vagas=vagas,
                    ordem=position,
                ))

        for category_id, category in existing_categories.items():
            if category_id in incoming_ids:
                continue

            occupancy = self.get_event_category_occupancy(category)
            if occupancy > 0:
                raise ValueError(
                    f'Não é possível remover a categoria "{category.nome}" porque ela já possui {occupancy} inscrição(ões).'
                )
            db.session.delete(category)

    @staticmethod
    def can_create_events(user):
        return bool(user and getattr(user, 'can_create_events', False))

    @staticmethod
    def can_manage_event_certificates(user, event):
        if not user or not event:
            return False
        if user.role in ['admin', 'extensao']:
            return True
        return EventService.can_manage_event(user, event)

    @staticmethod
    def can_view_event_certificates(user, event):
        if not user or not event:
            return False
        if user.role in ['admin', 'extensao', 'gestor']:
            return True
        return EventService.can_manage_event_certificates(user, event)

    @staticmethod
    def can_manage_event_participants(user, event):
        if not user or not event:
            return False
        if user.role in ['admin', 'extensao']:
            return True
        return EventService.can_manage_event(user, event)

    @staticmethod
    def can_add_event_participants(user, event):
        if not user or not event:
            return False
        if user.role in ['admin', 'extensao']:
            return True
        return EventService.can_manage_event(user, event)

    @staticmethod
    def can_notify_event_participants(user, event):
        return EventService.can_manage_event(user, event)

    @staticmethod
    def can_access_event_management(user):
        if not user:
            return False
        if user.role in ['admin', 'coordenador', 'gestor', 'extensao']:
            return True
        return EventService.can_create_events(user)

    @staticmethod
    def _can_manage_own_events(user):
        if not user:
            return False
        if user.role in ['coordenador', 'gestor']:
            return True
        return EventService.can_create_events(user)

    @staticmethod
    def is_event_owner(user, event):
        if not user or not event:
            return False
        return bool(event.owner_username and event.owner_username == user.username)

    @staticmethod
    def is_same_course_event(user, event):
        if not user or not event:
            return False
        return bool(user.course_id and event.course_id and user.course_id == event.course_id)

    @staticmethod
    def can_view_event(user, event):
        if not user or not event:
            return False
        if user.role == 'admin':
            return True
        if user.role == 'gestor':
            return True
        if user.role == 'coordenador':
            return EventService.is_same_course_event(user, event)
        if EventService.can_create_events(user):
            return event.owner_username == user.username
        return False

    @staticmethod
    def can_edit_event(user, event):
        if not user or not event:
            return False
        if user.role == 'admin':
            return True
        if user.role == 'coordenador':
            return EventService.is_same_course_event(user, event)
        return EventService.is_event_owner(user, event) and EventService._can_manage_own_events(user)

    @staticmethod
    def can_delete_event(user, event):
        if not user or not event:
            return False
        if user.role == 'admin':
            return True
        if user.role == 'coordenador':
            return EventService.is_event_owner(user, event)
        return EventService.is_event_owner(user, event) and EventService._can_manage_own_events(user)

    @staticmethod
    def can_manage_event(user, event):
        return EventService.can_edit_event(user, event)

    def create_event(self, owner_username, data):
        """Creates a new event and its associated activities."""
        is_rapido = bool(data.get('is_rapido'))
        fast_event_hours = self._parse_fast_event_hours(data.get('carga_horaria_rapida')) if is_rapido else None
        allowed_roles = self._normalize_allowed_roles_payload(
            data.get('perfis_habilitados'),
            default_if_missing=True,
        )
        registration_categories = self._normalize_registration_categories_payload(
            data.get('categorias_inscricao'),
            default_if_missing=True,
        )
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
        self._sync_event_allowed_roles(event, allowed_roles)
        self._sync_event_registration_categories(event, registration_categories)
        db.session.flush()
        
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
        allowed_roles = self._normalize_allowed_roles_payload(data.get('perfis_habilitados'))
        registration_categories = self._normalize_registration_categories_payload(data.get('categorias_inscricao'))
            
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

        if allowed_roles is None:
            allowed_roles = self.get_event_allowed_roles(event)
        if registration_categories is None:
            if event.registration_categories:
                registration_categories = [
                    {
                        'id': category.id,
                        'nome': category.nome,
                        'vagas': category.vagas,
                        'ordem': int(category.ordem or index),
                    }
                    for index, category in enumerate(event.registration_categories)
                ]
            else:
                registration_categories = self._normalize_registration_categories_payload(
                    None,
                    default_if_missing=True,
                )

        self._sync_event_allowed_roles(event, allowed_roles)
        self._sync_event_registration_categories(event, registration_categories)
        db.session.flush()
        
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
                activity.nome = atv_data.get('nome')
                activity.local = atv_data.get('local')
                activity.descricao = atv_data.get('descricao', '')
                activity.data_atv = self._parse_date(atv_data.get('data_atv'))
                activity.hora_atv = self._parse_time(atv_data.get('hora_atv'))
                activity.carga_horaria = horas
                activity.vagas = vagas
                activity.latitude = event.latitude
                activity.longitude = event.longitude
                self._sync_activity_speakers(activity, atv_data)
                self.activity_repo.save(activity)
                incoming_ids.add(int(atv_id))
            else:
                # Create new activity
                new_atv = Activity(
                    event_id=event.id,
                    nome=atv_data.get('nome'),
                    local=atv_data.get('local'),
                    descricao=atv_data.get('descricao', ''),
                    data_atv=self._parse_date(atv_data.get('data_atv')),
                    hora_atv=self._parse_time(atv_data.get('hora_atv')),
                    carga_horaria=horas,
                    vagas=vagas,
                    latitude=event.latitude,
                    longitude=event.longitude
                )
                self._sync_activity_speakers(new_atv, atv_data)
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
        if user.role == 'admin':
            pass
        elif user.role == 'extensao':
            pass
        elif user.role == 'gestor':
            # Gestor can consult events across courses.
            pass
        elif user.role == 'coordenador':
            if user.course_id:
                query = query.filter(Event.course_id == user.course_id)
            else:
                query = query.filter(Event.id == -1)
        elif self.can_create_events(user):
            query = query.filter_by(owner_username=user.username)
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

        if user.role == 'admin':
            pass
        elif user.role == 'extensao':
            pass
        elif user.role == 'coordenador':
            if user.course_id:
                query = query.filter(Event.course_id == user.course_id)
            else:
                query = query.filter(Event.id == -1)
        elif user.role == 'gestor':
            # Gestor can consult all events; edition constraints are enforced elsewhere.
            pass
        elif self.can_create_events(user):
            query = query.filter(Event.owner_username == user.username)
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

    def get_open_events_paginated(self, user, page=1, per_page=12, filters=None):
        """Lists open enrollment events available to any authenticated user."""
        query = Event.query.filter(Event.status == 'ABERTO')
        joined_course = False

        if user and getattr(user, 'role', None) not in ['admin', 'extensao']:
            user_cpf = getattr(user, 'cpf', None)
            has_existing_registration = False
            if user_cpf:
                has_existing_registration = or_(
                    Event.registrations.any(EventRegistration.user_cpf == user_cpf),
                    Event.activities.any(
                        Activity.enrollments.any(Enrollment.user_cpf == user_cpf)
                    ),
                )

            query = query.filter(or_(
                ~Event.allowed_roles.any(),
                Event.allowed_roles.any(EventAllowedRole.role == getattr(user, 'role', None)),
                has_existing_registration,
            ))

        if filters:
            if filters.get('nome'):
                query = query.filter(Event.nome.ilike(f"%{filters['nome']}%"))
            if filters.get('tipo'):
                query = query.filter(Event.tipo == filters['tipo'])
            if filters.get('course_id'):
                query = query.filter(Event.course_id == filters['course_id'])
            if filters.get('curso'):
                if not joined_course:
                    query = query.join(Course, Event.course_id == Course.id, isouter=True)
                    joined_course = True
                query = query.filter(Course.nome.ilike(f"%{filters['curso']}%"))
            if filters.get('data'):
                parsed_date = self._parse_date(filters['data'])
                if parsed_date:
                    query = query.filter(Event.data_inicio == parsed_date)
            else:
                start_date = self._parse_date(filters.get('data_inicio'))
                end_date = self._parse_date(filters.get('data_fim'))
                if start_date and end_date and start_date > end_date:
                    start_date, end_date = end_date, start_date
                if start_date:
                    query = query.filter(Event.data_inicio >= start_date)
                if end_date:
                    query = query.filter(Event.data_inicio <= end_date)
            if filters.get('programacao'):
                search = f"%{filters['programacao']}%"
                query = query.filter(Event.activities.any(or_(
                    Activity.nome.ilike(search),
                    Activity.descricao.ilike(search),
                    Activity.local.ilike(search),
                    Activity.palestrante.ilike(search),
                    Activity.speakers.any(ActivitySpeaker.nome.ilike(search)),
                )))
            if filters.get('situacao') in {'inscrito', 'nao_inscrito'} and user and getattr(user, 'cpf', None):
                user_is_enrolled = or_(
                    Event.registrations.any(EventRegistration.user_cpf == user.cpf),
                    Event.activities.any(
                        Activity.enrollments.any(Enrollment.user_cpf == user.cpf)
                    ),
                )
                if filters['situacao'] == 'inscrito':
                    query = query.filter(user_is_enrolled)
                else:
                    query = query.filter(~user_is_enrolled)

        return query.order_by(Event.data_inicio.asc(), Event.hora_inicio.asc()).paginate(page=page, per_page=per_page, error_out=False)

    def get_event_participants_paginated(self, event_id, page=1, per_page=10, filters=None):
        """Retrieves a paginated list of participants enrolled in an event."""
        from sqlalchemy.orm import joinedload

        query = (
            Enrollment.query
            .join(Activity, Enrollment.activity_id == Activity.id)
            .filter(Activity.event_id == event_id)
            .options(
                joinedload(Enrollment.activity),
                joinedload(Enrollment.event_registration).joinedload(EventRegistration.category),
            )
        )
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

        return query.order_by(Enrollment.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

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
        if not self.can_delete_event(user, event):
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

    def toggle_enrollment(self, user, activity_id, action, category_id=None, actor_user=None):
        """Handles user enrollment and disenrollment logic."""
        activity = self.activity_repo.get_by_id(activity_id)
        if not activity:
            return None, "Atividade não encontrada"

        event = activity.event
        existing = self.get_enrollment(activity_id, user.cpf)

        if action == 'inscrever':
            if existing:
                return existing, "Já inscrito"

            registration, registration_error = self.ensure_event_registration(
                event,
                user,
                category_id=category_id,
                actor_user=actor_user or user,
            )
            if registration_error:
                return None, registration_error

            current_count = len(activity.enrollments)
            if activity.vagas != -1 and current_count >= activity.vagas:
                return None, "Lotado!"
            
            enrollment = Enrollment(
                activity_id=activity_id,
                user_cpf=user.cpf,
                event_registration_id=registration.id if registration else None,
                nome=user.nome,
                presente=False,
            )
            try:
                saved = self.enrollment_repo.save(enrollment)
            except IntegrityError:
                # Covers concurrent insert attempts after uniqueness hardening.
                existing = self.get_enrollment(activity_id, user.cpf)
                if existing:
                    if not existing.event_registration_id:
                        refreshed_registration, _ = self.ensure_event_registration(
                            event,
                            user,
                            category_id=category_id,
                            actor_user=actor_user or user,
                        )
                        if refreshed_registration:
                            existing.event_registration_id = refreshed_registration.id
                            self.enrollment_repo.save(existing)
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
                        'my_events_url': f"{app_url}/meus_eventos" if app_url else '',
                        'cancel_url': '',
                    },
                )
            return saved, "Inscrição Realizada!"
        elif action == 'sair':
            if existing:
                self.enrollment_repo.delete(existing)
                self.cleanup_event_registration_if_empty(event, user)
            return None, "Desinscrição realizada."
        return None, "Ação inválida"

    def manual_enroll_user(self, actor_user, subject_user, activity_id, category_id=None):
        activity = self.get_activity(activity_id)
        if not activity:
            return False, "Atividade inválida.", None

        existing = self.get_enrollment(activity_id, subject_user.cpf)
        if existing:
            return False, "Usuário já está inscrito nesta atividade.", existing

        enrollment, message = self.toggle_enrollment(
            subject_user,
            activity_id,
            'inscrever',
            category_id=category_id,
            actor_user=actor_user,
        )
        if not enrollment:
            return False, message, None

        enrollment.presente = True
        self.enrollment_repo.save(enrollment)
        return True, "Inscrição realizada com sucesso.", enrollment

    def confirm_attendance(self, user, activity_id, event_id, lat=None, lon=None, category_id=None):
        activity = self.get_activity(activity_id)
        if not activity:
            return False, "Atividade não encontrada", None

        event = activity.event
        enrollment = self.get_enrollment(activity_id, user.cpf)

        if not enrollment:
            if activity.nome == "Check-in Presença":
                registration, registration_error = self.ensure_event_registration(
                    event,
                    user,
                    category_id=category_id,
                    actor_user=user,
                )
                if registration_error:
                    return False, registration_error, None

                enrollment = Enrollment(
                    activity_id=activity_id,
                    user_cpf=user.cpf,
                    event_registration_id=registration.id if registration else None,
                    nome=user.nome,
                    presente=True,
                    lat_checkin=lat,
                    lon_checkin=lon,
                )
                self.enrollment_repo.save(enrollment)
            else:
                return False, "Você não se inscreveu nesta atividade.", None
        else:
            if not enrollment.event_registration_id:
                registration, registration_error = self.ensure_event_registration(
                    event,
                    user,
                    category_id=category_id,
                    actor_user=user,
                )
                if registration_error:
                    return False, registration_error, None
                enrollment.event_registration_id = registration.id if registration else None
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
                    'app_url': f"{app_url}/meus_eventos" if app_url else '',
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
        activity = Activity(event_id=event.id, nome="Check-in Presença", palestrante="", email_palestrante=None, local="", descricao="Registro de presença.", data_atv=event.data_inicio, hora_atv=event.hora_inicio, carga_horaria=workload_hours, vagas=-1, latitude=event.latitude, longitude=event.longitude)
        activity.sync_legacy_speaker_fields()
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

            activity = Activity(
                event_id=event.id,
                nome=atv.get('nome'),
                local=atv.get('local'),
                descricao=atv.get('descricao', ''),
                data_atv=self._parse_date(atv.get('data_atv')),
                hora_atv=self._parse_time(atv.get('hora_atv')),
                carga_horaria=horas,
                vagas=vagas,
                latitude=event.latitude,
                longitude=event.longitude,
            )
            self._sync_activity_speakers(activity, atv)
            self.activity_repo.save(activity)
