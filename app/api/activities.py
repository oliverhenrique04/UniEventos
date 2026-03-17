from flask import Blueprint, request, jsonify, send_file, current_app, url_for
from flask_login import login_required, current_user
from app.models import Activity, Enrollment, db
from app.utils import gerar_hash_dinamico, validar_hash_dinamico, build_absolute_app_url
from app.services.event_service import EventService
import qrcode
from io import BytesIO

bp = Blueprint('activities', __name__, url_prefix='/api')
event_service = EventService()

@bp.route('/toggle_inscricao', methods=['POST'])
@login_required
def toggle_inscricao():
    data = request.json
    atv_id = int(data.get('activity_id'))
    acao = data.get('acao')
    category_id = data.get('categoria_inscricao_id')
    activity = event_service.get_activity(atv_id)
    
    enrollment, message = event_service.toggle_enrollment(
        current_user,
        atv_id,
        acao,
        category_id=category_id,
        actor_user=current_user,
    )
    
    if enrollment is None and message in [
        "Atividade não encontrada",
        "Lotado!",
        "Ação inválida",
        "Selecione uma categoria de inscrição.",
        "Categoria de inscrição inválida.",
        "Categoria de inscrição lotada.",
        "Seu perfil não está habilitado para este evento.",
    ]:
        if message == "Atividade não encontrada":
            return jsonify({"erro": message}), 404
        if message == "Seu perfil não está habilitado para este evento.":
            return jsonify({"erro": message}), 403
        return jsonify({"erro": message}), 400

    current_registration = None
    if activity and activity.event:
        current_registration = event_service.get_event_registration(activity.event.id, current_user.cpf)

    payload = {"mensagem": message}
    if current_registration and current_registration.category:
        payload["categoria_inscricao"] = {
            "id": current_registration.category.id,
            "nome": current_registration.category.nome,
        }
    else:
        payload["categoria_inscricao"] = None
    payload["possui_inscricao_evento"] = bool(
        current_registration
        or (activity and activity.event and event_service.user_has_event_enrollment(activity.event.id, current_user.cpf))
    )

    return jsonify(payload)

@bp.route('/qrcode_atividade/<int:atv_id>')
def qrcode_atividade(atv_id):
    """
    Generates a dynamic QR code for activity check-in as a direct link.
    """
    if not atv_id:
        return "ID Inválido", 404
        
    try:
        activity = event_service.get_activity(atv_id)
        if not activity:
            return "Atividade não encontrada", 404
            
        token = gerar_hash_dinamico(atv_id)
        # Generate a direct URL for scanning
        conteudo = build_absolute_app_url(f"/confirmar_presenca/{atv_id}/{token}")
        
        qr = qrcode.QRCode(box_size=20, border=1)
        qr.add_data(conteudo)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except Exception as e:
        return f"Erro QR: {str(e)}", 500

@bp.route('/validar_presenca', methods=['POST'])
@login_required
def validar_presenca():
    """
    Validates a dynamic QR code and performs a geofencing check if applicable.
    """
    data_rcv = request.json
    token_full = data_rcv.get('token', '')
    user_lat = data_rcv.get('latitude')
    user_lon = data_rcv.get('longitude')
    category_id = data_rcv.get('categoria_inscricao_id')

    try:
        parts = token_full.split(":")
        evt_id = int(parts[1])
        atv_id = int(parts[2])
        hash_rcv = parts[3]
    except (IndexError, ValueError):
        return jsonify({"erro": "Formato de QR Code inválido"}), 400
        
    # 1. Cryptographic Validation (Time-based HMAC)
    if not validar_hash_dinamico(atv_id, hash_rcv):
        return jsonify({"erro": "Código expirado ou inválido (tente novamente)"}), 400
    
    # 2. Geofencing Validation (Physical presence)
    activity = db.session.get(Activity, atv_id)
    if activity and activity.latitude and activity.longitude:
        if not user_lat or not user_lon:
            return jsonify({"erro": "Localização necessária para confirmar presença"}), 403
        
        from app.utils import haversine_distance
        checkin_radius = int(current_app.config.get('CHECKIN_RADIUS_METERS', 500))
        dist = haversine_distance(user_lat, user_lon, activity.latitude, activity.longitude)
        if dist > checkin_radius:
            return jsonify({"erro": f"Você está muito longe do local do evento ({int(dist)}m)"}), 403

    success, message, enrollment = event_service.confirm_attendance(
        current_user,
        atv_id,
        evt_id,
        lat=user_lat,
        lon=user_lon,
        category_id=category_id,
    )
    
    if not success:
        if message == "Atividade não encontrada":
            return jsonify({"erro": message}), 404
        if message in {
            "Selecione uma categoria de inscrição.",
            "Categoria de inscrição inválida.",
            "Categoria de inscrição lotada.",
        }:
            return jsonify({"erro": message}), 400
        return jsonify({"erro": message}), 403
        
    return jsonify({
        "status": "success", 
        "mensagem": message, 
        "download_link": url_for('reports.baixar_certificado', evt_id=evt_id, cpf=current_user.cpf)
    })
