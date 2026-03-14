"""
Email Template Service for EuroEventos.
Renders HTML email templates with Jinja2.
"""
import os
from jinja2 import Environment, FileSystemLoader


class EmailTemplateService:
    """Service for rendering email templates."""
    
    def __init__(self):
        """Initialize the template environment."""
        # Support both template references styles:
        # - direct file names (e.g. welcome.html) from templates/emails
        # - prefixed inheritance paths (e.g. emails/base.html) from templates
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_root_dir = os.path.join(base_dir, 'templates')
        templates_dir = os.path.join(base_dir, 'templates', 'emails')
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader([templates_root_dir, templates_dir]),
            autoescape=True
        )
    
    def render_template(self, template_name: str, context: dict = None) -> str:
        """
        Render an email template with the provided context.
        
        Args:
            template_name (str): Name of the template file (e.g., 'welcome.html')
            context (dict, optional): Template variables
            
        Returns:
            str: Rendered HTML content
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**(context or {}))
        except Exception as e:
            # Log error and return a simple fallback
            print(f"Error rendering template {template_name}: {e}")
            return self._render_fallback(template_name, context or {})
    
    def render_welcome_email(self, user_name: str, email: str, app_url: str) -> str:
        """Render welcome email template."""
        return self.render_template('welcome.html', {
            'user_name': user_name,
            'email': email,
            'app_url': app_url,
            'year': 2026,
            'unsubscribe_url': f"{app_url}/unsubscribe/"
        })
    
    def render_enrollment_confirmation(
        self, 
        user_name: str,
        event_name: str,
        event_date: str,
        event_time: str,
        event_location: str,
        event_type: str = None,
        event_description: str = None,
        event_details_url: str = None,
        my_events_url: str = None,
        cancel_url: str = None
    ) -> str:
        """Render enrollment confirmation email template."""
        return self.render_template('enrollment_confirmation.html', {
            'user_name': user_name,
            'event_name': event_name,
            'event_date': event_date,
            'event_time': event_time,
            'event_location': event_location,
            'event_type': event_type,
            'event_description': event_description,
            'event_details_url': event_details_url or '',
            'my_events_url': my_events_url or '',
            'cancel_url': cancel_url or ''
        })
    
    def render_certificate_ready(
        self,
        user_name: str,
        event_name: str,
        event_date: str,
        course_hours: str = None,
        certificate_number: str = None,
        certificate_download_url: str = None,
        view_certificate_url: str = None,
        my_certificates_url: str = None
    ) -> str:
        """Render certificate ready email template (for event certificates)."""
        return self.render_template('certificate_ready.html', {
            'user_name': user_name,
            'event_name': event_name,
            'event_date': event_date,
            'course_hours': course_hours,
            'certificate_number': certificate_number,
            'certificate_download_url': certificate_download_url or '',
            'view_certificate_url': view_certificate_url or '',
            'my_certificates_url': my_certificates_url or ''
        })
    
    def render_institutional_certificate_ready(
        self,
        recipient_name: str,
        certificate_title: str,
        category_name: str = None,
        issue_date: str = None,
        certificate_number: str = None,
        signer_name: str = None,
        recipient_cpf: str = None,
        additional_info: str = None,
        download_url: str = None,
        preview_url: str = None,
        validation_url: str = None
    ) -> str:
        """
        Render institutional certificate ready email template.
        
        This template is specifically for institutional certificates that are NOT
        tied to events (e.g., recognition certificates, special awards, etc.).
        
        Args:
            recipient_name (str): Name of the certificate recipient
            certificate_title (str): Title/name of the certificate
            category_name (str, optional): Category of the certificate
            issue_date (str, optional): Issue date
            certificate_number (str, optional): Certificate number for validation
            signer_name (str, optional): Name of the signatory authority
            recipient_cpf (str, optional): CPF of the recipient
            additional_info (str, optional): Additional information about the certificate
            download_url (str, optional): URL to download the PDF
            preview_url (str, optional): URL to preview online
            validation_url (str, optional): URL to validate the certificate
            
        Returns:
            str: Rendered HTML email
        """
        return self.render_template('institutional_certificate_ready.html', {
            'recipient_name': recipient_name,
            'certificate_title': certificate_title,
            'category_name': category_name,
            'issue_date': issue_date,
            'certificate_number': certificate_number,
            'signer_name': signer_name,
            'recipient_cpf': recipient_cpf,
            'additional_info': additional_info,
            'download_url': download_url or '',
            'preview_url': preview_url or '',
            'validation_url': validation_url or ''
        })
    
    def _render_fallback(self, template_name: str, context: dict) -> str:
        """Render a simple fallback email if template fails."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Email</title>
        </head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1>EuroEventos</h1>
            <p>Este é um e-mail do sistema EuroEventos.</p>
            <p>Template: {template_name}</p>
        </body>
        </html>
        """
