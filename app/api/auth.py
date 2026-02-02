from flask import Blueprint, request, jsonify, redirect
from flask_login import login_user, logout_user
from app.services.auth_service import AuthService

bp = Blueprint('auth', __name__, url_prefix='/api')
auth_service = AuthService()

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = auth_service.authenticate_user(username, password)
    
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
