from flask import Blueprint, request, jsonify, session, redirect
from app.db import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    d = request.json
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (d.get('username'),)).fetchone()
    conn.close()
    if user and user['password'] == d.get('password'):
        session['user'] = dict(user)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Dados inválidos"}), 401

@auth_bp.route('/api/registrar', methods=['POST'])
def registrar():
    d = request.json
    try:
        conn = get_db()
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                    (d.get('username'), d.get('password'), 'participante', d.get('nome'), d.get('cpf')))
        conn.commit()
        conn.close()
        return jsonify({"mensagem": "Cadastrado!"})
    except: return jsonify({"erro": "Usuário já existe"}), 400

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/')