from flask import Blueprint, request, jsonify, redirect
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService

bp = Blueprint('auth', __name__, url_prefix='/api')
auth_service = AuthService()

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    login_value = data.get('cpf') or data.get('login') or data.get('username')
    password = data.get('password')
    
    user = auth_service.authenticate_user(login_value, password)
    
    if user:
        login_user(user)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Dados inválidos"}), 401

@bp.route('/registrar', methods=['POST'])
def registrar():
    data = request.json
    try:
        auth_service.register_user(data)
        return jsonify({"mensagem": "Cadastrado!"})
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": "Erro interno"}), 500

@bp.route('/logout')
def logout():
    logout_user()
    return redirect('/')


@bp.route('/password/forgot', methods=['POST'])
def password_forgot():
    data = request.json or {}
    email = data.get('email')

    # Prevent account enumeration by always returning success response.
    auth_service.request_password_reset(email)
    return jsonify({
        'mensagem': 'Se o e-mail estiver cadastrado, enviaremos as instruções de recuperação.'
    })


@bp.route('/password/reset', methods=['POST'])
def password_reset():
    data = request.json or {}
    token = data.get('token')
    new_password = data.get('password')

    success, msg = auth_service.reset_password_with_token(token, new_password)
    if success:
        return jsonify({'mensagem': msg})
    return jsonify({'erro': msg}), 400


@bp.route('/me/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.json or {}
    success, msg = auth_service.update_profile(
        current_user,
        data.get('nome'),
        data.get('email'),
    )
    if success:
        return jsonify({'mensagem': msg, 'nome': current_user.nome, 'email': current_user.email})
    return jsonify({'erro': msg}), 400


@bp.route('/me/password', methods=['PUT'])
@login_required
def change_password():
    data = request.json or {}
    success, msg = auth_service.change_password(
        current_user,
        data.get('current_password'),
        data.get('new_password'),
    )
    if success:
        return jsonify({'mensagem': msg})
    return jsonify({'erro': msg}), 400
