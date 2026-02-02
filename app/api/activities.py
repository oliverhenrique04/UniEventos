from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from app.models import Activity, Enrollment, db
from app.utils import gerar_hash_dinamico, validar_hash_dinamico
import qrcode
from io import BytesIO

bp = Blueprint('activities', __name__, url_prefix='/api')

@bp.route('/toggle_inscricao', methods=['POST'])
@login_required
def toggle_inscricao():
    data = request.json
    atv_id = int(data.get('activity_id'))
    acao = data.get('acao')
    
    activity = Activity.query.get(atv_id)
    if not activity:
        return jsonify({"erro": "Atividade não encontrada"}), 404

    # Check existing enrollment using cpf or username.
    # Model uses user_cpf.
    existing = Enrollment.query.filter_by(activity_id=atv_id, user_cpf=current_user.cpf).first()

    if acao == 'inscrever':
        if existing:
            return jsonify({"mensagem": "Já inscrito"})
        
        count = Enrollment.query.filter_by(activity_id=atv_id).count()
        if activity.vagas != -1 and count >= activity.vagas:
            return jsonify({"erro": "Lotado!"}), 400
        
        enrollment = Enrollment(
            activity_id=atv_id,
            event_id=activity.event_id,
            user_cpf=current_user.cpf,
            nome=current_user.nome,
            presente=False
        )
        db.session.add(enrollment)
        db.session.commit()
        return jsonify({"mensagem": "Inscrição Realizada!"})

    elif acao == 'sair':
        if existing:
            db.session.delete(existing)
            db.session.commit()
        return jsonify({"mensagem": "Desinscrição realizada."})
    
    return jsonify({"erro": "Ação inválida"}), 400

@bp.route('/qrcode_atividade/<int:atv_id>')
def qrcode_atividade(atv_id):
    if not atv_id: return "ID Inválido", 404
    try:
        token = gerar_hash_dinamico(atv_id)
        activity = Activity.query.get(atv_id)
        
        if not activity: return "Atividade não encontrada", 404
        
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
        return "Erro QR", 500

@bp.route('/validar_presenca', methods=['POST'])
@login_required
def validar_presenca():
    token_full = request.json.get('token', '')
    try:
        parts = token_full.split(":")
        evt_id, atv_id, hash_rcv = int(parts[1]), int(parts[2]), parts[3]
    except:
        return jsonify({"erro": "QR Inválido"}), 400
        
    if not validar_hash_dinamico(atv_id, hash_rcv):
        return jsonify({"erro": "Código expirado"}), 400
    
    enrollment = Enrollment.query.filter_by(activity_id=atv_id, user_cpf=current_user.cpf).first()
    
    # Auto-enrollment for fast check-in
    if not enrollment:
        activity = Activity.query.get(atv_id)
        if activity and activity.nome == "Check-in Presença":
            enrollment = Enrollment(
                activity_id=atv_id,
                event_id=evt_id,
                user_cpf=current_user.cpf,
                nome=current_user.nome,
                presente=True
            )
            db.session.add(enrollment)
            db.session.commit()
            return jsonify({"status": "success", "mensagem": "Presença Registrada!", "download_link": f"/certificado/{evt_id}/{current_user.cpf}"})
        else:
            return jsonify({"erro": "Você não se inscreveu."}), 403

    enrollment.presente = True
    db.session.commit()
        
    return jsonify({"status": "success", "mensagem": "Presença confirmada!", "download_link": f"/certificado/{evt_id}/{current_user.cpf}"})
