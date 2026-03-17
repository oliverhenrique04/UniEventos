from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services.admin_service import AdminService
from app.services.event_service import EventService
from app.serializers import serialize_user
from app.models import Activity, Event
from app.extensions import db
from threading import Thread, Lock
from math import ceil
from uuid import uuid4
from io import BytesIO
from pathlib import Path
import json
import tempfile
import time
from datetime import datetime

bp = Blueprint('admin', __name__, url_prefix='/api')
admin_service = AdminService()
_IMPORT_JOBS = {}
_IMPORT_JOBS_LOCK = Lock()


def _jobs_store_dir() -> Path:
    path = Path(tempfile.gettempdir()) / 'unieventos_import_jobs'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_file_path(job_id: str) -> Path:
    return _jobs_store_dir() / f'{job_id}.json'


def _persist_job(job: dict):
    job_id = job.get('job_id')
    if not job_id:
        return
    file_path = _job_file_path(job_id)
    temp_path = file_path.with_suffix('.json.tmp')
    temp_path.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
    temp_path.replace(file_path)


def _load_job(job_id: str):
    file_path = _job_file_path(job_id)
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _job_rank(job: dict):
    if not isinstance(job, dict):
        return (-1, -1, -1)
    return (
        1 if job.get('completed') else 0,
        int(job.get('processed_rows') or 0),
        float(job.get('updated_at') or 0),
    )


def _best_job_state(*jobs):
    valid_jobs = [j for j in jobs if isinstance(j, dict)]
    if not valid_jobs:
        return None
    return max(valid_jobs, key=_job_rank)


def _get_active_job_for_user(username: str):
    if not username:
        return None
    for job in _IMPORT_JOBS.values():
        if job.get('created_by') != username:
            continue
        if job.get('completed'):
            continue
        if job.get('status') in {'queued', 'running'}:
            return job
    return None


def _update_job(job_id, **kwargs):
    with _IMPORT_JOBS_LOCK:
        job = _IMPORT_JOBS.get(job_id)
        if not job:
            return
        kwargs['updated_at'] = time.time()
        job.update(kwargs)
        _persist_job(job)


def _append_job_row(job_id, row_result):
    with _IMPORT_JOBS_LOCK:
        job = _IMPORT_JOBS.get(job_id)
        if not job:
            return

        job['processed_rows'] += 1
        status = row_result.get('status')
        if status == 'created':
            job['created'] += 1
        elif status == 'updated':
            job['updated'] += 1
        elif status == 'unchanged':
            job['unchanged'] += 1
        else:
            job['errors_count'] += 1

        job['rows'].append(row_result)
        job['updated_at'] = time.time()
        _persist_job(job)


def _run_tabular_import_job(job_id, file_content, app_obj, parse_method_name, process_method_name):
    with app_obj.app_context():
        try:
            parse_method = getattr(admin_service, parse_method_name)
            process_method = getattr(admin_service, process_method_name)

            parsed = parse_method(BytesIO(file_content))
            if not parsed.get('ok'):
                _update_job(
                    job_id,
                    status='failed',
                    completed=True,
                    message=parsed.get('message', 'Falha ao ler arquivo.'),
                    ignored_columns=parsed.get('ignored_columns', []),
                    rows=[
                        {
                            'row_number': 0,
                            'status': 'error',
                            'message': err,
                            'nome': '',
                            'cpf': '',
                            'curso': '',
                            'ra': '',
                        }
                        for err in parsed.get('errors', [])
                    ],
                    processed_rows=0,
                    total_rows=0,
                    errors_count=len(parsed.get('errors', [])),
                )
                return

            rows = parsed.get('rows', [])
            _update_job(
                job_id,
                status='running',
                message='Importação em andamento...',
                total_rows=len(rows),
                ignored_columns=parsed.get('ignored_columns', []),
            )

            for row_data in rows:
                row_result = process_method(row_data)
                _append_job_row(job_id, row_result)

            _update_job(
                job_id,
                status='completed',
                completed=True,
                message='Importação concluída com sucesso.',
            )
        except Exception as exc:
            _update_job(
                job_id,
                status='failed',
                completed=True,
                message=f'Falha ao processar importação: {str(exc)}',
            )


