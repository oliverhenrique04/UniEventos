from flask import Blueprint, request, jsonify, session
from app.db import get_db

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/listar_usuarios', methods=['GET'])
def listar_usuarios():
    if session.get('user', {}).get('role') not in ['admin', 'coordenador']:
        return jsonify([]), 403
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@admin_bp.route('/api/editar_usuario', methods=['POST'])
def editar_usuario():
    if session.get('user', {}).get('role') != 'admin':
        return jsonify({"erro": "Negado"}), 403
    d = request.json
    conn = get_db()
    conn.execute("UPDATE users SET nome=?, cpf=?, role=? WHERE username=?",
                (d.get('nome'), d.get('cpf'), d.get('role'), d.get('username_alvo')))
    conn.commit()
    conn.close()
    return jsonify({"mensagem": "Atualizado!"})