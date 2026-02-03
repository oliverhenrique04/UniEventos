import pika
import json
from flask import current_app

class NotificationService:
    """Service layer for publishing notification events to RabbitMQ.
    
    This service acts as a producer, sending structured messages to the
    'email_queue' for asynchronous processing by background workers.
    """
    def _get_channel(self):
        """Internal helper to establish a RabbitMQ connection and channel."""
        url = current_app.config.get('RABBITMQ_URL')
        params = pika.URLParameters(url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='email_queue', durable=True)
        return connection, channel

    def send_email_task(self, to_email: str, subject: str, body: str, attachment_path: str = None):
        """Publishes an email notification task to the RabbitMQ 'email_queue'.
        
        This method handles connection setup, message structure, and persistence.
        It uses the delivery_mode=2 to ensure messages survive a RabbitMQ restart.
        
        Args:
            to_email (str): Recipient email address.
            subject (str): Email subject line.
            body (str): Email content (plain text or HTML).
            attachment_path (str, optional): Absolute path to a file to be attached.
            
        Returns:
            bool: True if the task was published successfully, False otherwise.
        """
        connection = None
        try:
            connection, channel = self._get_channel()
            
            payload = {
                'to': to_email,
                'subject': subject,
                'body': body,
                'attachment': attachment_path
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='email_queue',
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            return True
        except Exception as e:
            # In a production app, we would use a logger (e.g., app.logger.error)
            print(f"CRITICAL: Failed to publish to RabbitMQ: {e}")
            return False
        finally:
            if connection and not connection.is_closed:
                connection.close()
