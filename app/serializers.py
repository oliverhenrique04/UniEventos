def _fmt_date(value):
    if not value:
        return None
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _fmt_time(value):
    if not value:
        return None
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    return str(value)


def serialize_user(user):
    """Serializes a User object to a dictionary."""
    if not user:
        return None
    return {
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'nome': user.nome,
        'cpf': user.cpf,
        'ra': user.ra,
        'curso': user.curso,
        'can_create_events': user.can_create_events,
    }

def serialize_activity(activity, current_user=None, include_private=False):
    """Serializes an Activity object to a dictionary, optionally checking enrollment."""
    total_inscritos = len(activity.enrollments)
    inscrito = False
    
    if current_user:
        for e in activity.enrollments:
            if e.user_cpf == current_user.cpf:
                inscrito = True
                break
    
    speakers_payload = activity.get_speakers_payload(include_emails=include_private)
    primary_speaker_name = activity.primary_speaker_name
    primary_speaker_email = activity.primary_speaker_email if include_private else None

    return {
        'id': activity.id,
        'event_id': activity.event_id,
        'nome': activity.nome,
        'palestrante': primary_speaker_name,
        'email_palestrante': primary_speaker_email,
        'palestrantes': speakers_payload,
        'palestrantes_label': activity.palestrantes_label,
        'local': activity.local,
        'descricao': activity.descricao,
        'data_atv': _fmt_date(activity.data_atv),
        'hora_atv': _fmt_time(activity.hora_atv),
        'carga_horaria': activity.carga_horaria,
        'vagas': activity.vagas,
        'total_inscritos': total_inscritos,
        'inscrito': inscrito
    }

def serialize_event(event, current_user=None):
    """Serializes an Event object to a dictionary with participation aggregates."""
    if not event:
        return None
        
    total_inscritos = 0
    total_presentes = 0
    for a in event.activities:
        total_inscritos += len(a.enrollments)
        total_presentes += len([e for e in a.enrollments if e.presente])

    # Sort activities chronologically
    sorted_activities = sorted(event.activities, key=lambda a: (a.data_atv or '', a.hora_atv or ''))
    
    from app.models import User
    owner_user = User.query.filter_by(username=event.owner_username).first() if event.owner_username else None
    owner_name = owner_user.nome if owner_user else (event.owner_username or 'Sistema')

    can_edit = False
    can_delete = False
    can_manage_participants = False
    can_manage_certificates = False

    if current_user:
        same_course = bool(current_user.course_id and event.course_id and current_user.course_id == event.course_id)
        is_owner = event.owner_username == current_user.username
        can_manage_own_events = bool(getattr(current_user, 'can_create_events', False) and is_owner)

        if current_user.role == 'admin':
            can_edit = True
            can_delete = True
            can_manage_participants = True
            can_manage_certificates = True
        elif current_user.role == 'coordenador':
            can_edit = same_course
            can_delete = same_course
            can_manage_participants = same_course
            can_manage_certificates = same_course
        elif current_user.role == 'gestor':
            can_edit = same_course
            can_delete = same_course
            can_manage_participants = same_course
            can_manage_certificates = same_course
        elif can_manage_own_events:
            can_edit = True
            can_delete = True
            can_manage_participants = True
            can_manage_certificates = True

    include_private_speaker_data = can_edit or can_manage_participants or can_manage_certificates

    return {
        'id': event.id,
        'owner': event.owner_username,
        'owner_name': owner_name,
        'nome': event.nome,
        'descricao': event.descricao,
        'curso': event.curso, # Derived from normalized course relation
        'course_id': event.course_id,
        'tipo': event.tipo,
        'data_inicio': _fmt_date(event.data_inicio),
        'hora_inicio': _fmt_time(event.hora_inicio),
        'data_fim': _fmt_date(event.data_fim),
        'hora_fim': _fmt_time(event.hora_fim),
        'token_publico': event.token_publico,
        'status': event.status,
        'total_inscritos': total_inscritos,
        'total_presentes': total_presentes,
        'atividades': [serialize_activity(a, current_user, include_private=include_private_speaker_data) for a in sorted_activities],
        'can_edit': can_edit,
        'can_delete': can_delete,
        'can_manage_participants': can_manage_participants,
        'can_manage_certificates': can_manage_certificates,
    }
