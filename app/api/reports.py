from flask import Blueprint, jsonify, send_file
from flask_login import login_required, current_user
from app.models import Event, Activity, Enrollment, User, db
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

bp = Blueprint('reports', __name__)

@bp.route('/api/relatorio_inscritos/<int:evt_id>', methods=['GET'])
@login_required
def relatorio_inscritos(evt_id):
    event = Event.query.get(evt_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404
        
    if current_user.role != 'admin' and event.owner_username != current_user.username:
        return jsonify({"erro": "Sem permissão"}), 403
    
    relatorio = []
    for atv in event.activities:
        inscritos = []
        for enroll in atv.enrollments:
            inscritos.append({
                "nome": enroll.nome,
                "cpf": enroll.user_cpf,
                "presente": enroll.presente
            })
        relatorio.append({"atividade": atv.nome, "inscritos": inscritos})
        
    return jsonify(relatorio)

@bp.route('/certificado/<int:evt_id>/<cpf>')
def baixar_certificado(evt_id, cpf):
    # This route is public in the original app? Or at least doesn't check session explicitly, 
    # but uses session in logic? Original code: 
    # user_dados = conn.execute("SELECT nome FROM users WHERE cpf=?", (cpf,)).fetchone()
    # It didn't enforce login strictly in the route decorator, but logic implies it relies on data.
    # It seems to be a download link.
    
    event = Event.query.get(evt_id)
    user = User.query.filter_by(cpf=cpf).first()
    
    # Get confirmed enrollments for this event and user
    # Enrollment -> Activity -> Event
    # We can join.
    
    presencas = db.session.query(Activity).join(Enrollment).filter(
        Enrollment.user_cpf == cpf,
        Enrollment.presente == True,
        Enrollment.event_id == evt_id # Redundant if checking activity.event_id but faster.
    ).all()
    
    if not presencas:
        return "<h1>Erro: Nenhuma presença confirmada.</h1>", 403
    
    total_horas = sum([p.carga_horaria for p in presencas])
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    
    p.setFont("Helvetica-Bold", 26)
    p.drawCentredString(w/2, 700, "CERTIFICADO DE EXTENSÃO")
    p.setFont("Helvetica", 14)
    p.drawCentredString(w/2, 620, "Certificamos que")
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(w/2, 590, user.nome if user else "Participante")
    p.setFont("Helvetica", 12)
    p.drawCentredString(w/2, 570, f"CPF: {cpf}")
    
    p.setFont("Helvetica", 14)
    p.drawCentredString(w/2, 520, f"Participou do evento: {event.nome}")
    
    if total_horas > 0:
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(w/2, 490, f"Carga Horária Total: {total_horas} horas")
    else:
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(w/2, 490, "Participação Confirmada")
    
    y = 420
    p.setFont("Helvetica-Bold", 12)
    p.drawString(80, y, "Atividades Concluídas:")
    y -= 25
    p.setFont("Helvetica", 10)
    
    for item in presencas:
        texto = f"• {item.nome}"
        if item.carga_horaria > 0: texto += f" ({item.carga_horaria}h)"
        if item.data_atv: texto += f" - {item.data_atv}"
        if item.palestrante: texto += f" | {item.palestrante}"
        p.drawString(90, y, texto)
        y -= 15
        
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="certificado.pdf")
