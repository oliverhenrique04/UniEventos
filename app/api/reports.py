from flask import Blueprint, jsonify, send_file
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
    # Permission check should ideally be in service or here. 
    # Service doesn't know about current_user usually, so controller checks permissions.
    # But for "is owner", we need to fetch event.
    # I'll fetch event in service and check here, or let service return None/raise error.
    # The legacy code checked owner.
    # My ReportService.get_event_enrollment_report returns list or None.
    # I should check permission before calling service? 
    # Or fetch event -> check -> call service.
    # But service encapsulates logic.
    # Let's keep permission check logic "light" here.
    # But wait, to check permission I need the event owner.
    # I will modify this to be consistent with previous logic.
    
    # Actually, let's instantiate Repository here just for check? No, that breaks the pattern.
    # Service should probably handle access control or I provide the user to the service.
    # But clean architecture says "Controller handles HTTP, Service handles Business".
    # Access control is business logic? Or security?
    # I'll stick to: Controller calls Service.
    
    # I'll trust the previous logic which fetched event.
    # I can add `get_event` to `EventService`? Or just use `ReportService`?
    # Let's use `report_service` to get data, but wait, permission check...
    # I will add a helper to `EventRepository` accessed via `ReportService`?
    # Or just let `ReportService` return the event object too?
    
    # Simple approach: 
    # `report_service.get_event_enrollment_report` returns data.
    # But I need to check owner.
    # I'll assume the service returns the event object or I add a method to check ownership.
    # Actually, `EventRepository` has `get_by_id`.
    # I can use `report_service.event_repo.get_by_id(evt_id)`? 
    # Ideally Controller shouldn't touch repo.
    # I'll add `get_event_for_report(evt_id, current_user)` to service?
    
    # Let's stick to the current implementation of `ReportService` which just returns data.
    # But I can't check permission if I don't have the event.
    # I will modify `ReportService` to return `(event, report_data)` or similar.
    # Or I'll just skip permission check strictly inside the service (return error if not allowed)?
    # Better: Controller asks Service "get report for this event". 
    # Service gets event. Service returns data.
    # But Controller needs to check "is this user allowed?".
    
    # Re-reading `api/reports.py`:
    # if current_user.role != 'admin' and event.owner_username != current_user.username:
    
    # I will rely on `report_service.event_repo` being accessible or add `get_event_owner(id)` to service.
    # Accessing `service.repo` is a pragmatic shortcut often used in Python.
    # But let's be cleaner.
    # I'll update `ReportService` to `get_event_metadata(id)`?
    # Or just `get_event_enrollment_report` returns `(event, data)`.
    
    # Wait, I already wrote `ReportService`. It returns `relatorio` (list) or `None`.
    # It consumes `get_by_id`.
    # I will just invoke it. But I miss the permission check.
    # I will update `ReportService` to take `user` and perform the check?
    # Yes, passing `current_user` to service methods is common for authorization.
    
    # But `ReportService` in previous step didn't have user check.
    # I will modify `api/reports.py` to:
    # 1. Ask service for event (I need a method for this, or just use the repo if I must).
    # 2. Check perm.
    # 3. Ask service for report.
    
    # Since I cannot modify Service in this `replace` call (it targets `api/reports.py`),
    # I will rely on `report_service.event_repo.get_by_id(evt_id)` which is available since python attributes are public.
    # It's a slight coupling but acceptable for "Controller using Service's capabilities".
    
    event = report_service.event_repo.get_by_id(evt_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404
        
    if current_user.role != 'admin' and event.owner_username != current_user.username:
        return jsonify({"erro": "Sem permissão"}), 403
        
    relatorio = report_service.get_event_enrollment_report(evt_id)
    return jsonify(relatorio)

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
