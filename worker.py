import pika
import json
import time
import os
import sys
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.email_template_service import EmailTemplateService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

"""
RabbitMQ Worker for EuroEventos.
Processes asynchronous email tasks from the 'email_queue'.
Includes Dead Letter Queue (DLQ) support for failure handling.
"""

# Load RabbitMQ URL from environment with proper fallback
RABBITMQ_URL = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')

# Email configuration (loaded from environment variables)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.office365.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
DEFAULT_SENDER = os.environ.get('DEFAULT_SENDER', '')
template_service = EmailTemplateService()


def build_email_body(payload):
    """Build email body from template data or fallback to raw body."""
    template_name = payload.get('template_name')
    template_data = payload.get('template_data') or {}
    raw_body = payload.get('body')

    if template_name:
        try:
            logger.info(f"Rendering email template: {template_name}")
            return template_service.render_template(template_name, template_data)
        except Exception as e:
            logger.error(f"Template rendering failed ({template_name}): {e}")

    if raw_body:
        return raw_body

    return "<p>Mensagem automática do sistema EuroEventos.</p>"

def send_email(to, subject, body, attachment_path=None):
    """
    Sends an email via SMTP with optional file attachments.
    
    Args:
        to (str): Recipient email address
        subject (str): Email subject line
        body (str): Email content (HTML or plain text)
        attachment_path (str, optional): Path to file to attach
        
    Raises:
        Exception: If email sending fails
    """
    logger.info(f"Preparing email to {to}")
    logger.debug(f"Subject: {subject}")
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = DEFAULT_SENDER
    msg['To'] = to
    
    # Attach body (auto-detect basic html/plain)
    subtype = 'html' if '<' in body and '>' in body else 'plain'
    msg.attach(MIMEText(body, subtype))
    
    # Handle attachment
    if attachment_path:
        if os.path.exists(attachment_path):
            logger.info(f"Attachment found: {os.path.basename(attachment_path)}")
            
            try:
                with open(attachment_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(attachment_path)}'
                    )
                    msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to attach file: {e}")
                raise
        else:
            logger.warning(f"Attachment not found at {attachment_path}")
    
    # Send email via SMTP (only if credentials are configured)
    if SMTP_USERNAME and SMTP_PASSWORD:
        try:
            import smtplib
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(DEFAULT_SENDER, [to], msg.as_string())
            server.quit()
            logger.info(f"Email successfully sent to {to}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise
    else:
        # Simulation mode for development
        logger.info("Simulation mode: Email would be sent (no SMTP credentials configured)")
        time.sleep(1)  # Simulate network delay
        logger.info(f"[SIMULATION] Email successfully prepared for {to}")

def callback(ch, method, properties, body):
    """
    Callback function executed when a message is received from the queue.
    Decodes the JSON payload and attempts to send the email.
    """
    logger.info("Received notification task")
    try:
        data = json.loads(body)
        body_content = build_email_body(data)
        send_email(
            data['to'], 
            data['subject'], 
            body_content,
            data.get('attachment')
        )
        # Acknowledge successful processing
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # Reject message and send to DLQ (requeue=False)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) 

def main():
    """
    Main entry point for the worker process.
    Configures exchanges, queues, and starts consuming messages.
    """
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    
    # 1. Declare Dead Letter Exchange (DLX) and Queue (DLQ)
    # Failed messages will be automatically routed here.
    channel.exchange_declare(exchange='dlx_exchange', exchange_type='direct')
    channel.queue_declare(queue='email_dlq', durable=True)
    channel.queue_bind(exchange='dlx_exchange', queue='email_dlq', routing_key='dlq_key')
    
    # 2. Declare Main Queue with DLQ arguments.
    # If queue already exists with a different schema, fallback without crashing.
    args = {
        'x-dead-letter-exchange': 'dlx_exchange',
        'x-dead-letter-routing-key': 'dlq_key'
    }
    try:
        channel.queue_declare(queue='email_queue', durable=True, arguments=args)
    except pika.exceptions.ChannelClosedByBroker as e:
        logger.warning(
            "email_queue exists with different arguments; using existing queue config. "
            f"Broker error: {e}"
        )
        # Re-open channel after broker closes it on precondition failure.
        channel = connection.channel()
        channel.queue_declare(queue='email_queue', durable=True)
    
    # Ensure fair dispatch (one message at a time per worker)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='email_queue', on_message_callback=callback)
    
    logger.info('EuroEventos Worker active. Waiting for messages. Press CTRL+C to stop.')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
