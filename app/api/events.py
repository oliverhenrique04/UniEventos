import json
from flask import Blueprint, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, func, case
from app.models import (
    Event,
    Activity,
    Enrollment,
    Course,
    User,
    InstitutionalCertificate,
    InstitutionalCertificateRecipient,
    InstitutionalCertificateCategory,
    db,
)
from app.services.event_service import EventService
from app.serializers import serialize_event
from datetime import datetime, timedelta, timezone

bp = Blueprint('events', __name__, url_prefix='/api')
event_service = EventService()


def _user_can_manage_event(event):
    return event_service.can_manage_event(current_user, event)


def _user_can_view_event(event):
    return event_service.can_view_event(current_user, event)


def _enforce_role_course_for_creation(data):
    if current_user.role not in ['coordenador', 'gestor']:
        return None

    if not current_user.course_id or not current_user.curso:
        return 'Perfil sem curso vinculado para criar eventos.'

    requested_course = (data.get('curso') or '').strip()
    if requested_course and requested_course.lower() != str(current_user.curso).lower():
        return 'Para este perfil, o evento deve estar vinculado ao seu curso.'

    # Force binding to the user course to keep data consistency.
    data['curso'] = current_user.curso
    return None


def _paginate_items(items, page, per_page):
    total = len(items)
    pages = (total + per_page - 1) // per_page if total > 0 else 0
    if pages == 0:
        return {
            'items': [],
            'total': 0,
            'pages': 0,
            'current_page': 1,
        }

    current_page = max(1, min(page, pages))
    start = (current_page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'total': total,
        'pages': pages,
        'current_page': current_page,
    }


def _safe_workload_hours(value):
    raw = str(value or '').strip().replace(',', '.')
    if not raw:
        return 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0


def _apply_event_visibility_scope(base_query):
    """Apply role-based event visibility to analytics/reporting queries."""
    query = base_query
    if current_user.role == 'professor':
        query = query.filter(Event.owner_username == current_user.username)
    elif current_user.role == 'coordenador':
        if current_user.course_id:
            query = query.filter(Event.course_id == current_user.course_id)
        else:
            query = query.filter(Event.id == -1)
    elif current_user.role == 'gestor':
        # Gestor can consult all events.
        pass
    elif current_user.role != 'admin':
        query = query.filter(Event.id == -1)
    return query


def _get_user_institutional_recipients(user):
    recipient_filters = []
    if user.username:
        recipient_filters.append(InstitutionalCertificateRecipient.user_username == user.username)
    if user.cpf:
        recipient_filters.append(InstitutionalCertificateRecipient.cpf == user.cpf)
    if user.email:
        recipient_filters.append(
            func.lower(InstitutionalCertificateRecipient.email) == user.email.lower()
        )

    if not recipient_filters:
        return []

    return (
        InstitutionalCertificateRecipient.query
        .join(
            InstitutionalCertificate,
            InstitutionalCertificate.id == InstitutionalCertificateRecipient.certificate_id,
        )
        .filter(InstitutionalCertificateRecipient.cert_hash.isnot(None))
        .filter(or_(*recipient_filters))
        .all()
    )

