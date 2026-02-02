import os
import json
import secrets
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter
from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.services.notification_service import NotificationService
from flask import current_app

class CertificateService:
    """Service for managing, generating and distributing academic certificates."""
    
    def __init__(self):
        self.event_repo = EventRepository()
        self.user_repo = UserRepository()
        self.activity_repo = ActivityRepository()
        self.notifier = NotificationService()

    def generate_pdf(self, event, user, activities, total_hours, enrollment=None):
        """Generates a single certificate PDF for a user using professional layout blocks."""
        import hashlib
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Frame
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        
        # 0. Handle Validation Hash
        if enrollment and not enrollment.cert_hash:
            raw = f"{event.id}-{user.cpf}-{secrets.token_hex(8)}"
            enrollment.cert_hash = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
            from app.extensions import db
            db.session.commit()
        
        cert_hash = enrollment.cert_hash if enrollment else "VALID-SAMPLE-HASH"
        validation_url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/validar/{cert_hash}"

        filename = f"cert_{event.id}_{user.cpf}.pdf"
        filepath = os.path.join(current_app.root_path, 'static', 'certificates', 'generated', filename)
        
        from PIL import Image as PILImage
        page_width, page_height = landscape(letter) 
        
        if event.cert_bg_path and os.path.exists(os.path.join(current_app.root_path, 'static', event.cert_bg_path)):
            full_bg_path = os.path.join(current_app.root_path, 'static', event.cert_bg_path)
            with PILImage.open(full_bg_path) as img:
                img_w, img_h = img.size
                page_height = (img_h / img_w) * page_width

        c = canvas.Canvas(filepath, pagesize=(page_width, page_height))
        
        # 1. Draw Background
        if event.cert_bg_path and os.path.exists(os.path.join(current_app.root_path, 'static', event.cert_bg_path)):
            c.drawImage(os.path.join(current_app.root_path, 'static', event.cert_bg_path), 0, 0, width=page_width, height=page_height)
        
        # 2. Parse Template
        elements = {
            'txt1': {'text': 'CERTIFICADO', 'x': 50, 'y': 20, 'w': 80, 'h': 10, 'font': 40, 'color': '#1e293b', 'align': 'center', 'bold': True, 'font_family': 'Helvetica'},
            'txt2': {'text': 'Certificamos que {{NOME}} participou do evento {{EVENTO}}.', 'x': 50, 'y': 50, 'w': 70, 'h': 20, 'font': 20, 'color': '#475569', 'align': 'center', 'bold': False, 'font_family': 'Helvetica'},
            'qrcode': {'x': 85, 'y': 85, 'size': 80}
        }
        
        if event.cert_template_json:
            try:
                elements = json.loads(event.cert_template_json)
            except: pass
        
        # 3. Draw Elements
        tags = {
            '{{NOME}}': user.nome.upper(),
            '{{EVENTO}}': event.nome,
            '{{HORAS}}': str(total_hours),
            '{{DATA}}': f"{event.data_inicio.split('-')[::-1][0]}/{event.data_inicio.split('-')[::-1][1]}/{event.data_inicio.split('-')[::-1][2]}" if event.data_inicio else "",
            '{{CPF}}': user.cpf,
            '{{HASH}}': cert_hash
        }

        for key, config in elements.items():
            if key == 'qrcode':
                import qrcode
                from io import BytesIO
                qr = qrcode.QRCode(box_size=10, border=0)
                qr.add_data(validation_url)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white")
                qr_buffer = BytesIO()
                img_qr.save(qr_buffer, format="PNG")
                qr_buffer.seek(0)
                
                abs_x = (config['x'] / 100) * page_width
                abs_y = (1 - (config['y'] / 100)) * page_height
                qr_size = config.get('size', 80)
                c.drawInlineImage(img_qr, abs_x - (qr_size/2), abs_y - (qr_size/2), width=qr_size, height=qr_size)
                continue

            raw_text = config.get('text', '')
            if not raw_text: continue
            
            final_text = raw_text
            for tag, val in tags.items():
                final_text = final_text.replace(tag, val)
            
            # Font Construction
            family = config.get('font_family', 'Helvetica')
            is_bold = config.get('bold', False)
            is_italic = config.get('italic', False)
            
            font_name = family
            if family == 'Helvetica':
                if is_bold and is_italic: font_name = "Helvetica-BoldOblique"
                elif is_bold: font_name = "Helvetica-Bold"
                elif is_italic: font_name = "Helvetica-Oblique"
            elif family == 'Times-Roman':
                if is_bold and is_italic: font_name = "Times-BoldItalic"
                elif is_bold: font_name = "Times-Bold"
                elif is_italic: font_name = "Times-Italic"
            elif family == 'Courier':
                if is_bold and is_italic: font_name = "Courier-BoldOblique"
                elif is_bold: font_name = "Courier-Bold"
                elif is_italic: font_name = "Courier-Oblique"

            # Dimensions
            w_perc = config.get('w', 50)
            h_perc = config.get('h', 10)
            abs_w = (w_perc / 100) * page_width
            abs_h = (h_perc / 100) * page_height
            
            # Position (anchor at center)
            abs_x_center = (config['x'] / 100) * page_width
            abs_y_center = (1 - (config['y'] / 100)) * page_height
            
            frame_x = abs_x_center - (abs_w / 2)
            frame_y = abs_y_center - (abs_h / 2)

            align_map = {'center': TA_CENTER, 'left': TA_LEFT, 'right': TA_RIGHT}
            
            style = ParagraphStyle(
                name=f'Style_{key}',
                fontName=font_name,
                fontSize=(config.get('font', 20) / 1000) * page_width,
                textColor=config.get('color', '#000000'),
                alignment=align_map.get(config.get('align', 'center'), TA_CENTER),
                leading=(config.get('font', 20) / 1000) * page_width * 1.2
            )

            p = Paragraph(final_text, style)
            f = Frame(frame_x, frame_y, abs_w, abs_h, showBoundary=0, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0)
            f.addFromList([p], c)
        
        c.showPage()
        c.save()
        return filepath
        
        c.showPage()
        c.save()
        return filepath

    def queue_event_certificates(self, event_id):
        """Queues certificate delivery for all present participants of an event."""
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return False, "Evento não encontrado"
            
        # Group by user to sum hours across activities of the same event
        # Note: In a 'PADRAO' event, a user might be in multiple activities.
        # We need the enrollment record to store the hash. Usually there's one enrollment per activity.
        # Let's use the first enrollment found to store the 'Event Certificate Hash'.
        
        user_stats = {} # cpf -> {user, total_hours, first_enrollment}
        
        for atv in event.activities:
            for enroll in atv.enrollments:
                if enroll.presente:
                    if enroll.user_cpf not in user_stats:
                        user = self.user_repo.get_by_cpf(enroll.user_cpf)
                        if user:
                            user_stats[enroll.user_cpf] = {
                                'user': user,
                                'hours': 0,
                                'enrollment': enroll
                            }
                    if enroll.user_cpf in user_stats:
                        user_stats[enroll.user_cpf]['hours'] += (atv.carga_horaria or 0)

        count = 0
        for cpf, data in user_stats.items():
            user = data['user']
            if not user.email: continue
                
            # Generate PDF passing the enrollment to generate/store hash
            pdf_path = self.generate_pdf(event, user, [], data['hours'], enrollment=data['enrollment'])
            
            # Queue Email
            self.notifier.send_email_task(
                to_email=user.email,
                subject=f"Seu Certificado: {event.nome}",
                body=f"Olá {user.nome}, seu certificado de participação no evento {event.nome} está disponível para validação em nossa plataforma e segue em anexo.",
                attachment_path=pdf_path
            )
            
            # Update tracking
            from datetime import datetime
            data['enrollment'].cert_data_envio = datetime.now()
            data['enrollment'].cert_entregue = True
            from app.extensions import db
            db.session.commit()
            
            count += 1
            
        return True, f"{count} certificados colocados na fila de envio."

    def update_config(self, event_id, bg_path=None, template_json=None):
        """Updates certificate configuration for an event."""
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return False
            
        if bg_path is not None:
            event.cert_bg_path = bg_path if bg_path != "" else None
        if template_json:
            event.cert_template_json = template_json
            
        self.event_repo.save(event)
        return True
