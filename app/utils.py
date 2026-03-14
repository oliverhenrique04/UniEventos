import time
import hashlib
import hmac
from math import radians, cos, sin, asin, sqrt
from flask import current_app
from urllib.parse import urlparse, urlunparse

import unicodedata
import re


def _join_url_paths(*parts):
    """Joins URL path chunks preserving a single leading slash."""
    chunks = [str(p or '').strip('/') for p in parts if str(p or '').strip('/')]
    return f"/{'/'.join(chunks)}" if chunks else '/'


def build_absolute_app_url(path):
    """Builds an absolute URL using BASE_URL + optional BASE_PATH for subpath deploys."""
    raw_path = str(path or '').strip()
    normalized_path = raw_path if raw_path.startswith('/') else f"/{raw_path}"

    base_url = (current_app.config.get('BASE_URL') or '').strip()
    if not base_url:
        return normalized_path

    parsed = urlparse(base_url)
    base_path = parsed.path or ''
    configured_base_path = (current_app.config.get('BASE_PATH') or '').strip()
    configured_base_path = configured_base_path if configured_base_path.startswith('/') else f"/{configured_base_path}" if configured_base_path else ''
    configured_base_path = configured_base_path.rstrip('/')

    merged_base_path = base_path.rstrip('/')
    if configured_base_path and not merged_base_path.endswith(configured_base_path):
        merged_base_path = _join_url_paths(merged_base_path, configured_base_path)

    final_path = _join_url_paths(merged_base_path, normalized_path)
    return urlunparse((parsed.scheme, parsed.netloc, final_path, '', '', ''))


def normalize_cpf(value):
    """Returns CPF as digits only (11 chars expected by domain rules)."""
    if value is None:
        return None
    digits = re.sub(r'\D', '', str(value))
    return digits

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the great-circle distance between two points in meters."""
    if None in [lat1, lon1, lat2, lon2]: return 0
    R = 6371000 # Earth radius in meters
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)

    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2*asin(sqrt(a))
    return R * c

def gerar_hash_dinamico(activity_id):
    """Generates a secure time-based HMAC for activity validation."""
    window = int(time.time() / 30) # 30-second rotation
    key = current_app.config['SECRET_KEY'].encode()
    msg = f"{activity_id}:{window}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def validar_hash_dinamico(activity_id, token_recebido):
    """Validates if the provided token matches the current or previous 30s window."""
    window_atual = int(time.time() / 30)
    key = current_app.config['SECRET_KEY'].encode()
    
    # Allow current and immediate previous window (grace period for network/scan lag)
    for w in [window_atual, window_atual - 1]:
        msg = f"{activity_id}:{w}".encode()
        expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
        if hmac.compare_digest(token_recebido, expected):
            return True
    return False

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