def _run_xlsx_import_job(job_id, file_content, app_obj):
    _run_tabular_import_job(job_id, file_content, app_obj, 'parse_students_xlsx', 'process_student_record')


def _run_users_csv_import_job(job_id, file_content, app_obj):
    _run_tabular_import_job(job_id, file_content, app_obj, 'parse_users_csv', 'process_user_csv_record')


def _apply_import_rows_filter(rows, field, query):
    q = (query or '').strip().lower()
    if not q:
        return rows

    allowed_fields = {'row_number', 'nome', 'cpf', 'curso', 'ra', 'status', 'message'}
    normalized_field = (field or 'all').strip().lower()

    def match_row(row):
        if normalized_field in allowed_fields:
            value = row.get(normalized_field, '')
            return q in str(value).lower()

        searchable = [
            row.get('row_number', ''),
            row.get('nome', ''),
            row.get('cpf', ''),
            row.get('curso', ''),
            row.get('ra', ''),
            row.get('status', ''),
            row.get('message', ''),
        ]
        return any(q in str(value).lower() for value in searchable)

    return [row for row in rows if match_row(row)]


def _build_import_job_payload(job_id, page, per_page, filter_field, filter_query):
    page = max(page, 1)
    per_page = max(min(per_page, 100), 5)

    with _IMPORT_JOBS_LOCK:
        memory_job = _IMPORT_JOBS.get(job_id)
        file_job = _load_job(job_id)
        job = _best_job_state(memory_job, file_job)
        if not job:
            return None

        _IMPORT_JOBS[job_id] = job

        rows = list(job.get('rows', []))
        filtered_rows = _apply_import_rows_filter(rows, filter_field, filter_query)
        total_items = len(filtered_rows)
        pages = max(1, ceil(total_items / per_page))
        if page > pages:
            page = pages

        start = (page - 1) * per_page
        end = start + per_page
        page_items = filtered_rows[start:end]

        return {
            'job_id': job['job_id'],
            'import_type': job.get('import_type'),
            'status': job['status'],
            'completed': job['completed'],
            'message': job['message'],
            'total_rows': job['total_rows'],
            'processed_rows': job['processed_rows'],
            'created': job['created'],
            'updated': job['updated'],
            'unchanged': job['unchanged'],
            'errors_count': job['errors_count'],
            'ignored_columns': job['ignored_columns'],
            'rows': page_items,
            'filters': {
                'field': filter_field,
                'q': filter_query,
                'filtered_total_items': total_items,
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'pages': pages,
                'total_items': total_items,
            },
        }


def _cert_generated_dir() -> Path:
    return Path(current_app.root_path) / 'static' / 'certificates' / 'generated'


def _bytes_to_mb(size_bytes: int) -> float:
    if size_bytes <= 0:
        return 0.0
    return round(size_bytes / (1024 * 1024), 2)

@bp.route('/listar_usuarios', methods=['GET'])
@login_required
def listar_usuarios():
    if current_user.role not in ['admin', 'coordenador', 'gestor']:
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
    if not EventService.can_access_event_management(current_user):
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
    if not EventService.can_access_event_management(current_user):
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    try:
        activity_id = int(data.get('activity_id'))
    except (TypeError, ValueError):
        return jsonify({"erro": "Atividade inválida."}), 400

    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"erro": "Atividade não encontrada."}), 404

    event = db.session.get(Event, activity.event_id)
    if not event:
        return jsonify({"erro": "Evento não encontrado."}), 404

    if not EventService.can_add_event_participants(current_user, event):
        return jsonify({"erro": "Acesso negado para este evento."}), 403

    success, msg = admin_service.manual_enroll(
        data.get('cpf'),
        activity_id,
        actor_user=current_user,
        category_id=data.get('categoria_inscricao_id'),
    )
    
    if success:
        return jsonify({"mensagem": msg})

    if msg == "Seu perfil não está habilitado para este evento.":
        return jsonify({"erro": msg}), 403
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

