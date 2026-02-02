from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import User, db

bp = Blueprint('admin', __name__, url_prefix='/api')

@bp.route('/listar_usuarios', methods=['GET'])
@login_required
def listar_usuarios():
    if current_user.role not in ['admin', 'coordenador']:
        return jsonify([]), 403
    
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])

@bp.route('/editar_usuario', methods=['POST'])
@login_required
def editar_usuario():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    target_username = data.get('username_alvo')
    
    user = User.query.get(target_username)
    if user:
        user.nome = data.get('nome')
        user.cpf = data.get('cpf')
        user.role = data.get('role')
        db.session.commit()
        return jsonify({"mensagem": "Atualizado!"})
        
    return jsonify({"erro": "Usuário não encontrado"}), 404
