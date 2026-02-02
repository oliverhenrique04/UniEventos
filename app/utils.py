import time
import hashlib
from flask import current_app

def gerar_hash_dinamico(activity_id):
    timestamp = int(time.time() / 30)
    raw = f"{activity_id}:{timestamp}:{current_app.config['SECRET_KEY']}"
    return hashlib.sha256(raw.encode()).hexdigest()

def validar_hash_dinamico(activity_id, token_recebido):
    timestamp_atual = int(time.time() / 30)
    for t in [timestamp_atual, timestamp_atual - 1]:
        raw = f"{activity_id}:{t}:{current_app.config['SECRET_KEY']}"
        if token_recebido == hashlib.sha256(raw.encode()).hexdigest():
            return True
    return False