@bp.route('/importar_usuarios_csv', methods=['POST'])
@login_required
def importar_usuarios_csv():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
    
    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"erro": "Nenhum arquivo selecionado"}), 400

    try:
        result = admin_service.import_users_csv(file)
    except Exception as exc:
        return jsonify({"erro": f"Falha ao processar CSV: {str(exc)}"}), 400

    imported_count = int(result.get('created', 0)) + int(result.get('updated', 0))
    return jsonify({
        "mensagem": result.get('message', 'Importação concluída.'),
        "importados": imported_count,
        "erros": result.get('errors', []),
        **result,
    })

@bp.route('/importar_alunos_xlsx', methods=['POST'])
@login_required
def importar_alunos_xlsx():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403

    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"erro": "Nenhum arquivo selecionado"}), 400

    try:
        result = admin_service.import_students_xlsx(file)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"erro": f"Falha ao processar XLSX: {str(exc)}"}), 400


@bp.route('/importar_alunos_xlsx/start', methods=['POST'])
@login_required
def importar_alunos_xlsx_start():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403

    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"erro": "Nenhum arquivo selecionado"}), 400

    with _IMPORT_JOBS_LOCK:
        active_job = _get_active_job_for_user(current_user.username)
        if active_job:
            return jsonify({
                'job_id': active_job['job_id'],
                'import_type': active_job.get('import_type'),
                'message': 'Já existe uma importação em andamento para este usuário.',
                'reused': True,
            }), 202

    job_id = uuid4().hex
    file_content = file.read()

    with _IMPORT_JOBS_LOCK:
        _IMPORT_JOBS[job_id] = {
            'job_id': job_id,
            'import_type': 'xlsx',
            'status': 'queued',
            'completed': False,
            'message': 'Importação iniciada.',
            'created_by': current_user.username,
            'updated_at': time.time(),
            'total_rows': 0,
            'processed_rows': 0,
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'errors_count': 0,
            'ignored_columns': [],
            'rows': [],
        }
        _persist_job(_IMPORT_JOBS[job_id])

    app_obj = current_app._get_current_object()
    worker = Thread(target=_run_xlsx_import_job, args=(job_id, file_content, app_obj), daemon=True)
    worker.start()

    return jsonify({'job_id': job_id, 'import_type': 'xlsx', 'message': 'Importação em processamento.'})


@bp.route('/importar_usuarios_csv/start', methods=['POST'])
@login_required
def importar_usuarios_csv_start():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403

    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"erro": "Nenhum arquivo selecionado"}), 400

    with _IMPORT_JOBS_LOCK:
        active_job = _get_active_job_for_user(current_user.username)
        if active_job:
            return jsonify({
                'job_id': active_job['job_id'],
                'import_type': active_job.get('import_type'),
                'message': 'Já existe uma importação em andamento para este usuário.',
                'reused': True,
            }), 202

    job_id = uuid4().hex
    file_content = file.read()

    with _IMPORT_JOBS_LOCK:
        _IMPORT_JOBS[job_id] = {
            'job_id': job_id,
            'import_type': 'csv',
            'status': 'queued',
            'completed': False,
            'message': 'Importação iniciada.',
            'created_by': current_user.username,
            'updated_at': time.time(),
            'total_rows': 0,
            'processed_rows': 0,
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'errors_count': 0,
            'ignored_columns': [],
            'rows': [],
        }
        _persist_job(_IMPORT_JOBS[job_id])

    app_obj = current_app._get_current_object()
    worker = Thread(target=_run_users_csv_import_job, args=(job_id, file_content, app_obj), daemon=True)
    worker.start()

    return jsonify({'job_id': job_id, 'import_type': 'csv', 'message': 'Importação em processamento.'})


@bp.route('/importar_alunos_xlsx/status/<job_id>', methods=['GET'])
@login_required
def importar_alunos_xlsx_status(job_id):
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    filter_field = request.args.get('field', 'all', type=str)
    filter_query = request.args.get('q', '', type=str)
    payload = _build_import_job_payload(job_id, page, per_page, filter_field, filter_query)
    if not payload:
        return jsonify({'erro': 'Job não encontrado.'}), 404
    return jsonify(payload)


