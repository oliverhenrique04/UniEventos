import pika
import json
import time
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

"""
RabbitMQ Worker for UniEventos.
Processes asynchronous email tasks from the 'email_queue'.
Includes Dead Letter Queue (DLQ) support for failure handling.
"""

RABBITMQ_URL = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')

def send_email(to, subject, body, attachment_path=None):
    """
    Simulates sending an email via an external SMTP or API.
    Handles optional file attachments.
    """
    print(f" [x] Preparing email to {to}")
    
    # Simulation of attachment processing
    if attachment_path:
        if os.path.exists(attachment_path):
            print(f"     [OK] Attachment found: {os.path.basename(attachment_path)}")
        else:
            print(f"     [!] Warning: Attachment not found at {attachment_path}")
    
    print(f"     Subject: {subject}")
    # print(f"     Body: {body[:50]}...")
    
    time.sleep(1) # Simulate network delay
    print(" [x] Email successfully sent")

def callback(ch, method, properties, body):
    """
    Callback function executed when a message is received from the queue.
    Decodes the JSON payload and attempts to send the email.
    """
    print(" [x] Received notification task")
    try:
        data = json.loads(body)
        send_email(
            data['to'], 
            data['subject'], 
            data['body'], 
            data.get('attachment')
        )
        # Acknowledge successful processing
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f" [!] Error processing message: {e}")
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
    
    # 2. Declare Main Queue with DLQ arguments
    args = {
        'x-dead-letter-exchange': 'dlx_exchange',
        'x-dead-letter-routing-key': 'dlq_key'
    }
    channel.queue_declare(queue='email_queue', durable=True, arguments=args)
    
    # Ensure fair dispatch (one message at a time per worker)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='email_queue', on_message_callback=callback)
    
    print(' [*] UniEventos Worker active. Waiting for messages. Press CTRL+C to stop.')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
