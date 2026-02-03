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
        'curso': user.curso
    }

def serialize_activity(activity, current_user=None):
    """Serializes an Activity object to a dictionary, optionally checking enrollment."""
    total_inscritos = len(activity.enrollments)
    inscrito = False
    
    if current_user:
        for e in activity.enrollments:
            if e.user_cpf == current_user.cpf:
                inscrito = True
                break
    
    return {
        'id': activity.id,
        'event_id': activity.event_id,
        'nome': activity.nome,
        'palestrante': activity.palestrante,
        'local': activity.local,
        'descricao': activity.descricao,
        'data_atv': activity.data_atv,
        'hora_atv': activity.hora_atv,
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
    
    return {
        'id': event.id,
        'owner': event.owner_username,
        'nome': event.nome,
        'descricao': event.descricao,
        'curso': event.curso, # Include curso in serialization
        'tipo': event.tipo,
        'data_inicio': event.data_inicio,
        'hora_inicio': event.hora_inicio,
        'data_fim': event.data_fim,
        'hora_fim': event.hora_fim,
        'token_publico': event.token_publico,
        'status': event.status,
        'total_inscritos': total_inscritos,
        'total_presentes': total_presentes,
        'atividades': [serialize_activity(a, current_user) for a in sorted_activities]
    }
