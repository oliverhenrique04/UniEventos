from flask import Blueprint, jsonify, send_file, request, current_app
from flask_login import login_required, current_user
from app.services.report_service import ReportService
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

bp = Blueprint('reports', __name__)
report_service = ReportService()

@bp.route('/api/relatorio_inscritos/<int:evt_id>', methods=['GET'])
@login_required
def relatorio_inscritos(evt_id):
    event = report_service.event_repo.get_by_id(evt_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404
        
    if current_user.role != 'admin' and event.owner_username != current_user.username:
        return jsonify({"erro": "Sem permissão"}), 403
        
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    
    pagination = report_service.get_event_enrollment_report_paginated(evt_id, page=page, filter_nome=search)
    
    return jsonify({
        "items": [{
            "nome": e.nome,
            "cpf": e.user_cpf,
            "presente": e.presente,
            "atividade": e.activity.nome if e.activity else "N/A"
        } for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/certificado/<int:evt_id>/<cpf>')
def baixar_certificado(evt_id, cpf):
    data = report_service.get_certificate_data(evt_id, cpf)
    if not data:
        return "<h1>Erro: Nenhuma presença confirmada.</h1>", 403
        
    event = data['event']
    user = data['user']
    activities = data['activities']
    total_hours = data['total_hours']
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    
    p.setFont("Helvetica-Bold", 26)
    p.drawCentredString(w/2, 700, "CERTIFICADO DE EXTENSÃO")
    p.setFont("Helvetica", 14)
    p.drawCentredString(w/2, 620, "Certificamos que")
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(w/2, 590, user.nome)
    p.setFont("Helvetica", 12)
    p.drawCentredString(w/2, 570, f"CPF: {cpf}")
    
    p.setFont("Helvetica", 14)
    p.drawCentredString(w/2, 520, f"Participou do evento: {event.nome}")
    
    if total_hours > 0:
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(w/2, 490, f"Carga Horária Total: {total_hours} horas")
    else:
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(w/2, 490, "Participação Confirmada")
    
    y = 420
    p.setFont("Helvetica-Bold", 12)
    p.drawString(80, y, "Atividades Concluídas:")
    y -= 25
    p.setFont("Helvetica", 10)
    
    for item in activities:
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
