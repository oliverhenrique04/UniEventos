import json
from flask import Blueprint, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.models import Event, Activity, Enrollment, InstitutionalCertificate, InstitutionalCertificateRecipient, db
from app.services.event_service import EventService
from app.serializers import serialize_event
from datetime import datetime

bp = Blueprint('events', __name__, url_prefix='/api')
event_service = EventService()


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
    if current_user.role == 'participante':
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    
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
    
    try:
        event, message = event_service.update_event(
            evt_id, current_user.username, current_user.role, data
        )
        
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
    
    pagination = event_service.list_events_paginated(page=page, filters=filters)
    
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
    status = request.json.get('presente')
    success, msg = event_service.toggle_attendance_manual(enrollment_id, status)
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/deletar_evento/<int:event_id>', methods=['DELETE'])
@login_required
def deletar_evento(event_id):
    """Removes an event and all its data."""
    success, msg = event_service.delete_event(event_id, current_user.username, current_user.role)
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
