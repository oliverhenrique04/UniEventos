from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.course_service import CourseService

bp = Blueprint('courses_api', __name__, url_prefix='/api/courses')
course_service = CourseService()

@bp.route('/', methods=['GET'])
@login_required
def list_courses():
    courses = course_service.list_all()
    return jsonify([{"id": c.id, "nome": c.nome} for c in courses])

@bp.route('/', methods=['POST'])
@login_required
def create_course():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
    
    course, msg = course_service.create_course(request.json)
    if course:
        return jsonify({"id": course.id, "nome": course.nome, "mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/<int:course_id>', methods=['PUT'])
@login_required
def update_course(course_id):
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
        
    course, msg = course_service.update_course(course_id, request.json)
    if course:
        return jsonify({"id": course.id, "nome": course.nome, "mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/<int:course_id>', methods=['DELETE'])
@login_required
def delete_course(course_id):
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
        
    success, msg = course_service.delete_course(course_id)
    if success:
        return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400
