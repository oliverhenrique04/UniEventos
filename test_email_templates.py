"""
Test script to send a notification via RabbitMQ.
Use this to verify the email system is working.
"""
import json
import pika

def test_send_welcome_email():
    """Test sending a welcome email."""
    print("🧪 Testing Welcome Email Template...")
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.URLParameters(
        'amqp://guest:guest@nuted-ia.dev:7770/'
    ))
    channel = connection.channel()
    
    # Don't declare queue - worker already handles it with DLQ support
    
    # Prepare message
    message = {
        'to': 'joao.teste@unieuro.edu.br',
        'subject': 'Bem-vindo ao UniEventos!',
        'template_name': 'welcome.html',
        'template_data': {
            'user_name': 'João Teste',
            'email': 'joao.teste@unieuro.edu.br',
            'app_url': 'https://unieventos.local',
            'year': 2026,
            'unsubscribe_url': 'https://unieventos.local/unsubscribe/',
        },
        'attachment': None
    }
    
    # Send message
    channel.basic_publish(
        exchange='',
        routing_key='email_queue',
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Make message persistent
            content_type='application/json'
        )
    )
    
    print("✅ Welcome email sent to queue!")
    connection.close()

def test_send_institutional_certificate():
    """Test sending an institutional certificate email."""
    print("\n🧪 Testing Institutional Certificate Email Template...")
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.URLParameters(
        'amqp://guest:guest@nuted-ia.dev:7770/'
    ))
    channel = connection.channel()
    
    # Don't declare queue - worker already handles it with DLQ support
    
    # Prepare message
    message = {
        'to': 'maria.silva@unieuro.edu.br',
        'subject': '🎓 Certificado Institucional Disponível - Reconhecimento Profissional',
        'template_name': 'institutional_certificate_ready.html',
        'template_data': {
            'recipient_name': 'Maria Silva',
            'certificate_title': 'Certificado de Reconhecimento Profissional',
            'category_name': 'Reconhecimento',
            'issue_date': '13/03/2026',
            'certificate_number': 'INST-2026-005678',
            'signer_name': 'Prof. Dr. João Santos - Diretor do NUTED',
            'recipient_cpf': '123.456.789-00',
            'additional_info': 'Este certificado atesta a participação especial na comissão organizacional.',
            'download_url': 'https://unieventos.local/institutional-certificates/download/123',
            'preview_url': 'https://unieventos.local/institutional-certificates/preview/123',
            'validation_url': 'https://unieventos.local/validate/INST-2026-005678',
        },
        'attachment': None
    }
    
    # Send message
    channel.basic_publish(
        exchange='',
        routing_key='email_queue',
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type='application/json'
        )
    )
    
    print("✅ Institutional certificate email sent to queue!")
    connection.close()

if __name__ == '__main__':
    print("=" * 60)
    print("UniEventos - Email Template Test")
    print("=" * 60)
    
    try:
        test_send_welcome_email()
        test_send_institutional_certificate()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed! Check your worker.py logs.")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
