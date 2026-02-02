from flask import Blueprint, request, jsonify, session, send_file, current_app
from app.db import get_db
import time
import hashlib
import qrcode
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

participant_bp = Blueprint('participant', __name__)

def gerar_hash_dinamico(activity_id):
    timestamp = int(time.time() / 30)
    # Acesso a app.secret_key via current_app
    raw = f"{activity_id}:{timestamp}:{current_app.secret_key}"
    return hashlib.sha256(raw.encode()).hexdigest()

def validar_hash_dinamico(activity_id, token_recebido):
    timestamp_atual = int(time.time() / 30)
    for t in [timestamp_atual, timestamp_atual - 1]:
        raw = f"{activity_id}:{t}:{current_app.secret_key}"
        if token_recebido == hashlib.sha256(raw.encode()).hexdigest():
            return True
    return False

@participant_bp.route('/api/toggle_inscricao', methods=['POST'])
def toggle_inscricao():
    user = session.get('user')
    if not user: return jsonify({"erro": "Sessão expirada"}), 401
    d = request.json
    atv_id = int(d.get('activity_id'))
    acao = d.get('acao')
    conn = get_db()
    atv = conn.execute("SELECT * FROM activities WHERE id=?", (atv_id,)).fetchone()
    if not atv: conn.close(); return jsonify({"erro": "Atividade não encontrada"}), 404

    if acao == 'inscrever':
        ja_inscrito = conn.execute("SELECT * FROM activity_enrollments WHERE activity_id=? AND cpf=?", (atv_id, user['cpf'])).fetchone()
        if ja_inscrito: conn.close(); return jsonify({"mensagem": "Já inscrito"})
        
        count = conn.execute("SELECT COUNT(*) FROM activity_enrollments WHERE activity_id=?", (atv_id,)).fetchone()[0]
        if atv['vagas'] != -1 and count >= atv['vagas']: conn.close(); return jsonify({"erro": "Lotado!"}), 400
        
        conn.execute("INSERT INTO activity_enrollments (activity_id, event_id, cpf, nome, presente) VALUES (?, ?, ?, ?, 0)", (atv_id, atv['event_id'], user['cpf'], user['nome']))
        conn.commit()
        return jsonify({"mensagem": "Inscrição Realizada!"})

    elif acao == 'sair':
        conn.execute("DELETE FROM activity_enrollments WHERE activity_id=? AND cpf=?", (atv_id, user['cpf']))
        conn.commit()
        return jsonify({"mensagem": "Desinscrição realizada."})
    return jsonify({"erro": "Ação inválida"}), 400

@participant_bp.route('/api/qrcode_atividade/<int:atv_id>')
def qrcode_atividade(atv_id):
    if not atv_id: return "ID Inválido", 404
    try:
        token = gerar_hash_dinamico(atv_id)
        conn = get_db()
        atv = conn.execute("SELECT event_id FROM activities WHERE id=?", (atv_id,)).fetchone()
        conn.close()
        if not atv: return "Atividade não encontrada", 404
        
        conteudo = f"CHECKIN:{atv['event_id']}:{atv_id}:{token}"
        qr = qrcode.QRCode(box_size=20, border=1)
        qr.add_data(conteudo)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except: return "Erro QR", 500

@participant_bp.route('/api/validar_presenca', methods=['POST'])
def validar_presenca():
    user = session.get('user')
    if not user: return jsonify({"erro": "Faça login novamente"}), 401
    token_full = request.json.get('token', '')
    try:
        parts = token_full.split(":")
        evt_id, atv_id, hash_rcv = int(parts[1]), int(parts[2]), parts[3]
    except: return jsonify({"erro": "QR Inválido"}), 400
        
    if not validar_hash_dinamico(atv_id, hash_rcv): return jsonify({"erro": "Código expirado"}), 400
    
    conn = get_db()
    inscricao = conn.execute("SELECT * FROM activity_enrollments WHERE activity_id=? AND cpf=?", (atv_id, user['cpf'])).fetchone()
    
    if not inscricao:
        atv = conn.execute("SELECT * FROM activities WHERE id=?", (atv_id,)).fetchone()
        if atv and atv['nome'] == "Check-in Presença":
             conn.execute("INSERT INTO activity_enrollments (activity_id, event_id, cpf, nome, presente) VALUES (?, ?, ?, ?, 1)", (atv_id, evt_id, user['cpf'], user['nome']))
             conn.commit()
             conn.close()
             return jsonify({"status": "success", "mensagem": "Presença Registrada!", "download_link": f"/certificado/{evt_id}/{user['cpf']}"})
        else:
            conn.close()
            return jsonify({"erro": "Você não se inscreveu."}), 403

    conn.execute("UPDATE activity_enrollments SET presente=1 WHERE id=?", (inscricao['id'],))
    conn.commit()
    return jsonify({"status": "success", "mensagem": "Presença confirmada!", "download_link": f"/certificado/{evt_id}/{user['cpf']}"})

@participant_bp.route('/certificado/<int:evt_id>/<cpf>')
def baixar_certificado(evt_id, cpf):
    conn = get_db()
    evt = conn.execute("SELECT * FROM events WHERE id=?", (evt_id,)).fetchone()
    presencas = conn.execute('''SELECT a.nome, a.carga_horaria, a.palestrante, a.data_atv FROM activity_enrollments ae JOIN activities a ON ae.activity_id = a.id WHERE ae.event_id = ? AND ae.cpf = ? AND ae.presente = 1''', (evt_id, cpf)).fetchall()
    user_dados = conn.execute("SELECT nome FROM users WHERE cpf=?", (cpf,)).fetchone()
    conn.close()
    
    if not presencas: return "<h1>Erro: Nenhuma presença confirmada.</h1>", 403
    total_horas = sum([p['carga_horaria'] for p in presencas])
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    p.setFont("Helvetica-Bold", 26); p.drawCentredString(w/2, 700, "CERTIFICADO DE EXTENSÃO")
    p.setFont("Helvetica", 14); p.drawCentredString(w/2, 620, "Certificamos que")
    p.setFont("Helvetica-Bold", 18); p.drawCentredString(w/2, 590, user_dados['nome'] if user_dados else "Participante")
    p.setFont("Helvetica", 12); p.drawCentredString(w/2, 570, f"CPF: {cpf}")
    p.setFont("Helvetica", 14); p.drawCentredString(w/2, 520, f"Participou do evento: {evt['nome']}")
    if total_horas > 0:
        p.setFont("Helvetica-Bold", 14); p.drawCentredString(w/2, 490, f"Carga Horária Total: {total_horas} horas")
    else:
        p.setFont("Helvetica-Bold", 14); p.drawCentredString(w/2, 490, "Participação Confirmada")
    y = 420; p.setFont("Helvetica-Bold", 12); p.drawString(80, y, "Atividades Concluídas:"); y -= 25; p.setFont("Helvetica", 10)
    for item in presencas:
        texto = f"• {item['nome']}"; 
        if item['carga_horaria'] > 0: texto += f" ({item['carga_horaria']}h)"
        if item['data_atv']: texto += f" - {item['data_atv']}"; 
        if item['palestrante']: texto += f" | {item['palestrante']}";
        p.drawString(90, y, texto); y -= 15
    p.showPage(); p.save(); buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="certificado.pdf")