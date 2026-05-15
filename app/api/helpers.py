from functools import wraps

from flask import jsonify, request
from flask_login import current_user


def json_error(message, status=400):
    return jsonify({'erro': message}), status


def json_success(message=None, status=200, **payload):
    body = dict(payload)
    if message is not None:
        body.setdefault('mensagem', message)
    return jsonify(body), status


def parse_json_body(required=False):
    raw_body = request.get_data(cache=True)
    if not raw_body or not raw_body.strip():
        if required:
            return None, json_error('Payload JSON obrigatório.', 400)
        return {}, None

    data = request.get_json(silent=True)
    if data is None:
        return None, json_error('Payload JSON inválido.', 400)
    if not isinstance(data, dict):
        return None, json_error('Payload JSON inválido.', 400)
    return data, None


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if current_user.role != 'admin':
            return json_error('Negado', 403)
        return view_func(*args, **kwargs)

    return wrapped