@bp.route('/criar_evento', methods=['POST'])
@login_required
def criar_evento():
    """
    Endpoint for creating a new event.
    Only professors and admins can create events.
    """
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json

    course_error = _enforce_role_course_for_creation(data)
    if course_error:
        return jsonify({"erro": course_error}), 403
    
    # Simple validation for start date
    try:
        data_ini_obj = datetime.strptime(data.get('data_inicio'), '%Y-%m-%d').date()
        if data_ini_obj < datetime.now().date():
            return jsonify({"erro": "Data de início no passado!"}), 400
    except (ValueError, TypeError):
        pass

    try:
        event = event_service.create_event(current_user.username, data)
        return jsonify({
            "mensagem": "Criado!",
            "link": url_for('main.inscrever_via_link', token=event.token_publico),
        })
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/editar_evento', methods=['POST'])
@login_required
def editar_evento():
    """
    Endpoint for updating an existing event.
    Validates ownership or administrative privileges before proceeding.
    """
    data = request.json
    evt_id = data.get('id')
    
    if not evt_id:
        return jsonify({"erro": "ID do evento é obrigatório"}), 400

    event = event_service.get_event_by_id(evt_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404

    if not _user_can_manage_event(event):
        return jsonify({"erro": "Sem permissão para editar este evento"}), 403

    if current_user.role in ['coordenador', 'gestor']:
        data['curso'] = current_user.curso
    
    try:
        event, message = event_service.update_event(evt_id, current_user, data)
        
        if not event:
            status_code = 404 if message == "Evento não encontrado" else 403
            return jsonify({"erro": message}), status_code
            
        return jsonify({"mensagem": message})
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": f"Erro interno ao atualizar evento: {str(e)}"}), 500

@bp.route('/eventos_admin', methods=['GET'])
@login_required
def listar_eventos_admin():
    """Paginated and filtered list of all events for administrative purposes."""
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return jsonify([]), 403
    
    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'tipo': request.args.get('tipo'),
        'status': request.args.get('status'),
        'owner': request.args.get('owner'),
        'curso': request.args.get('curso'),
        'data': request.args.get('data')
    }
    
    pagination = event_service.list_events_paginated(current_user, page=page, filters=filters)
    
    return jsonify({
        "items": [serialize_event(e, current_user) for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/notificar_participantes/<int:event_id>', methods=['POST'])
@login_required
def notificar_participantes(event_id):
    """
    Sends a broadcast email notification to all participants of an event.
    Only authorized personnel (admin, professor, coordinator) can call this.
    """
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return jsonify({"erro": "Acesso negado"}), 403

    event = event_service.get_event_by_id(event_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404
    if not _user_can_manage_event(event):
        return jsonify({"erro": "Acesso negado"}), 403
    
    data = request.json
    subject = data.get('assunto')
    body = data.get('mensagem')
    
    if not subject or not body:
        return jsonify({"erro": "Assunto e mensagem são obrigatórios"}), 400
        
    try:
        count = event_service.notify_all_participants(event_id, subject, body)
        return jsonify({"mensagem": f"Notificação enfileirada para {count} participantes!"})
    except Exception as e:
        return jsonify({"erro": f"Erro ao processar notificações: {str(e)}"}), 500

@bp.route('/participantes_evento/<int:event_id>', methods=['GET'])
@login_required
def listar_participantes_evento(event_id):
    """Paginated and filtered list of participants in an event, including geofencing distance."""
    from app.utils import haversine_distance

    event = event_service.get_event_by_id(event_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404
    if not _user_can_view_event(event):
        return jsonify({"erro": "Acesso negado"}), 403

    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'cpf': request.args.get('cpf'),
        'activity_id': request.args.get('activity_id', type=int),
        'presente': request.args.get('presente', type=lambda v: v.lower() == 'true') if request.args.get('presente') else None
    }
    
    pagination = event_service.get_event_participants_paginated(event_id, page=page, filters=filters)
    
    items = []
    for e in pagination.items:
        # Calculate distance if we have both activity and check-in coordinates
        dist = None
        # Use activity coords if set, otherwise event coords
        ref_lat = e.activity.latitude if e.activity.latitude else e.activity.event.latitude
        ref_lon = e.activity.longitude if e.activity.longitude else e.activity.event.longitude
        
        if ref_lat and ref_lon and e.lat_checkin and e.lon_checkin:
            dist = haversine_distance(ref_lat, ref_lon, e.lat_checkin, e.lon_checkin)
        
        items.append({
            "id": e.id,
            "nome": e.nome,
            "cpf": e.user_cpf,
            "presente": e.presente,
            "atividade": e.activity.nome,
            "distancia": round(dist) if dist is not None else None,
            "lat_checkin": e.lat_checkin,
            "lon_checkin": e.lon_checkin
        })
    
    return jsonify({
        "items": items,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/alternar_presenca/<int:enrollment_id>', methods=['POST'])
@login_required
def alternar_presenca_manual(enrollment_id):
    """Manually toggles the attendance status of a participant."""
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({"erro": "Matrícula não encontrada"}), 404

    activity = db.session.get(Activity, enrollment.activity_id)
    event = db.session.get(Event, activity.event_id) if activity else None
    if not event or not _user_can_manage_event(event):
        return jsonify({"erro": "Acesso negado"}), 403

    status = request.json.get('presente')
    success, msg = event_service.toggle_attendance_manual(enrollment_id, status)
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/deletar_evento/<int:event_id>', methods=['DELETE'])
@login_required
def deletar_evento(event_id):
    """Removes an event and all its data."""
    success, msg = event_service.delete_event(event_id, current_user)
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 403

@bp.route('/remover_inscricao/<int:enrollment_id>', methods=['DELETE'])
@login_required
def remover_inscricao(enrollment_id):
    """Deletes a specific enrollment record."""
    from app.models import Enrollment, db
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        abort(404)

    activity = db.session.get(Activity, enrollment.activity_id)
    event = db.session.get(Event, activity.event_id) if activity else None
    if not event or not _user_can_manage_event(event):
        return jsonify({"erro": "Acesso negado"}), 403

    db.session.delete(enrollment)
    db.session.commit()
    return jsonify({"mensagem": "Inscrição removida!"})

@bp.route('/me/history', methods=['GET'])
@login_required
def meu_historico():
    """Endpoint for the current user to retrieve their participation history and stats."""
    type = request.args.get('type', 'events') 
    page = request.args.get('page', 1, type=int)

    allowed_types = {'stats', 'participated', 'events', 'activities', 'certificates'}
    if type not in allowed_types:
        return jsonify({'erro': 'Tipo de historico invalido'}), 400
    
    if type == 'stats':
        presences = Enrollment.query.filter_by(user_cpf=current_user.cpf, presente=True).all()
        total_event_hours = 0
        for presence in presences:
            activity = db.session.get(Activity, presence.activity_id)
            if activity:
                total_event_hours += activity.carga_horaria or 0
        event_count = db.session.query(Activity.event_id).join(Enrollment, Enrollment.activity_id == Activity.id).filter(
            Enrollment.user_cpf == current_user.cpf
        ).distinct().count()

        institutional_recipients = _get_user_institutional_recipients(current_user)
        seen_inst = set()
        institutional_hours = 0
        for recipient in institutional_recipients:
            inst_key = recipient.cert_hash or recipient.id
            if inst_key in seen_inst:
                continue
            seen_inst.add(inst_key)
            metadata = {}
            if recipient.metadata_json:
                try:
                    metadata = json.loads(recipient.metadata_json)
                except Exception:
                    metadata = {}
            institutional_hours += _safe_workload_hours(metadata.get('carga_horaria'))

        total_hours = total_event_hours + institutional_hours

        return jsonify({
            "total_hours": int(total_hours) if float(total_hours).is_integer() else round(total_hours, 2),
            "total_events": event_count,
            "total_institutional_certificates": len(seen_inst),
        })

    if type == 'participated':
        # Join Events with Enrollments where presente=True
        query = db.session.query(Event).join(Activity, Event.id == Activity.event_id).join(Enrollment, Enrollment.activity_id == Activity.id)\
            .filter(Enrollment.user_cpf == current_user.cpf, Enrollment.presente == True).distinct()
        
        pagination = query.order_by(Event.data_inicio.desc()).paginate(page=page, per_page=10, error_out=False)
        
        items = []
        for ev in pagination.items:
            # Sum hours for this user in this event
            ev_hours = db.session.query(db.func.sum(Activity.carga_horaria))\
                .join(Enrollment, Activity.id == Enrollment.activity_id)\
                .filter(Activity.event_id == ev.id, Enrollment.user_cpf == current_user.cpf, Enrollment.presente == True).scalar() or 0
            
            
            # Check if any certificate has been generated and published (has cert_hash)
            has_cert = db.session.query(Enrollment.id)\
                .join(Activity, Activity.id == Enrollment.activity_id)\
                .filter(Activity.event_id == ev.id, Enrollment.user_cpf == current_user.cpf, Enrollment.cert_hash.isnot(None), Enrollment.presente == True).first() is not None

            items.append({
                "id": ev.id,
                "nome": ev.nome,
                "data": ev.data_inicio.isoformat() if ev.data_inicio else None,
                "horas": int(ev_hours),
                "tipo": ev.tipo,
                "token": ev.token_publico
            ,
                "cert_disponivel": has_cert
            })
        
        return jsonify({
            "items": items,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": pagination.page
        })

    if type == 'events':
        pagination = event_service.get_user_events_paginated(current_user.cpf, page=page)
        items = [serialize_event(e, current_user) for e in pagination.items]
    elif type == 'activities':
        event_activities = (
            Enrollment.query
            .filter_by(user_cpf=current_user.cpf)
            .join(Activity)
            .order_by(Activity.data_atv.desc(), Activity.hora_atv.desc())
            .all()
        )

        merged_timeline = [{
            "id": f"event-{e.id}",
            "entry_type": "evento",
            "atv_nome": e.activity.nome,
            "event_nome": e.activity.event.nome,
            "data": e.activity.data_atv.isoformat() if e.activity.data_atv else None,
            "horas": e.activity.carga_horaria,
            "presente": e.presente
        } for e in event_activities]

        institutional_recipients = _get_user_institutional_recipients(current_user)
        seen_timeline_inst = set()
        for recipient in institutional_recipients:
            unique_key = recipient.cert_hash or recipient.id
            if unique_key in seen_timeline_inst:
                continue
            seen_timeline_inst.add(unique_key)

            cert = recipient.certificate
            metadata = {}
            if recipient.metadata_json:
                try:
                    metadata = json.loads(recipient.metadata_json)
                except Exception:
                    metadata = {}

            merged_timeline.append({
                "id": f"inst-{recipient.id}",
                "entry_type": "institucional",
                "atv_nome": cert.titulo,
                "event_nome": cert.categoria,
                "data": cert.data_emissao,
                "horas": metadata.get('carga_horaria'),
                "presente": True,
            })

        merged_timeline.sort(key=lambda item: item.get('data') or '', reverse=True)
        paged = _paginate_items(merged_timeline, page=page, per_page=10)
        return jsonify(paged)
    else: # certificates
        event_certificates = (
            Enrollment.query
            .filter_by(user_cpf=current_user.cpf, presente=True)
            .filter(Enrollment.cert_hash.isnot(None))
            .join(Activity)
            .order_by(Activity.data_atv.desc(), Activity.hora_atv.desc())
            .all()
        )

        merged_items = [
            {
                "certificate_type": "evento",
                "enrollment_id": e.id,
                "title": e.activity.nome,
                "atv_nome": e.activity.nome,
                "event_id": e.activity.event_id,
                "event_nome": e.activity.event.nome,
                "category": "Evento",
                "data": e.activity.data_atv.isoformat() if e.activity.data_atv else None,
                "horas": e.activity.carga_horaria,
                "hash": e.cert_hash,
                "download_url": url_for('certificates.download_public', cert_hash=e.cert_hash) if e.cert_hash else url_for('certificates.download_single', enrollment_id=e.id),
                "preview_url": url_for('certificates.preview_public', cert_hash=e.cert_hash) if e.cert_hash else None,
                "issued_at": e.activity.data_atv.isoformat() if e.activity.data_atv else None,
            }
            for e in event_certificates
        ]

        institutional_recipients = _get_user_institutional_recipients(current_user)

        if institutional_recipients:

            for recipient in institutional_recipients:
                cert = recipient.certificate
                metadata = {}
                if recipient.metadata_json:
                    try:
                        metadata = json.loads(recipient.metadata_json)
                    except Exception:
                        metadata = {}

                merged_items.append({
                    "certificate_type": "institucional",
                    "recipient_id": recipient.id,
                    "institutional_certificate_id": cert.id,
                    "title": cert.titulo,
                    "atv_nome": cert.titulo,
                    "event_nome": cert.categoria,
                    "category": cert.categoria,
                    "data": cert.data_emissao,
                    "horas": metadata.get('carga_horaria'),
                    "hash": recipient.cert_hash,
                    "download_url": url_for('institutional_certificates.download_public_by_hash', cert_hash=recipient.cert_hash),
                    "preview_url": url_for('institutional_certificates.preview_public_by_hash', cert_hash=recipient.cert_hash),
                    "issued_at": cert.data_emissao,
                })

        deduped_items = []
        seen = set()
        for item in merged_items:
            if item.get('certificate_type') == 'institucional':
                key = ('institucional', item.get('hash') or item.get('recipient_id'))
            else:
                key = ('evento', item.get('hash') or item.get('enrollment_id'))
            if key in seen:
                continue
            seen.add(key)
            deduped_items.append(item)

        deduped_items.sort(key=lambda item: item.get('issued_at') or '', reverse=True)
        paged = _paginate_items(deduped_items, page=page, per_page=12)
        return jsonify(paged)

    return jsonify({
        "items": items,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/eventos', methods=['GET'])
@login_required
def listar_eventos():
    """Endpoint for listing events visible to the current user with pagination and filters."""
    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'data': request.args.get('data'),
        'curso': request.args.get('curso')
    }
    pagination = event_service.get_events_for_user_paginated(current_user, page=page, filters=filters)
    
    return jsonify({
        "items": [serialize_event(e, current_user) for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })


@bp.route('/dashboard/analytics', methods=['GET'])
@login_required
def dashboard_analytics():
    """Return aggregated analytics for admin/coordinator/professor/manager dashboards."""
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return jsonify({'erro': 'Acesso negado'}), 403

    period_days = request.args.get('period_days', 30, type=int)
    if period_days not in [7, 30, 90]:
        period_days = 30

    course_id = request.args.get('course_id', type=int)
    if course_id is not None and course_id <= 0:
        course_id = None

    today = datetime.utcnow().date()
    cutoff_date = today - timedelta(days=period_days)
    cutoff_datetime = datetime.utcnow() - timedelta(days=period_days)

    scoped_events_query = _apply_event_visibility_scope(Event.query)
    scoped_events_query = scoped_events_query.filter(Event.data_inicio.isnot(None), Event.data_inicio >= cutoff_date)
    if course_id:
        scoped_events_query = scoped_events_query.filter(Event.course_id == course_id)

    event_ids = [event_id for (event_id,) in scoped_events_query.with_entities(Event.id).all()]

    def _empty_payload():
        return {
            'summary': {
                'total_events': 0,
                'active_events': 0,
                'closed_events': 0,
                'total_courses': 0,
                'total_enrollments': 0,
                'unique_students': 0,
                'presence_rate': 0,
                'pending_certificate_events': 0,
            },
            'events_by_course': [],
            'students_by_course': [],
            'status_breakdown': [],
            'certificate_pipeline': {
                'with_certificate': 0,
                'without_certificate': 0,
            },
            'pending_certificate_events': [],
            'institutional_summary': {
                'total_certificates': 0,
                'draft_certificates': 0,
                'sent_certificates': 0,
                'archived_certificates': 0,
                'total_recipients': 0,
                'delivered_recipients': 0,
                'pending_recipients': 0,
                'delivery_rate': 0,
            },
            'institutional_by_category': [],
            'institutional_pending': [],
            'applied_filters': {
                'period_days': period_days,
                'course_id': course_id,
                'cutoff_date': cutoff_date.isoformat(),
            },
            'generated_at': datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        }

    if not event_ids:
        payload = _empty_payload()
    else:
        scoped_events_query = Event.query.filter(Event.id.in_(event_ids))

        total_events = scoped_events_query.count()
        active_events = scoped_events_query.filter(Event.status == 'ABERTO').count()
        closed_events = scoped_events_query.filter(Event.status != 'ABERTO').count()
        total_courses = (
            scoped_events_query
            .with_entities(Event.course_id)
            .filter(Event.course_id.isnot(None))
            .distinct()
            .count()
        )

        enrollments_query = (
            Enrollment.query
            .join(Activity, Enrollment.activity_id == Activity.id)
            .join(Event, Activity.event_id == Event.id)
            .filter(Event.id.in_(event_ids))
        )
        total_enrollments = enrollments_query.count()

        unique_students = (
            enrollments_query
            .with_entities(Enrollment.user_cpf)
            .filter(Enrollment.user_cpf.isnot(None))
            .distinct()
            .count()
        )

        presences_total = enrollments_query.filter(Enrollment.presente.is_(True)).count()
        presence_rate = round((presences_total / total_enrollments) * 100, 2) if total_enrollments else 0

        status_rows = (
            scoped_events_query
            .with_entities(Event.status, func.count(Event.id))
            .group_by(Event.status)
            .all()
        )
        status_breakdown = [
            {'status': status or 'SEM_STATUS', 'count': count}
            for status, count in status_rows
        ]

        events_by_course_rows = (
            db.session.query(
                Course.nome.label('course_name'),
                func.count(Event.id).label('events_count')
            )
            .select_from(Event)
            .outerjoin(Course, Event.course_id == Course.id)
            .filter(Event.id.in_(event_ids))
            .group_by(Course.nome)
            .order_by(func.count(Event.id).desc(), Course.nome.asc())
            .limit(10)
            .all()
        )
        events_by_course = [
            {'course': (course_name or 'Sem curso'), 'count': int(events_count)}
            for course_name, events_count in events_by_course_rows
        ]

        students_by_course_rows = (
            db.session.query(
                Course.nome.label('course_name'),
                func.count(func.distinct(User.cpf)).label('students_count')
            )
            .select_from(Enrollment)
            .join(Activity, Enrollment.activity_id == Activity.id)
            .join(Event, Activity.event_id == Event.id)
            .outerjoin(User, User.cpf == Enrollment.user_cpf)
            .outerjoin(Course, Course.id == User.course_id)
            .filter(Event.id.in_(event_ids))
            .group_by(Course.nome)
            .order_by(func.count(func.distinct(User.cpf)).desc(), Course.nome.asc())
            .limit(10)
            .all()
        )
        students_by_course = [
            {'course': (course_name or 'Sem curso'), 'count': int(students_count)}
            for course_name, students_count in students_by_course_rows
        ]

        pending_rows = (
            db.session.query(
                Event.id,
                Event.nome,
                Course.nome.label('course_name'),
                Event.data_inicio,
                func.count(Enrollment.id).label('enrollments_count'),
                func.count(Enrollment.cert_hash).label('cert_generated_count'),
                func.sum(case((Enrollment.presente.is_(True), 1), else_=0)).label('presence_count'),
            )
            .select_from(Event)
            .outerjoin(Course, Course.id == Event.course_id)
            .outerjoin(Activity, Activity.event_id == Event.id)
            .outerjoin(Enrollment, Enrollment.activity_id == Activity.id)
            .filter(Event.id.in_(event_ids))
            .group_by(Event.id, Event.nome, Course.nome, Event.data_inicio)
            .order_by(Event.data_inicio.desc())
            .all()
        )

        pending_certificate_events = []
        with_certificate = 0
        without_certificate = 0
        for row in pending_rows:
            enrollments_count = int(row.enrollments_count or 0)
            cert_generated_count = int(row.cert_generated_count or 0)
            presence_count = int(row.presence_count or 0)
            pending_count = max(enrollments_count - cert_generated_count, 0)

            if enrollments_count > 0 and cert_generated_count > 0:
                with_certificate += 1
            if enrollments_count > 0 and cert_generated_count == 0:
                without_certificate += 1

            if pending_count > 0:
                pending_certificate_events.append({
                    'id': row.id,
                    'name': row.nome,
                    'course': row.course_name or 'Sem curso',
                    'start_date': row.data_inicio.isoformat() if row.data_inicio else None,
                    'enrollments_count': enrollments_count,
                    'presence_count': presence_count,
                    'cert_generated_count': cert_generated_count,
                    'pending_count': pending_count,
                })

        total_pending_certificate_events = len(pending_certificate_events)
        pending_certificate_events = sorted(
            pending_certificate_events,
            key=lambda item: (item['pending_count'], item['presence_count']),
            reverse=True,
        )[:8]

        payload = {
            'summary': {
                'total_events': total_events,
                'active_events': active_events,
                'closed_events': closed_events,
                'total_courses': total_courses,
                'total_enrollments': total_enrollments,
                'unique_students': unique_students,
                'presence_rate': presence_rate,
                'pending_certificate_events': total_pending_certificate_events,
            },
            'events_by_course': events_by_course,
            'students_by_course': students_by_course,
            'status_breakdown': status_breakdown,
            'certificate_pipeline': {
                'with_certificate': with_certificate,
                'without_certificate': without_certificate,
            },
            'pending_certificate_events': pending_certificate_events,
        }

    institutional_query = InstitutionalCertificate.query
    if current_user.role not in ['admin', 'gestor']:
        institutional_query = institutional_query.filter(InstitutionalCertificate.created_by_username == current_user.username)
    institutional_query = institutional_query.filter(InstitutionalCertificate.created_at >= cutoff_datetime)

    institutional_ids = [cert_id for (cert_id,) in institutional_query.with_entities(InstitutionalCertificate.id).all()]

    institutional_summary = {
        'total_certificates': 0,
        'draft_certificates': 0,
        'sent_certificates': 0,
        'archived_certificates': 0,
        'total_recipients': 0,
        'delivered_recipients': 0,
        'pending_recipients': 0,
        'delivery_rate': 0,
    }
    institutional_by_category = []
    institutional_pending = []

    if institutional_ids:
        institutional_scoped = InstitutionalCertificate.query.filter(InstitutionalCertificate.id.in_(institutional_ids))
        institutional_summary['total_certificates'] = institutional_scoped.count()
        institutional_summary['draft_certificates'] = institutional_scoped.filter(InstitutionalCertificate.status == 'RASCUNHO').count()
        institutional_summary['sent_certificates'] = institutional_scoped.filter(InstitutionalCertificate.status == 'ENVIADO').count()
        institutional_summary['archived_certificates'] = institutional_scoped.filter(InstitutionalCertificate.status == 'ARQUIVADO').count()

        recipient_scope = (
            InstitutionalCertificateRecipient.query
            .join(InstitutionalCertificate, InstitutionalCertificate.id == InstitutionalCertificateRecipient.certificate_id)
            .filter(InstitutionalCertificateRecipient.certificate_id.in_(institutional_ids))
        )
        if course_id:
            recipient_scope = (
                recipient_scope
                .join(User, User.username == InstitutionalCertificateRecipient.user_username)
                .filter(User.course_id == course_id)
            )

        total_recipients = recipient_scope.count()
        delivered_recipients = recipient_scope.filter(InstitutionalCertificateRecipient.cert_entregue.is_(True)).count()
        pending_recipients = max(total_recipients - delivered_recipients, 0)
        delivery_rate = round((delivered_recipients / total_recipients) * 100, 2) if total_recipients else 0

        institutional_summary['total_recipients'] = total_recipients
        institutional_summary['delivered_recipients'] = delivered_recipients
        institutional_summary['pending_recipients'] = pending_recipients
        institutional_summary['delivery_rate'] = delivery_rate

        categories_rows = (
            db.session.query(
                InstitutionalCertificateCategory.nome.label('category_name'),
                func.count(InstitutionalCertificate.id).label('certificates_count')
            )
            .select_from(InstitutionalCertificate)
            .outerjoin(InstitutionalCertificateCategory, InstitutionalCertificate.category_id == InstitutionalCertificateCategory.id)
            .filter(InstitutionalCertificate.id.in_(institutional_ids))
            .group_by(InstitutionalCertificateCategory.nome)
            .order_by(func.count(InstitutionalCertificate.id).desc())
            .limit(8)
            .all()
        )
        institutional_by_category = [
            {'category': ((category_name or '').strip() or 'Sem categoria'), 'count': int(certificates_count)}
            for category_name, certificates_count in categories_rows
        ]

        pending_inst_rows = (
            db.session.query(
                InstitutionalCertificate.id,
                InstitutionalCertificate.titulo,
                InstitutionalCertificateCategory.nome.label('category_name'),
                func.count(InstitutionalCertificateRecipient.id).label('recipients_count'),
                func.sum(case((InstitutionalCertificateRecipient.cert_entregue.is_(True), 1), else_=0)).label('delivered_count'),
            )
            .select_from(InstitutionalCertificate)
            .outerjoin(InstitutionalCertificateCategory, InstitutionalCertificate.category_id == InstitutionalCertificateCategory.id)
            .outerjoin(InstitutionalCertificateRecipient, InstitutionalCertificateRecipient.certificate_id == InstitutionalCertificate.id)
            .filter(InstitutionalCertificate.id.in_(institutional_ids))
            .group_by(InstitutionalCertificate.id, InstitutionalCertificate.titulo, InstitutionalCertificateCategory.nome)
            .order_by(InstitutionalCertificate.created_at.desc())
            .all()
        )
        for row in pending_inst_rows:
            recipients_count = int(row.recipients_count or 0)
            delivered_count = int(row.delivered_count or 0)
            pending_count = max(recipients_count - delivered_count, 0)
            if pending_count <= 0:
                continue
            institutional_pending.append({
                'id': row.id,
                'title': row.titulo,
                'category': ((row.category_name or '').strip() or 'Sem categoria'),
                'recipients_count': recipients_count,
                'delivered_count': delivered_count,
                'pending_count': pending_count,
            })

    payload['institutional_summary'] = institutional_summary
    payload['institutional_by_category'] = institutional_by_category
    payload['institutional_pending'] = sorted(
        institutional_pending,
        key=lambda item: item['pending_count'],
        reverse=True,
    )[:8]
    payload['applied_filters'] = {
        'period_days': period_days,
        'course_id': course_id,
        'cutoff_date': cutoff_date.isoformat(),
    }
    payload['generated_at'] = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    return jsonify(payload)
