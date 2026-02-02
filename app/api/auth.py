from flask import Blueprint, request, jsonify, session, redirect
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db

bp = Blueprint('auth', __name__, url_prefix='/api')

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        login_user(user)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Dados inválidos"}), 401

@bp.route('/registrar', methods=['POST'])
def registrar():
    data = request.json
    username = data.get('username')
    
    if User.query.filter_by(username=username).first():
        return jsonify({"erro": "Usuário já existe"}), 400
        
    try:
        user = User(
            username=username,
            role='participante',
            nome=data.get('nome'),
            cpf=data.get('cpf')
        )
        user.set_password(data.get('password'))
        db.session.add(user)
        db.session.commit()
        return jsonify({"mensagem": "Cadastrado!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

@bp.route('/logout') # Legacy app had /logout as a view, not api. But I can keep it here or in main.
def logout():
    logout_user()
    return redirect('/')
