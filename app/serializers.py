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
    can_delete_permission = False
    can_manage_participants = False
    can_add_participants = False
    can_notify_participants = False
    can_view_certificates = False
    can_manage_certificates = False
    allowed_roles = []
    registration_categories = []
    current_registration = None
    current_registration_category = None
    can_self_enroll = False
    has_event_registration = False
    enrollment_block_reason = None
    delete_block_reason = None
    delete_block_status = {
        'linked_event_registrations_count': 0,
        'linked_enrollments_count': 0,
        'has_linked_records': False,
        'delete_block_reason': None,
    }

    if current_user:
        from app.services.event_service import EventService

        can_edit = EventService.can_edit_event(current_user, event)
        can_delete_permission = EventService.can_delete_event(current_user, event)
        can_manage_participants = EventService.can_manage_event_participants(current_user, event)
        can_add_participants = EventService.can_add_event_participants(current_user, event)
        can_notify_participants = EventService.can_notify_event_participants(current_user, event)
        can_view_certificates = EventService.can_view_event_certificates(current_user, event)
        can_manage_certificates = EventService.can_manage_event_certificates(current_user, event)
        service = EventService()
        delete_block_status = service.get_event_delete_block_status(event)
        can_delete = can_delete_permission and not delete_block_status['has_linked_records']
        if not can_delete_permission:
            delete_block_reason = 'Sem permissão para excluir este evento.'
        elif delete_block_status['has_linked_records']:
            delete_block_reason = delete_block_status['delete_block_reason']
        allowed_roles = service.get_event_allowed_roles(event)
        current_registration = service.get_event_registration_for_user(event, current_user)
        has_legacy_enrollment = any(
            enrollment.user_cpf == current_user.cpf
            for activity in event.activities
            for enrollment in activity.enrollments
        )
        has_event_registration = bool(current_registration or has_legacy_enrollment)
        if current_registration and current_registration.category:
            current_registration_category = current_registration.category
        elif has_legacy_enrollment:
            current_registration_category = service.resolve_registration_category(event)
        can_self_enroll = service.can_self_enroll(current_user) and service.can_user_access_open_event(current_user, event)
        if not can_self_enroll and not has_event_registration and service.can_self_enroll(current_user):
            enrollment_block_reason = 'Seu perfil não está habilitado para este evento.'
    else:
        from app.services.event_service import EventService

        allowed_roles = EventService.get_event_allowed_roles(event)

    if not allowed_roles:
        from app.services.event_service import EventService

        allowed_roles = EventService.get_event_allowed_roles(event)

    from app.services.event_service import EventService
    category_service = EventService()
    event_categories = category_service.get_event_categories(event)
    fallback_unique_enrollments = len({
        enrollment.user_cpf
        for activity in event.activities
        for enrollment in activity.enrollments
        if enrollment.user_cpf
    })
    for category in event_categories:
        if getattr(category, 'id', None):
            occupancy = category_service.get_event_category_occupancy(category)
        else:
            occupancy = fallback_unique_enrollments
        vagas = category.vagas if getattr(category, 'vagas', None) is not None else -1
        vagas_restantes = None if vagas == -1 else max(0, vagas - occupancy)
        registration_categories.append({
            'id': getattr(category, 'id', None),
            'nome': category.nome,
            'vagas': vagas,
            'ocupacao': occupancy,
            'vagas_restantes': vagas_restantes,
            'lotada': vagas != -1 and occupancy >= vagas,
            'selecionada': bool(
                current_registration_category
                and current_registration_category.nome == category.nome
            ),
        })

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
        'perfis_habilitados': allowed_roles,
        'categorias_inscricao': registration_categories,
        'categoria_inscricao_usuario': (
            {
                'id': getattr(current_registration_category, 'id', None),
                'nome': current_registration_category.nome,
            }
            if current_registration_category else None
        ),
        'possui_inscricao_evento': has_event_registration,
        'pode_se_inscrever': can_self_enroll,
        'motivo_bloqueio_inscricao': enrollment_block_reason,
        'can_edit': can_edit,
        'can_delete': can_delete,
        'can_delete_permission': can_delete_permission,
        'linked_event_registrations_count': delete_block_status['linked_event_registrations_count'],
        'linked_enrollments_count': delete_block_status['linked_enrollments_count'],
        'has_linked_records': delete_block_status['has_linked_records'],
        'delete_block_reason': delete_block_reason,
        'can_manage_participants': can_manage_participants,
        'can_add_participants': can_add_participants,
        'can_notify_participants': can_notify_participants,
        'can_view_certificates': can_view_certificates,
        'can_manage_certificates': can_manage_certificates,
    }
