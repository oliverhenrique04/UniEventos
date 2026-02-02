from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.admin_service import AdminService
from app.serializers import serialize_user

bp = Blueprint('admin', __name__, url_prefix='/api')
admin_service = AdminService()

@bp.route('/listar_usuarios', methods=['GET'])
@login_required
def listar_usuarios():
    if current_user.role not in ['admin', 'coordenador']:
        return jsonify([]), 403
    
    page = request.args.get('page', 1, type=int)
    filters = {
        'ra': request.args.get('ra'),
        'curso': request.args.get('curso'),
        'cpf': request.args.get('cpf'),
        'email': request.args.get('email'),
        'nome': request.args.get('nome'),
        'event_id': request.args.get('event_id', type=int),
        'activity_id': request.args.get('activity_id', type=int)
    }
    
    pagination = admin_service.list_users_paginated(page=page, filters=filters)
    
    return jsonify({
        "items": [serialize_user(u) for u in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/buscar_participante', methods=['GET'])
@login_required
def buscar_participante():
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify([]), 403
    
    termo = request.args.get('q', '')
    if len(termo) < 2: return jsonify([])
    
    users = admin_service.buscar_usuarios_inscricao(termo)
    return jsonify([serialize_user(u) for u in users])

@bp.route('/criar_usuario', methods=['POST'])
@login_required
def criar_usuario():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
    user, msg = admin_service.create_user(request.json)
    if user: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/deletar_usuario/<username>', methods=['DELETE'])
@login_required
def deletar_usuario(username):
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
    if admin_service.delete_user(username):
        return jsonify({"mensagem": "Removido!"})
    return jsonify({"erro": "Falha ao remover"}), 404

@bp.route('/inscricao_manual', methods=['POST'])
@login_required
def inscricao_manual():
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    success, msg = admin_service.manual_enroll(data.get('cpf'), data.get('activity_id'))
    
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/editar_usuario', methods=['POST'])
@login_required
def editar_usuario():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    target_username = data.get('username_alvo')
    
    updated = admin_service.update_user_details(target_username, data)
    
    if updated:
        return jsonify({"mensagem": "Atualizado!"})
        
    return jsonify({"erro": "Usuário não encontrado"}), 404