@bp.route('/importar_usuarios_csv/status/<job_id>', methods=['GET'])
@login_required
def importar_usuarios_csv_status(job_id):
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    filter_field = request.args.get('field', 'all', type=str)
    filter_query = request.args.get('q', '', type=str)
    payload = _build_import_job_payload(job_id, page, per_page, filter_field, filter_query)
    if not payload:
        return jsonify({'erro': 'Job não encontrado.'}), 404
    return jsonify(payload)

@bp.route('/atualizar_permissoes', methods=['POST'])
@login_required
def atualizar_permissoes():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
        
    data = request.json
    success, msg = admin_service.update_user_permissions(
        data.get('username'), 
        data.get('can_create_events')
    )
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/permissoes_curso_lote', methods=['POST'])
@login_required
def permissoes_curso_lote():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403
        
    data = request.json
    count, msg = admin_service.bulk_update_permissions_by_course(
        data.get('course_id'), 
        data.get('can_create_events')
    )
    return jsonify({"mensagem": msg, "count": count})


@bp.route('/admin/certificados/cache/cleanup', methods=['POST'])
@login_required
def cleanup_generated_certificates_cache():
    if current_user.role != 'admin':
        return jsonify({"erro": "Negado"}), 403

    payload = request.get_json(silent=True) or {}
    raw_days = payload.get('older_than_days', 90)
    dry_run = bool(payload.get('dry_run', True))

    try:
        older_than_days = int(raw_days)
    except (TypeError, ValueError):
        return jsonify({"erro": "older_than_days inválido"}), 400

    if older_than_days < 0 or older_than_days > 3650:
        return jsonify({"erro": "older_than_days deve estar entre 0 e 3650"}), 400

    target_dir = _cert_generated_dir()
    if not target_dir.exists():
        return jsonify({
            "mode": "dry_run" if dry_run else "execute",
            "older_than_days": older_than_days,
            "target_dir": str(target_dir),
            "total_files": 0,
            "candidate_files": 0,
            "deleted_files": 0,
            "failed_files": 0,
            "freed_bytes": 0,
            "freed_mb": 0,
            "message": "Diretório de certificados gerados não existe.",
            "sample_files": []
        })

    cutoff_ts = time.time() - (older_than_days * 86400)
    all_files = []
    candidate_files = []

    for path in target_dir.glob('*.pdf'):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue

        file_info = {
            'name': path.name,
            'path': str(path),
            'size_bytes': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
            'modified_ts': stat.st_mtime,
        }
        all_files.append(file_info)
        if stat.st_mtime <= cutoff_ts:
            candidate_files.append(file_info)

    candidate_files.sort(key=lambda item: item['modified_ts'])
    total_candidate_bytes = sum(item['size_bytes'] for item in candidate_files)

    deleted_files = 0
    failed_files = 0
    freed_bytes = 0

    if not dry_run:
        for item in candidate_files:
            try:
                Path(item['path']).unlink(missing_ok=True)
                deleted_files += 1
                freed_bytes += item['size_bytes']
            except OSError:
                failed_files += 1

    response = {
        "mode": "dry_run" if dry_run else "execute",
        "older_than_days": older_than_days,
        "target_dir": str(target_dir),
        "total_files": len(all_files),
        "candidate_files": len(candidate_files),
        "deleted_files": deleted_files,
        "failed_files": failed_files,
        "freed_bytes": 0 if dry_run else freed_bytes,
        "freed_mb": 0 if dry_run else _bytes_to_mb(freed_bytes),
        "estimated_freed_bytes": total_candidate_bytes,
        "estimated_freed_mb": _bytes_to_mb(total_candidate_bytes),
        "message": "Simulação concluída." if dry_run else "Limpeza concluída.",
        "sample_files": [
            {
                "name": item['name'],
                "size_mb": _bytes_to_mb(item['size_bytes']),
                "modified_at": item['modified_at'],
            }
            for item in candidate_files[:10]
        ]
    }

    return jsonify(response)
