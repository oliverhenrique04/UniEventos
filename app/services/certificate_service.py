import os
import json
import secrets
import html
import re
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.services.notification_service import NotificationService
from app.extensions import db
from flask import current_app, has_app_context
from app.utils import build_absolute_app_url, current_certificate_issue_date_label

class CertificateService:
    """Service for managing, generating and distributing academic certificates."""

    SUPPORTED_FONT_FAMILIES = ('Helvetica', 'Times-Roman', 'Courier')
    PAGE_WIDTH_MM = 297
    PAGE_HEIGHT_MM = 210
    DEFAULT_FIXED_LAYOUT_MM = {
        'name_x': 30.0,
        'name_y': 65.0,
        'name_w': 240.0,
        'name_h': 12.0,
        'name_font': 24.0,
        'qr_x': 12.0,
        'qr_y': 108.0,
        'qr_size': 36.0,
        'hash_x': 12.0,
        'hash_y': 150.0,
        'hash_w': 60.0,
        'hash_h': 8.0,
        'date_x': 12.0,
        'date_y': 195.0,
        'date_w': 78.0,
        'date_h': 8.0,
    }
    
    def __init__(self):
        self.event_repo = EventRepository()
        self.user_repo = UserRepository()
        self.activity_repo = ActivityRepository()
        self.notifier = NotificationService()

    @classmethod
    def _config_float(cls, key, default):
        raw = current_app.config.get(key, default) if has_app_context() else default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _pct_x_from_mm(cls, value_mm):
        return (float(value_mm) / cls.PAGE_WIDTH_MM) * 100

    @classmethod
    def _pct_y_from_mm(cls, value_mm):
        return (float(value_mm) / cls.PAGE_HEIGHT_MM) * 100

    @classmethod
    def _px_from_mm_x(cls, value_mm, canvas_width_px=1000):
        return (float(value_mm) / cls.PAGE_WIDTH_MM) * canvas_width_px

    @classmethod
    def _box_from_top_left_mm(cls, x_mm, y_mm, width_mm, height_mm):
        return {
            'x': cls._pct_x_from_mm(float(x_mm) + (float(width_mm) / 2)),
            'y': cls._pct_y_from_mm(float(y_mm) + (float(height_mm) / 2)),
            'w': cls._pct_x_from_mm(width_mm),
            'h': cls._pct_y_from_mm(height_mm),
        }

    @classmethod
    def _designer_mode_for_entity(cls, event):
        mode = getattr(event, 'designer_mode', None)
        if mode in {'event', 'institutional'}:
            return mode
        return 'institutional' if getattr(event, 'is_institutional_certificate', False) else 'event'

    @classmethod
    def get_fixed_validation_elements(cls, designer_mode='event'):
        layout = {
            'name_x': cls._config_float('CERTIFICATE_NAME_DEFAULT_X_MM', cls.DEFAULT_FIXED_LAYOUT_MM['name_x']),
            'name_y': cls._config_float('CERTIFICATE_NAME_DEFAULT_Y_MM', cls.DEFAULT_FIXED_LAYOUT_MM['name_y']),
            'name_w': cls._config_float('CERTIFICATE_NAME_DEFAULT_W_MM', cls.DEFAULT_FIXED_LAYOUT_MM['name_w']),
            'name_h': cls._config_float('CERTIFICATE_NAME_DEFAULT_H_MM', cls.DEFAULT_FIXED_LAYOUT_MM['name_h']),
            'name_font': cls._config_float('CERTIFICATE_NAME_DEFAULT_FONT_SIZE', cls.DEFAULT_FIXED_LAYOUT_MM['name_font']),
            'qr_x': cls._config_float('CERTIFICATE_QR_DEFAULT_X_MM', cls.DEFAULT_FIXED_LAYOUT_MM['qr_x']),
            'qr_y': cls._config_float('CERTIFICATE_QR_DEFAULT_Y_MM', cls.DEFAULT_FIXED_LAYOUT_MM['qr_y']),
            'qr_size': cls._config_float('CERTIFICATE_QR_DEFAULT_SIZE_MM', cls.DEFAULT_FIXED_LAYOUT_MM['qr_size']),
            'hash_x': cls._config_float('CERTIFICATE_HASH_DEFAULT_X_MM', cls.DEFAULT_FIXED_LAYOUT_MM['hash_x']),
            'hash_y': cls._config_float('CERTIFICATE_HASH_DEFAULT_Y_MM', cls.DEFAULT_FIXED_LAYOUT_MM['hash_y']),
            'hash_w': cls.DEFAULT_FIXED_LAYOUT_MM['hash_w'],
            'hash_h': cls.DEFAULT_FIXED_LAYOUT_MM['hash_h'],
            'date_x': cls._config_float('CERTIFICATE_DATE_DEFAULT_X_MM', cls.DEFAULT_FIXED_LAYOUT_MM['date_x']),
            'date_y': cls._config_float('CERTIFICATE_DATE_DEFAULT_Y_MM', cls.DEFAULT_FIXED_LAYOUT_MM['date_y']),
            'date_w': cls.DEFAULT_FIXED_LAYOUT_MM['date_w'],
            'date_h': cls.DEFAULT_FIXED_LAYOUT_MM['date_h'],
        }

        name_box = cls._box_from_top_left_mm(layout['name_x'], layout['name_y'], layout['name_w'], layout['name_h'])
        date_box = cls._box_from_top_left_mm(layout['date_x'], layout['date_y'], layout['date_w'], layout['date_h'])
        hash_box = cls._box_from_top_left_mm(layout['hash_x'], layout['hash_y'], layout['hash_w'], layout['hash_h'])
        qr_box = cls._box_from_top_left_mm(layout['qr_x'], layout['qr_y'], layout['qr_size'], layout['qr_size'])
        qr_canvas_size = int(round(cls._px_from_mm_x(layout['qr_size'])))
        name_tag = '{{RECIPIENT_NAME}}' if designer_mode == 'institutional' else '{{NOME}}'

        return [
            {
                'id': 'name_fixed',
                'type': 'text',
                'text': name_tag,
                **name_box,
                'font': layout['name_font'],
                'color': '#0f172a',
                'align': 'center',
                'bold': True,
                'italic': False,
                'font_family': 'Helvetica',
                'zIndex': 2,
                'locked': True,
                'visible': True,
                'auto_fit': True,
            },
            {
                'id': 'date_fixed',
                'type': 'text',
                'text': 'Data de Emissão: {{DATA}}',
                **date_box,
                'font': 11,
                'color': '#64748b',
                'align': 'left',
                'bold': False,
                'italic': False,
                'font_family': 'Helvetica',
                'zIndex': 4,
                'locked': True,
                'visible': True,
                'auto_fit': True,
            },
            {
                'id': 'hash',
                'type': 'text',
                'text': '{{HASH}}',
                **hash_box,
                'font': 16,
                'color': '#94a3b8',
                'align': 'left',
                'bold': False,
                'italic': False,
                'font_family': 'Courier',
                'zIndex': 5,
                'locked': True,
                'visible': True,
                'auto_fit': False,
            },
            {
                'id': 'qrcode',
                'type': 'qr',
                **qr_box,
                'size': qr_canvas_size,
                'zIndex': 6,
                'locked': True,
                'visible': True,
            },
        ]
    
    @classmethod
    def build_default_template(cls, designer_mode='event', bg=''):
        text_elements = []
        if designer_mode == 'institutional':
            text_elements.append({
                'id': 'txt1',
                'type': 'text',
                'text': 'CERTIFICADO INSTITUCIONAL',
                'x': 50,
                'y': 20,
                'w': 80,
                'h': 8,
                'font': 34,
                'color': '#1e293b',
                'align': 'center',
                'bold': True,
                'italic': False,
                'font_family': 'Helvetica',
                'zIndex': 1,
                'locked': False,
                'visible': True,
            })

        text_elements.append({
        'id': 'txt2',
        'type': 'text',
        'text': (
            'Certificamos que {{RECIPIENT_NAME}} participou de {{CERTIFICATE_TITLE}}.'
            if designer_mode == 'institutional'
            else 'Certificamos que {{NOME}}, CPF {{CPF}}, participou do evento {{EVENTO}}.'
        ),
        'x': 50,
        'y': 50,
        'w': 82 if designer_mode == 'event' else 80,
        'h': 24,
        'font': 22,
        'color': '#334155',
        'align': 'center',
        'bold': False,
        'italic': False,
        'font_family': 'Helvetica',
        'zIndex': 3,
        'locked': False,
        'visible': True,
    })

        return {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'bg': str(bg or '').strip(),
            'elements': text_elements + json.loads(json.dumps(cls.get_fixed_validation_elements(designer_mode=designer_mode))),
        }

    @classmethod
    def normalize_font_family(cls, family):
        raw = str(family or '').strip().strip('"\'')
        lowered = raw.lower()

        if not raw:
            return 'Helvetica'
        if raw in cls.SUPPORTED_FONT_FAMILIES:
            return raw
        if 'courier' in lowered or 'mono' in lowered:
            return 'Courier'
        if 'sans' in lowered or lowered in {'arial', 'helvetica', 'inter', 'roboto', 'system-ui'}:
            return 'Helvetica'
        if 'times' in lowered or lowered in {'georgia', 'garamond'} or (
            'serif' in lowered and 'sans' not in lowered
        ):
            return 'Times-Roman'
        return 'Helvetica'

    @classmethod
    def _normalize_text_styles(cls, text_styles):
        if not isinstance(text_styles, dict):
            return {}

        normalized = {}
        for line_key, line_styles in text_styles.items():
            if not isinstance(line_styles, dict):
                continue

            compact_line = {}
            for char_key, style in line_styles.items():
                if not isinstance(style, dict):
                    continue

                compact_style = dict(style)
                if compact_style.get('fontFamily'):
                    compact_style['fontFamily'] = cls.normalize_font_family(compact_style.get('fontFamily'))

                font_size = compact_style.get('fontSize')
                if font_size is not None:
                    try:
                        compact_style['fontSize'] = max(8, float(font_size))
                    except (TypeError, ValueError):
                        compact_style.pop('fontSize', None)

                compact_line[str(char_key)] = compact_style

            if compact_line:
                normalized[str(line_key)] = compact_line

        return normalized

    @classmethod
    def normalize_template_payload(cls, template, designer_mode='event'):
        def _as_int(value, default):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def _as_float(value, default):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        if not isinstance(template, dict):
            template = {}

        raw_document = template.get('document') if isinstance(template.get('document'), dict) else {}
        raw_elements = template.get('elements')

        normalized = {
            'version': 2,
            'document': {
                'gridSize': max(1, min(10, _as_int(raw_document.get('gridSize', 2) or 2, 2))),
                'snap': raw_document.get('snap', True) is not False,
                'guides': raw_document.get('guides', True) is not False,
            },
            'bg': str(template.get('bg') or '').strip(),
            'elements': [],
        }

        if not isinstance(raw_elements, list):
            raw_elements = []

        fixed_elements = cls.get_fixed_validation_elements(designer_mode=designer_mode)
        fixed_element_ids = {item['id'] for item in fixed_elements}
        fixed_elements_by_id = {item['id']: item for item in fixed_elements}
        seen_fixed_ids = set()
        normalized_elements = []

        for idx, element in enumerate(raw_elements):
            if not isinstance(element, dict):
                continue

            element_id = str(element.get('id') or f'el_{idx}').strip() or f'el_{idx}'
            is_fixed_validation_element = element_id in fixed_element_ids
            if element_id in fixed_element_ids:
                if element_id in seen_fixed_ids:
                    continue
                seen_fixed_ids.add(element_id)

            element_type = element.get('type') or ('qr' if element_id == 'qrcode' else 'text')
            if element_id == 'qrcode':
                element_type = 'qr'

            base = {
                'id': element_id,
                'type': element_type,
                'x': _as_float(element.get('x', 50) or 50, 50),
                'y': _as_float(element.get('y', 50) or 50, 50),
                'w': _as_float(element.get('w', 20) or 20, 20),
                'h': _as_float(element.get('h', 8) or 8, 8),
                'zIndex': _as_int(element.get('zIndex', idx + 1) or (idx + 1), idx + 1),
                'locked': False if is_fixed_validation_element else bool(element.get('locked')),
                'visible': True if is_fixed_validation_element else element.get('visible', True) is not False,
            }

            if element_type == 'qr':
                normalized_elements.append({
                    **base,
                    'size': _as_int(element.get('size', 80) or 80, 80),
                })
                continue

            if element_type == 'image':
                src = str(element.get('src') or '').strip()
                if not src:
                    continue
                normalized_elements.append({
                    **base,
                    'src': src,
                })
                continue

            font_family = cls.normalize_font_family(element.get('font_family'))
            text = str(element.get('text') or '')
            if element_id == 'date_fixed' and '{{DATA}}' not in text:
                text = 'Data de Emissão: {{DATA}}'
            if element_id == 'name_fixed':
                text = '{{RECIPIENT_NAME}}' if designer_mode == 'institutional' else '{{NOME}}'
                font_family = 'Helvetica'
            if element_id == 'hash':
                font_family = 'Courier'
                text = '{{HASH}}'

            normalized_elements.append({
                **base,
                'type': 'text',
                'text': text,
                'font': max(8, _as_float(element.get('font', 20) or 20, 20)),
                'color': str(element.get('color') or '#000000'),
                'align': 'left' if element_id == 'hash' else str(element.get('align') or 'center'),
                'bold': bool(element.get('bold')),
                'italic': bool(element.get('italic')),
                'font_family': font_family,
                'text_styles': cls._normalize_text_styles(element.get('text_styles') or {}),
                'is_html': False if element_id in {'hash', 'name_fixed'} else bool(element.get('is_html')),
                'html_content': None if element_id in {'hash', 'name_fixed'} else element.get('html_content'),
                'auto_fit': False if element_id == 'hash' else element.get('auto_fit', True) is not False,
            })

        for required in fixed_elements:
            if any(element.get('id') == required['id'] for element in normalized_elements):
                continue
            normalized_elements.append(json.loads(json.dumps(fixed_elements_by_id[required['id']])))

        normalized_elements.sort(key=lambda item: item.get('zIndex', 0))
        for idx, element in enumerate(normalized_elements, start=1):
            element['zIndex'] = idx

        normalized['elements'] = normalized_elements
        return normalized

    def _parse_template_elements(self, event, template_override=None):
        """Loads and normalizes template elements with legacy compatibility."""
        designer_mode = self._designer_mode_for_entity(event)
        if template_override is not None:
            if isinstance(template_override, str):
                try:
                    template_override = json.loads(template_override)
                except Exception:
                    template_override = {}

            normalized_override = self.normalize_template_payload(template_override or {}, designer_mode=designer_mode)
            return normalized_override.get('elements', []), (normalized_override.get('bg') or getattr(event, 'cert_bg_path', None))

        default_template = self.build_default_template(designer_mode=designer_mode, bg=getattr(event, 'cert_bg_path', ''))

        if not event.cert_template_json:
            normalized = self.normalize_template_payload(default_template, designer_mode=designer_mode)
            return normalized.get('elements', []), (normalized.get('bg') or getattr(event, 'cert_bg_path', None))

        try:
            template = json.loads(event.cert_template_json)
        except Exception:
            normalized = self.normalize_template_payload(default_template, designer_mode=designer_mode)
            return normalized.get('elements', []), (normalized.get('bg') or getattr(event, 'cert_bg_path', None))

        if isinstance(template, dict) and isinstance(template.get('elements'), list):
            normalized = self.normalize_template_payload(template, designer_mode=designer_mode)
            return normalized.get('elements', []), (normalized.get('bg') or getattr(event, 'cert_bg_path', None))

        if isinstance(template, dict):
            normalized_legacy = {
                'version': 2,
                'document': {'gridSize': 2, 'snap': True, 'guides': True},
                'bg': getattr(event, 'cert_bg_path', ''),
                'elements': self._normalize_legacy_elements(template),
            }
            normalized = self.normalize_template_payload(normalized_legacy, designer_mode=designer_mode)
            return normalized.get('elements', []), (normalized.get('bg') or getattr(event, 'cert_bg_path', None))

        normalized = self.normalize_template_payload(default_template, designer_mode=designer_mode)
        return normalized.get('elements', []), (normalized.get('bg') or getattr(event, 'cert_bg_path', None))

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
        family = self.normalize_font_family(family)
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

        def _replace_span(match):
            attrs = match.group(1) or ''
            content = match.group(2) or ''
            style_match = re.search(r'style=(["\'])(.*?)\1', attrs, flags=re.IGNORECASE | re.DOTALL)
            style_attr = style_match.group(2) if style_match else ''

            font_attrs = []
            wrappers = []
            for rule in style_attr.split(';'):
                raw_key, _, raw_value = rule.partition(':')
                key = raw_key.strip().lower()
                value = raw_value.strip()
                if not key or not value:
                    continue

                if key == 'color':
                    font_attrs.append(f'color="{value}"')
                elif key == 'font-size':
                    match_size = re.search(r'(\d+(?:\.\d+)?)', value)
                    if match_size:
                        font_attrs.append(f'size="{match_size.group(1)}"')
                elif key == 'font-family':
                    family_name = CertificateService.normalize_font_family(value.split(',')[0])
                    font_attrs.append(f'name="{family_name}"')
                elif key == 'font-weight' and value.lower() not in {'normal', '400'}:
                    wrappers.append(('b', 'b'))
                elif key == 'font-style' and value.lower() == 'italic':
                    wrappers.append(('i', 'i'))
                elif key == 'text-decoration':
                    lower_value = value.lower()
                    if 'underline' in lower_value:
                        wrappers.append(('u', 'u'))
                    if 'line-through' in lower_value:
                        wrappers.append(('strike', 'strike'))

            result = content
            for open_tag, close_tag in wrappers:
                result = f'<{open_tag}>{result}</{close_tag}>'
            if font_attrs:
                result = f'<font {" ".join(font_attrs)}>{result}</font>'
            return result

        h = re.sub(r'<span([^>]*)>(.*?)</span>', _replace_span, h, flags=re.IGNORECASE | re.DOTALL)
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

    def _build_template_tags(self, event, user, activities, total_hours, enrollment=None, tag_overrides=None):
        activity = None
        if activities:
            activity = next((item for item in activities if item is not None), None)
        if activity is None and enrollment and getattr(enrollment, 'activity', None):
            activity = enrollment.activity

        activity_name = activity.nome if activity and getattr(activity, 'nome', None) else ''
        speaker_name = activity.palestrante if activity and getattr(activity, 'palestrante', None) else ''
        issue_date = current_certificate_issue_date_label()
        reference_date_obj = (
            getattr(activity, 'data_atv', None)
            if activity and getattr(activity, 'data_atv', None)
            else getattr(event, 'data_inicio', None)
        )
        reference_date = (
            reference_date_obj.strftime('%d/%m/%Y')
            if getattr(reference_date_obj, 'strftime', None)
            else str(reference_date_obj or '')
        )

        tags = {
            '{{NOME}}': str(getattr(user, 'nome', '') or '').upper(),
            '{{EVENTO}}': str(getattr(event, 'nome', '') or ''),
            '{{ATIVIDADE}}': activity_name,
            '{{PALESTRANTE}}': speaker_name,
            '{{HORAS}}': str(total_hours),
            '{{DATA}}': issue_date,
            '{{EMISSION_DATE}}': issue_date,
            '{{DATA_REALIZACAO}}': reference_date,
            '{{CPF}}': str(getattr(user, 'cpf', '') or ''),
        }

        normalized_overrides = {}
        for key, value in (tag_overrides or {}).items():
            if str(key) in {'{{DATA}}', '{{EMISSION_DATE}}'}:
                continue
            normalized_overrides[str(key)] = '' if value is None else str(value)

        tags.update(normalized_overrides)
        tags['{{DATA}}'] = issue_date
        tags['{{EMISSION_DATE}}'] = issue_date
        return tags

    def _draw_qr_element(self, pdf_canvas, config, page_width, page_height, validation_url):
        import qrcode
        from io import BytesIO

        qr = qrcode.QRCode(box_size=10, border=0)
        qr.add_data(validation_url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = BytesIO()
        img_qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        abs_w = (config.get('w', 12) / 100) * page_width
        abs_h = (config.get('h', 12) / 100) * page_height
        abs_x_center = (config.get('x', 50) / 100) * page_width
        abs_y_center = (1 - (config.get('y', 50) / 100)) * page_height
        frame_x = abs_x_center - (abs_w / 2)
        frame_y = abs_y_center - (abs_h / 2)
        pdf_canvas.drawInlineImage(img_qr, frame_x, frame_y, width=abs_w, height=abs_h)

    def _draw_image_element(self, pdf_canvas, config, page_width, page_height):
        src = config.get('src')
        if not src:
            return

        if src.startswith('/static/'):
            image_path = os.path.join(current_app.root_path, 'static', src.replace('/static/', '', 1))
        elif src.startswith('static/'):
            image_path = os.path.join(current_app.root_path, src)
        else:
            image_path = os.path.join(current_app.root_path, 'static', src)

        if not os.path.exists(image_path):
            return

        abs_w = (config.get('w', 15) / 100) * page_width
        abs_h = (config.get('h', 15) / 100) * page_height
        abs_x_center = (config.get('x', 50) / 100) * page_width
        abs_y_center = (1 - (config.get('y', 50) / 100)) * page_height
        frame_x = abs_x_center - (abs_w / 2)
        frame_y = abs_y_center - (abs_h / 2)
        pdf_canvas.drawImage(image_path, frame_x, frame_y, width=abs_w, height=abs_h, mask='auto')

    def _draw_text_element(self, pdf_canvas, config, page_width, page_height, tags):
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Frame, KeepInFrame
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

        raw_text = config.get('text', '')
        html_content = config.get('html_content') if config.get('is_html') else None
        if not raw_text and not html_content:
            return

        final_text = raw_text
        for tag, val in tags.items():
            final_text = final_text.replace(tag, val)

        family = config.get('font_family', 'Helvetica')
        is_bold = config.get('bold', False)
        is_italic = config.get('italic', False)
        font_name = self._resolve_font_name(family, is_bold, is_italic)

        abs_w = (config.get('w', 50) / 100) * page_width
        abs_h = (config.get('h', 10) / 100) * page_height
        abs_x_center = (config.get('x', 50) / 100) * page_width
        abs_y_center = (1 - (config.get('y', 50) / 100)) * page_height
        frame_x = abs_x_center - (abs_w / 2)
        frame_y = abs_y_center - (abs_h / 2)

        align_map = {'center': TA_CENTER, 'left': TA_LEFT, 'right': TA_RIGHT, 'justify': TA_JUSTIFY}
        font_size = (config.get('font', 20) / 1000) * page_width

        style = ParagraphStyle(
            name=f"Style_{config.get('id') or 'text'}",
            fontName=font_name,
            fontSize=font_size,
            textColor=config.get('color', '#000000'),
            alignment=align_map.get(config.get('align', 'center'), TA_CENTER),
            leading=font_size * 1.2
        )

        if html_content:
            substituted_html = html_content
            for tag_key, tag_value in tags.items():
                substituted_html = substituted_html.replace(tag_key, html.escape(str(tag_value)))
            paragraph_content = self._convert_jodit_html(substituted_html)
        else:
            text_styles = config.get('text_styles', {})
            if isinstance(text_styles, dict) and text_styles:
                paragraph_content = self._build_rich_text_markup(raw_text, text_styles, config, tags)
            else:
                paragraph_content = final_text

        paragraph = Paragraph(paragraph_content, style)
        story = [KeepInFrame(abs_w, abs_h, [paragraph], mode='shrink')]
        frame = Frame(frame_x, frame_y, abs_w, abs_h, showBoundary=0, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0)
        frame.addFromList(story, pdf_canvas)

    def generate_pdf(self, event, user, activities, total_hours, enrollment=None, template_override=None, tag_overrides=None):
        """Generates a single certificate PDF for a user using professional layout blocks."""
        import hashlib

        tags = self._build_template_tags(
            event,
            user,
            activities,
            total_hours,
            enrollment=enrollment,
            tag_overrides=tag_overrides,
        )
        override_hash = str(tags.get('{{HASH}}') or '').strip()
        
        # 0. Handle Validation Hash
        if enrollment and not override_hash and not enrollment.cert_hash:
            raw = f"{event.id}-{user.cpf}-{secrets.token_hex(8)}"
            enrollment.cert_hash = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
            from app.extensions import db
            db.session.commit()
        
        cert_hash = override_hash or (enrollment.cert_hash if enrollment else "VALID-SAMPLE-HASH")
        tags['{{HASH}}'] = cert_hash
        validation_url = build_absolute_app_url(f"/validar/{cert_hash}")

        output_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'generated')
        os.makedirs(output_dir, exist_ok=True)
        safe_identifier = str(getattr(user, 'cpf', '') or f"USER-{getattr(user, 'id', 'NA')}")
        filename = f"cert_{event.id}_{safe_identifier}.pdf"
        filepath = os.path.join(output_dir, filename)
        
        page_width, page_height = landscape(A4)

        c = canvas.Canvas(filepath, pagesize=(page_width, page_height))
        
        # 1. Draw Background
        elements, background_path = self._parse_template_elements(event, template_override=template_override)
        if background_path and os.path.exists(os.path.join(current_app.root_path, 'static', background_path)):
            c.drawImage(os.path.join(current_app.root_path, 'static', background_path), 0, 0, width=page_width, height=page_height)
        
        # 2. Draw Elements

        ordered_elements = sorted(
            [e for e in elements if e.get('visible', True)],
            key=lambda item: item.get('zIndex', 0)
        )

        for config in ordered_elements:
            element_type = config.get('type', 'text')
            element_id = config.get('id', '')

            if element_type == 'qr' or element_id == 'qrcode':
                self._draw_qr_element(c, config, page_width, page_height, validation_url)
                continue

            if element_type == 'image' and config.get('src'):
                self._draw_image_element(c, config, page_width, page_height)
                continue

            self._draw_text_element(c, config, page_width, page_height, tags)
        
        c.showPage()
        try:
            c.save()
        except FileNotFoundError:
            # Defensive retry for environments where generated folder may be missing at runtime.
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            c.save()
        return filepath

    def queue_event_certificates(self, event_id):
        """Queues certificate delivery for all present participants of an event."""
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return False, "Evento não encontrado", {
                'total_enviado': 0,
                'sem_email': 0,
                'falha_fila': 0,
            }
        count = 0
        skipped_without_email = 0
        failed_queue = 0
        for atv in event.activities:
            for enroll in atv.enrollments:
                if not enroll.presente:
                    continue

                user = self.user_repo.get_by_cpf(enroll.user_cpf)
                if not user or not user.email:
                    skipped_without_email += 1
                    continue

                # Standard events issue one certificate per activity/enrollment.
                # Fast events still have a single default activity and behave naturally.
                cert_hours = atv.carga_horaria or 0
                pdf_path = self.generate_pdf(event, user, [atv], cert_hours, enrollment=enroll)
                cert_hash = enroll.cert_hash
                validation_url = build_absolute_app_url(f"/validar/{cert_hash}") if cert_hash else ''
                download_url = build_absolute_app_url(f"/api/certificates/download_public/{cert_hash}") if cert_hash else ''
                event_date = event.data_inicio.strftime('%d/%m/%Y') if event and event.data_inicio else ''
                activity_suffix = f" - {atv.nome}" if getattr(event, 'tipo', None) == 'PADRAO' else ''

                if not self.notifier.send_email_task(
                    to_email=user.email,
                    subject=f"Seu Certificado: {event.nome}{activity_suffix}",
                    template_name='certificate_ready.html',
                    template_data={
                        'user_name': user.nome,
                        'event_name': event.nome,
                        'event_date': event_date,
                        'course_hours': cert_hours,
                        'certificate_number': cert_hash,
                        'certificate_download_url': download_url,
                        'view_certificate_url': build_absolute_app_url(f"/api/certificates/preview_public/{cert_hash}") if cert_hash else '',
                        'my_certificates_url': validation_url,
                    },
                    attachment_path=pdf_path
                ):
                    failed_queue += 1
                    continue

                enroll.cert_data_envio = datetime.now()
                enroll.cert_entregue = True
                db.session.commit()
                count += 1

        if count == 0 and failed_queue > 0:
            return False, "Problema no envio: falha ao enfileirar e-mails.", {
                'total_enviado': count,
                'sem_email': skipped_without_email,
                'falha_fila': failed_queue,
            }

        if count == 0:
            return False, "Problema no envio: nenhum participante com e-mail válido.", {
                'total_enviado': count,
                'sem_email': skipped_without_email,
                'falha_fila': failed_queue,
            }

        message = f"{count} certificados colocados na fila de envio."
        if failed_queue > 0:
            message = f"Envio parcialmente concluído. {count} certificados enfileirados."

        return True, message, {
            'total_enviado': count,
            'sem_email': skipped_without_email,
            'falha_fila': failed_queue,
        }

    def update_config(self, event_id, bg_path=None, template_json=None):
        """Updates certificate configuration for an event."""
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return False
            
        if bg_path is not None:
            event.cert_bg_path = bg_path if bg_path != "" else None
        if template_json is not None:
            event.cert_template_json = template_json
            
        self.event_repo.save(event)
        return True
