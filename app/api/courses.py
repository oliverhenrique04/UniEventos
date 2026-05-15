from flask import Blueprint, jsonify
from flask_login import login_required
from app.api.helpers import admin_required, json_error, parse_json_body, json_success
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
@admin_required
def create_course():
    data, error = parse_json_body(required=True)
    if error:
        return error

    course, msg = course_service.create_course(data)
    if course:
        return json_success(msg, id=course.id, nome=course.nome)
    return json_error(msg, 400)

@bp.route('/<int:course_id>', methods=['PUT'])
@login_required
@admin_required
def update_course(course_id):
    data, error = parse_json_body(required=True)
    if error:
        return error

    course, msg = course_service.update_course(course_id, data)
    if course:
        return json_success(msg, id=course.id, nome=course.nome)
    return json_error(msg, 400)

@bp.route('/<int:course_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_course(course_id):
    success, msg = course_service.delete_course(course_id)
    if success:
        return json_success(msg)
    return json_error(msg, 400)
