import os
import json
import secrets
import html
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
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

    def _parse_template_elements(self, event):
        """Loads and normalizes template elements with legacy compatibility."""
        legacy_defaults = {
            'txt1': {'text': 'CERTIFICADO', 'x': 50, 'y': 20, 'w': 80, 'h': 10, 'font': 40, 'color': '#1e293b', 'align': 'center', 'bold': True, 'font_family': 'Helvetica'},
            'txt2': {'text': 'Certificamos que {{NOME}} participou do evento {{EVENTO}}.', 'x': 50, 'y': 50, 'w': 70, 'h': 20, 'font': 20, 'color': '#475569', 'align': 'center', 'bold': False, 'font_family': 'Helvetica'},
            'qrcode': {'x': 85, 'y': 85, 'size': 80}
        }

        if not event.cert_template_json:
            return self._normalize_legacy_elements(legacy_defaults)

        try:
            template = json.loads(event.cert_template_json)
        except Exception:
            return self._normalize_legacy_elements(legacy_defaults)

        if isinstance(template, dict) and isinstance(template.get('elements'), list):
            return template.get('elements', [])

        if isinstance(template, dict):
            return self._normalize_legacy_elements(template)

        return self._normalize_legacy_elements(legacy_defaults)

    def _normalize_legacy_elements(self, legacy_dict):
        """Converts old dictionary schema into list-based schema."""
        elements = []
        for idx, (key, config) in enumerate(legacy_dict.items()):
            if key == 'qrcode':
                size = config.get('size')
                elements.append({
                    'id': key,
                    'type': 'qr',
                    'x': config.get('x', 85),
                    'y': config.get('y', 85),
                    'w': config.get('w', 12),
                    'h': config.get('h', 12),
                    'size': size,
                    'zIndex': config.get('zIndex', idx + 1),
                    'locked': config.get('locked', False),
                    'visible': config.get('visible', True)
                })
                continue

            elements.append({
                'id': key,
                'type': config.get('type', 'text'),
                'text': config.get('text', ''),
                'x': config.get('x', 50),
                'y': config.get('y', 50),
                'w': config.get('w', 50),
                'h': config.get('h', 10),
                'font': config.get('font', 20),
                'color': config.get('color', '#000000'),
                'align': config.get('align', 'center'),
                'bold': config.get('bold', False),
                'italic': config.get('italic', False),
                'font_family': config.get('font_family', 'Helvetica'),
                'text_styles': config.get('text_styles', {}),
                'zIndex': config.get('zIndex', idx + 1),
                'locked': config.get('locked', False),
                'visible': config.get('visible', True),
                'src': config.get('src')
            })

        return elements

    def _resolve_font_name(self, family, is_bold=False, is_italic=False):
        family = family or 'Helvetica'
        font_name = family
        if family == 'Helvetica':
            if is_bold and is_italic:
                font_name = "Helvetica-BoldOblique"
            elif is_bold:
                font_name = "Helvetica-Bold"
            elif is_italic:
                font_name = "Helvetica-Oblique"
        elif family == 'Times-Roman':
            if is_bold and is_italic:
                font_name = "Times-BoldItalic"
            elif is_bold:
                font_name = "Times-Bold"
            elif is_italic:
                font_name = "Times-Italic"
        elif family == 'Courier':
            if is_bold and is_italic:
                font_name = "Courier-BoldOblique"
            elif is_bold:
                font_name = "Courier-Bold"
            elif is_italic:
                font_name = "Courier-Oblique"
        return font_name

    @staticmethod
    def _convert_jodit_html(html_content):
        """Converts Jodit-produced HTML to ReportLab Paragraph-compatible markup.

        ReportLab Paragraph supports: <b>, <i>, <u>, <strike>, <br/>, <font>, <a>.
        Other tags are converted to their closest equivalents or stripped.
        """
        import re
        h = html_content or ''
        # Normalize line endings
        h = h.replace('\r\n', ' ').replace('\r', ' ')
        # <strong> -> <b>, <em> -> <i>
        h = re.sub(r'<strong([^>]*)>', '<b>', h, flags=re.IGNORECASE)
        h = re.sub(r'</strong>', '</b>', h, flags=re.IGNORECASE)
        h = re.sub(r'<em([^>]*)>', '<i>', h, flags=re.IGNORECASE)
        h = re.sub(r'</em>', '</i>', h, flags=re.IGNORECASE)
        # <br> normalisation
        h = re.sub(r'<br\s*/?>', '<br/>', h, flags=re.IGNORECASE)
        # <p ...>content</p> -> content<br/>
        h = re.sub(r'<p[^>]*>(.*?)</p>', r'\1<br/>', h, flags=re.IGNORECASE | re.DOTALL)
        # Lists: ul/ol wrappers removed; li -> bullet + line break
        h = re.sub(r'<(ul|ol)[^>]*>', '', h, flags=re.IGNORECASE)
        h = re.sub(r'</(ul|ol)>', '', h, flags=re.IGNORECASE)
        h = re.sub(r'<li[^>]*>', '• ', h, flags=re.IGNORECASE)
        h = re.sub(r'</li>', '<br/>', h, flags=re.IGNORECASE)
        # <span style="color:#..."> -> <font color="...">
        h = re.sub(
            r'<span\s+style="[^"]*?color\s*:\s*(#[\w]+)[^"]*">(.*?)</span>',
            r'<font color="\1">\2</font>',
            h, flags=re.IGNORECASE | re.DOTALL
        )
        # Strip remaining unsupported/unknown tags but preserve their content
        h = re.sub(
            r'<(?!/?(b|i|u|strike|br|font|a)(\s[^>]*)?/?>)[^>]+>',
            '', h, flags=re.IGNORECASE
        )
        # Collapse multiple consecutive <br/>
        h = re.sub(r'(<br/>){3,}', '<br/><br/>', h, flags=re.IGNORECASE)
        return h.strip()

    def _build_rich_text_markup(self, raw_text, text_styles, config, tags):
        text_styles = text_styles or {}
        base_family = config.get('font_family', 'Helvetica')
        base_bold = bool(config.get('bold', False))
        base_italic = bool(config.get('italic', False))
        base_color = config.get('color', '#000000')
        base_size = config.get('font', 20)

        lines = raw_text.split('\n')
        line_markup = []

        for line_idx, line in enumerate(lines):
            line_styles = text_styles.get(str(line_idx), {})
            if not isinstance(line_styles, dict):
                line_styles = {}

            runs = []
            current_state = None
            current_chars = []

            for char_idx, char in enumerate(line):
                char_style = line_styles.get(str(char_idx), {})
                if not isinstance(char_style, dict):
                    char_style = {}

                family = char_style.get('fontFamily', base_family)
                weight = char_style.get('fontWeight', 'bold' if base_bold else 'normal')
                style = char_style.get('fontStyle', 'italic' if base_italic else 'normal')
                color = char_style.get('fill', base_color)
                size = char_style.get('fontSize', base_size)

                font_name = self._resolve_font_name(family, weight == 'bold', style == 'italic')
                state = (font_name, color, size)

                if current_state is None:
                    current_state = state

                if state != current_state:
                    runs.append((current_state, ''.join(current_chars)))
                    current_chars = [char]
                    current_state = state
                else:
                    current_chars.append(char)

            if current_state is not None:
                runs.append((current_state, ''.join(current_chars)))

            if not runs:
                line_markup.append('')
                continue

            chunk_markup = []
            for (font_name, color, size), run_text in runs:
                safe_text = html.escape(run_text)
                chunk_markup.append(
                    f'<font name="{font_name}" color="{color}" size="{size}">{safe_text}</font>'
                )
            line_markup.append(''.join(chunk_markup))

        rich_markup = '<br/>'.join(line_markup)
        for tag, val in tags.items():
            rich_markup = rich_markup.replace(tag, html.escape(str(val)))
        return rich_markup

    def generate_pdf(self, event, user, activities, total_hours, enrollment=None):
        """Generates a single certificate PDF for a user using professional layout blocks."""
        import hashlib
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Frame, KeepInFrame
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        
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
        
        page_width, page_height = landscape(A4)

        c = canvas.Canvas(filepath, pagesize=(page_width, page_height))
        
        # 1. Draw Background
        if event.cert_bg_path and os.path.exists(os.path.join(current_app.root_path, 'static', event.cert_bg_path)):
            c.drawImage(os.path.join(current_app.root_path, 'static', event.cert_bg_path), 0, 0, width=page_width, height=page_height)
        
        # 2. Parse Template
        elements = self._parse_template_elements(event)
        
        # 3. Draw Elements
        tags = {
            '{{NOME}}': user.nome.upper(),
            '{{EVENTO}}': event.nome,
            '{{HORAS}}': str(total_hours),
            '{{DATA}}': event.data_inicio.strftime('%d/%m/%Y') if event.data_inicio else "",
            '{{CPF}}': user.cpf,
            '{{HASH}}': cert_hash
        }

        ordered_elements = sorted(
            [e for e in elements if e.get('visible', True)],
            key=lambda item: item.get('zIndex', 0)
        )

        for config in ordered_elements:
            element_type = config.get('type', 'text')
            element_id = config.get('id', '')

            if element_type == 'qr' or element_id == 'qrcode':
                import qrcode
                from io import BytesIO
                qr = qrcode.QRCode(box_size=10, border=0)
                qr.add_data(validation_url)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white")
                qr_buffer = BytesIO()
                img_qr.save(qr_buffer, format="PNG")
                qr_buffer.seek(0)
                
                abs_x = (config.get('x', 85) / 100) * page_width
                abs_y = (1 - (config.get('y', 85) / 100)) * page_height
                abs_w = (config.get('w', 12) / 100) * page_width
                abs_h = (config.get('h', 12) / 100) * page_height
                qr_size = config.get('size') or min(abs_w, abs_h)
                c.drawInlineImage(img_qr, abs_x - (qr_size/2), abs_y - (qr_size/2), width=qr_size, height=qr_size)
                continue

            if element_type == 'image' and config.get('src'):
                src = config.get('src')
                if src.startswith('/static/'):
                    image_path = os.path.join(current_app.root_path, 'static', src.replace('/static/', '', 1))
                elif src.startswith('static/'):
                    image_path = os.path.join(current_app.root_path, src)
                else:
                    image_path = os.path.join(current_app.root_path, 'static', src)

                if os.path.exists(image_path):
                    abs_w = (config.get('w', 15) / 100) * page_width
                    abs_h = (config.get('h', 15) / 100) * page_height
                    abs_x_center = (config.get('x', 50) / 100) * page_width
                    abs_y_center = (1 - (config.get('y', 50) / 100)) * page_height
                    frame_x = abs_x_center - (abs_w / 2)
                    frame_y = abs_y_center - (abs_h / 2)
                    c.drawImage(image_path, frame_x, frame_y, width=abs_w, height=abs_h, mask='auto')
                continue

            raw_text = config.get('text', '')
            html_content = config.get('html_content') if config.get('is_html') else None
            if not raw_text and not html_content:
                continue
            
            final_text = raw_text
            for tag, val in tags.items():
                final_text = final_text.replace(tag, val)
            
            # Font Construction
            family = config.get('font_family', 'Helvetica')
            is_bold = config.get('bold', False)
            is_italic = config.get('italic', False)
            font_name = self._resolve_font_name(family, is_bold, is_italic)

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

            align_map = {'center': TA_CENTER, 'left': TA_LEFT, 'right': TA_RIGHT, 'justify': TA_JUSTIFY}
            
            style = ParagraphStyle(
                name=f"Style_{element_id or 'text'}",
                fontName=font_name,
                fontSize=(config.get('font', 20) / 1000) * page_width,
                textColor=config.get('color', '#000000'),
                alignment=align_map.get(config.get('align', 'center'), TA_CENTER),
                leading=(config.get('font', 20) / 1000) * page_width * 1.2
            )

            # Determine paragraph content:
            # 1. Jodit HTML (is_html) - rich HTML converted to ReportLab markup
            # 2. Fabric.js per-character styles (text_styles)
            # 3. Plain text fallback
            if html_content:
                substituted_html = html_content
                for tag_k, tag_v in tags.items():
                    substituted_html = substituted_html.replace(tag_k, html.escape(str(tag_v)))
                paragraph_content = self._convert_jodit_html(substituted_html)
            else:
                text_styles = config.get('text_styles', {})
                if isinstance(text_styles, dict) and text_styles:
                    paragraph_content = self._build_rich_text_markup(raw_text, text_styles, config, tags)
                else:
                    paragraph_content = final_text

            p = Paragraph(paragraph_content, style)
            frame_y = abs_y_center - (abs_h / 2)

            # Respect the configured block and shrink text content when it overflows.
            story = [KeepInFrame(abs_w, abs_h, [p], mode='shrink')]
            f = Frame(frame_x, frame_y, abs_w, abs_h, showBoundary=0, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0)
            f.addFromList(story, c)
        
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
