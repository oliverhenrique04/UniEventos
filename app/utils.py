import time
import hashlib
from flask import current_app

import unicodedata
import re

def remover_acentos(texto):
    """Removes accents and diacritics from a string."""
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

def normalizar_texto(texto):
    """Normalizes text for comparison: lowercase, no accents, only alphanumeric."""
    if not texto: return ""
    texto = texto.lower()
    texto = remover_acentos(texto)
    # Keep only letters and numbers
    return re.sub(r'[^a-z0-9]', '', texto)

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
