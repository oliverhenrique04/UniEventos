from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from app.models import Activity, Enrollment, db
from app.utils import gerar_hash_dinamico, validar_hash_dinamico
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
    
    enrollment, message = event_service.toggle_enrollment(current_user, atv_id, acao)
    
    if enrollment is None and message in ["Atividade não encontrada", "Lotado!", "Ação inválida"]:
        return jsonify({"erro": message}), 400 if message != "Atividade não encontrada" else 404
        
    return jsonify({"mensagem": message})

@bp.route('/qrcode_atividade/<int:atv_id>')
def qrcode_atividade(atv_id):
    """
    Generates a dynamic QR code for activity check-in.
    The QR code contains a time-limited hash.
    """
    if not atv_id:
        return "ID Inválido", 404
        
    try:
        activity = event_service.get_activity(atv_id)
        if not activity:
            return "Atividade não encontrada", 404
            
        token = gerar_hash_dinamico(atv_id)
        conteudo = f"CHECKIN:{activity.event_id}:{atv_id}:{token}"
        
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
    Validates a QR code scanned by a participant and registers their presence.
    If valid, confirms attendance and returns a success message.
    """
    token_full = request.json.get('token', '')
    try:
        parts = token_full.split(":")
        evt_id = int(parts[1])
        atv_id = int(parts[2])
        hash_rcv = parts[3]
    except (IndexError, ValueError):
        return jsonify({"erro": "Formato de QR Code inválido"}), 400
        
    if not validar_hash_dinamico(atv_id, hash_rcv):
        return jsonify({"erro": "Código expirado ou inválido"}), 400
    
    success, message, enrollment = event_service.confirm_attendance(
        current_user, atv_id, evt_id
    )
    
    if not success:
        return jsonify({"erro": message}), 403
        
    return jsonify({
        "status": "success", 
        "mensagem": message, 
        "download_link": f"/certificado/{evt_id}/{current_user.cpf}"
    })
