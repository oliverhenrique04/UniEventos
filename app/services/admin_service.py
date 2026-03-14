from app.models import User, Enrollment, Activity, Event, Course, db
from app.repositories.user_repository import UserRepository
from sqlalchemy import or_
import csv
import io
from openpyxl import load_workbook
from app.utils import normalize_cpf

class AdminService:
    """Service layer for administrative user management tasks.
    
    Handles user listing, creation, updates, and deletion with 
    advanced filtering and pagination support.
    """
    def __init__(self):
        self.user_repo = UserRepository()

    def list_users_paginated(self, page=1, per_page=10, filters=None):
        """Retrieves a paginated list of users with optional filtering.
        
        Filters can include: ra, curso, cpf, email, event_id, activity_id.
        """
        query = User.query
        
        if filters:
            if filters.get('ra'):
                query = query.filter(User.ra.ilike(f"%{filters['ra']}%"))
            if filters.get('curso'):
                query = query.join(Course, User.course_id == Course.id, isouter=True)
                query = query.filter(Course.nome.ilike(f"%{filters['curso']}%"))
            if filters.get('cpf'):
                cpf_digits = normalize_cpf(filters['cpf'])
                if cpf_digits:
                    query = query.filter(User.cpf.ilike(f"%{cpf_digits}%"))
            if filters.get('email'):
                query = query.filter(User.email.ilike(f"%{filters['email']}%"))
            if filters.get('nome'):
                query = query.filter(User.nome.ilike(f"%{filters['nome']}%"))
            
            # Filter by Event or Activity (requires joins)
            if filters.get('event_id') or filters.get('activity_id'):
                query = query.join(Enrollment, User.cpf == Enrollment.user_cpf)
                if filters.get('event_id'):
                    query = query.join(Activity, Enrollment.activity_id == Activity.id)
                    query = query.filter(Activity.event_id == filters['event_id'])
                if filters.get('activity_id'):
                    query = query.filter(Enrollment.activity_id == filters['activity_id'])

        return query.paginate(page=page, per_page=per_page, error_out=False)

    def buscar_usuarios_inscricao(self, termo):
        """Searches for users by normalized name, RA, or CPF."""
        from app.utils import normalizar_texto
        
        termo_norm = normalizar_texto(termo)
        if not termo_norm: return []
        
        all_users = User.query.all()
        matches = []
        
        for u in all_users:
            # Check RA or CPF (exact normalized match or contains)
            if termo_norm in normalizar_texto(u.ra) or termo_norm in normalizar_texto(u.cpf):
                matches.append(u)
                continue
            
            # Check Name (contains)
            if termo_norm in normalizar_texto(u.nome):
                matches.append(u)
        
        return matches[:10] # Limit to 10 results for performance

    def create_user(self, data):
        """Creates a new user manually."""
        if db.session.get(User, data.get('username')) or User.query.filter_by(cpf=data.get('cpf')).first():
            return None, "Usuário ou CPF já cadastrado."
            
        user = User(
            username=data.get('username'),
            nome=data.get('nome'),
            email=data.get('email'),
            cpf=data.get('cpf'),
            ra=data.get('ra'),
            curso=data.get('curso'),
            role=data.get('role', 'participante')
        )
        cpf_default = normalize_cpf(data.get('cpf'))
        user.set_password(data.get('password') or cpf_default)
        db.session.add(user)
        db.session.commit()
        return user, "Usuário criado com sucesso."

    def update_user_details(self, target_username: str, data: dict):
        """Updates an existing user's profile details."""
        user = self.user_repo.get_by_username(target_username)
        if not user:
            return False
            
        user.nome = data.get('nome', user.nome)
        user.cpf = data.get('cpf', user.cpf)
        user.email = data.get('email', user.email)
        user.ra = data.get('ra', user.ra)
        user.curso = data.get('curso', user.curso)
        user.role = data.get('role', user.role)
        
        if data.get('password'):
            user.set_password(data['password'])
            
        self.user_repo.update()
        return True

    def delete_user(self, username):
        """Deletes a user and their associations."""
        user = db.session.get(User, username)
        if not user: return False
        db.session.delete(user)
        db.session.commit()
        return True

    def manual_enroll(self, user_cpf, activity_id):
        """Manually enrolls a user into an activity."""
        try:
            activity_id = int(activity_id)
        except (TypeError, ValueError):
            return False, "Atividade inválida."

        user = self.user_repo.get_by_cpf(user_cpf)
        activity = db.session.get(Activity, activity_id)
        
        if not user or not activity:
            return False, "Usuário ou Atividade não encontrados."
            
        # Always use normalized persisted CPF from user record.
        existing = Enrollment.query.filter_by(user_cpf=user.cpf, activity_id=activity_id).first()
        if existing:
            return False, "Usuário já está inscrito nesta atividade."
            
        enrollment = Enrollment(
            activity_id=activity_id,
            user_cpf=user.cpf,
            nome=user.nome,
            presente=True # Admin manual enroll often implies immediate presence or force entry
        )
        db.session.add(enrollment)
        db.session.commit()
        return True, "Inscrição realizada com sucesso."

    def import_users_csv(self, file_stream):
        """
        Imports users from a CSV file.
        Expected format: username,email,nome,cpf,role,curso_nome
        """
        stream = io.StringIO(file_stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        success_count = 0
        errors = []
        
        for row in csv_input:
            try:
                username = row.get('username')
                cpf = row.get('cpf')
                
                if not username or not cpf:
                    continue
                    
                # Check if user exists
                if self.user_repo.get_by_username(username) or self.user_repo.get_by_cpf(cpf):
                    errors.append(f"Usuário {username} ou CPF {cpf} já existe.")
                    continue
                
                # Resolve course if provided
                course_obj = None
                curso_nome = row.get('curso_nome')
                if curso_nome:
                    course_obj = Course.query.filter(Course.nome.ilike(curso_nome)).first()
                
                user = User(
                    username=username,
                    email=row.get('email'),
                    nome=row.get('nome'),
                    cpf=cpf,
                    role=row.get('role', 'participante'),
                    curso=curso_nome,
                    course_id=course_obj.id if course_obj else None,
                    can_create_events=(row.get('can_create_events', '0') == '1')
                )
                cpf_default = normalize_cpf(cpf)
                user.set_password(row.get('password') or cpf_default)
                
                db.session.add(user)
                success_count += 1
            except Exception as e:
                errors.append(f"Erro na linha {username}: {str(e)}")
        
        db.session.commit()
        return success_count, errors

    @staticmethod
    def _normalize_cpf_digits(cpf):
        if not cpf:
            return ''
        return ''.join(ch for ch in str(cpf) if ch.isdigit())

    @staticmethod
    def _format_cpf_mask(cpf_digits):
        if len(cpf_digits) != 11:
            return None
        return f"{cpf_digits[0:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:11]}"

    def _find_user_by_cpf_flexible(self, cpf_raw):
        cpf_digits = self._normalize_cpf_digits(cpf_raw)
        if len(cpf_digits) != 11:
            return None

        cpf_masked = self._format_cpf_mask(cpf_digits)
        candidates = [cpf_raw, cpf_digits, cpf_masked]
        seen = set()

        for candidate in candidates:
            if not candidate:
                continue
            normalized = str(candidate).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            user = self.user_repo.get_by_cpf(normalized)
            if user:
                return user

        return None

    def parse_students_xlsx(self, file_stream):
        """Parses XLSX rows for student import and returns normalized row records."""
        workbook = load_workbook(filename=file_stream, read_only=True, data_only=True)
        sheet = workbook.active

        expected_headers = [
            'ALUNO_NOME', 'IES', 'CURSO', 'TURMA', 'CPF', 'DATANASCIMENTO',
            'SEXO', 'ESTADOCIVIL', 'MAE', 'NIVEL ESCOLAR', 'RA', 'TURNO',
            'PERIODO', 'RUA_NUMERO', 'BAIRRO', 'CEP', 'MUNICIPIO', 'ESTADO',
            'Total Geral'
        ]
        required_headers = {'ALUNO_NOME', 'CURSO', 'CPF'}

        rows = list(sheet.iter_rows(values_only=True))
        workbook.close()

        if not rows:
            return {
                'ok': False,
                'message': 'Arquivo XLSX vazio.',
                'rows': [],
                'errors': ['Arquivo sem linhas para processamento.'],
                'ignored_columns': expected_headers[1:]
            }

        headers = [str(h).strip() if h is not None else '' for h in rows[0]]
        header_map = {h.upper(): idx for idx, h in enumerate(headers) if h}

        missing_required = sorted([h for h in required_headers if h not in header_map])
        if missing_required:
            return {
                'ok': False,
                'message': 'Cabeçalho inválido.',
                'rows': [],
                'errors': [f"Colunas obrigatórias ausentes: {', '.join(missing_required)}"],
                'ignored_columns': []
            }

        ignored_columns = [col for col in expected_headers if col not in {'ALUNO_NOME', 'CURSO', 'CPF', 'RA'}]

        idx_nome = header_map.get('ALUNO_NOME')
        idx_curso = header_map.get('CURSO')
        idx_cpf = header_map.get('CPF')
        idx_ra = header_map.get('RA')
        idx_email = header_map.get('EMAIL')

        parsed_rows = []
        for row_number, row in enumerate(rows[1:], start=2):
            if row is None:
                continue

            nome = str(row[idx_nome]).strip() if idx_nome is not None and idx_nome < len(row) and row[idx_nome] is not None else ''
            curso_nome = str(row[idx_curso]).strip() if idx_curso is not None and idx_curso < len(row) and row[idx_curso] is not None else ''
            cpf_raw = str(row[idx_cpf]).strip() if idx_cpf is not None and idx_cpf < len(row) and row[idx_cpf] is not None else ''
            ra = str(row[idx_ra]).strip() if idx_ra is not None and idx_ra < len(row) and row[idx_ra] is not None else None
            email = str(row[idx_email]).strip().lower() if idx_email is not None and idx_email < len(row) and row[idx_email] is not None else ''

            if not any([nome, curso_nome, cpf_raw, ra, email]):
                continue

            parsed_rows.append({
                'row_number': row_number,
                'nome': nome,
                'curso_nome': curso_nome,
                'cpf_raw': cpf_raw,
                'ra': ra,
                'email': email,
                'has_ra_col': idx_ra is not None,
                'has_email_col': idx_email is not None,
            })

        return {
            'ok': True,
            'message': 'Arquivo lido com sucesso.',
            'rows': parsed_rows,
            'errors': [],
            'ignored_columns': ignored_columns,
        }

    def process_student_record(self, row_data):
        """Processes one student row and commits per-row for real-time progress updates."""
        row_number = row_data.get('row_number')
        nome = row_data.get('nome', '')
        curso_nome = row_data.get('curso_nome', '')
        cpf_raw = row_data.get('cpf_raw', '')
        ra = row_data.get('ra')
        email = row_data.get('email', '')
        has_ra_col = bool(row_data.get('has_ra_col'))
        has_email_col = bool(row_data.get('has_email_col'))

        cpf_digits = self._normalize_cpf_digits(cpf_raw)
        cpf_masked = self._format_cpf_mask(cpf_digits)

        base_payload = {
            'row_number': row_number,
            'nome': nome,
            'cpf': cpf_masked or cpf_raw,
            'curso': curso_nome,
            'ra': ra,
            'email': email,
        }

        if len(cpf_digits) != 11 or not cpf_masked:
            db.session.rollback()
            return {
                **base_payload,
                'status': 'error',
                'message': f"CPF inválido ({cpf_raw}).",
            }

        if not nome:
            db.session.rollback()
            return {
                **base_payload,
                'status': 'error',
                'message': 'ALUNO_NOME ausente.',
            }

        if not curso_nome:
            db.session.rollback()
            return {
                **base_payload,
                'status': 'error',
                'message': 'CURSO ausente.',
            }

        course_obj = Course.query.filter(Course.nome.ilike(curso_nome)).first()
        if not course_obj:
            db.session.rollback()
            return {
                **base_payload,
                'status': 'error',
                'message': f"Curso não encontrado ({curso_nome}).",
            }

        existing = self._find_user_by_cpf_flexible(cpf_masked)
        if existing:
            new_ra = ra if has_ra_col else existing.ra
            if has_ra_col and (new_ra is None or str(new_ra).strip() == ''):
                new_ra = None

            new_email = email if has_email_col else existing.email
            if has_email_col and (new_email is None or str(new_email).strip() == ''):
                new_email = None

            if has_ra_col and new_ra:
                ra_owner = User.query.filter(User.ra == new_ra, User.username != existing.username).first()
                if ra_owner:
                    db.session.rollback()
                    return {
                        **base_payload,
                        'status': 'error',
                        'message': f"RA {new_ra} já pertence a outro usuário.",
                    }

            if has_email_col and new_email:
                email_owner = User.query.filter(User.email == new_email, User.username != existing.username).first()
                if email_owner:
                    db.session.rollback()
                    return {
                        **base_payload,
                        'status': 'error',
                        'message': f"EMAIL {new_email} já pertence a outro usuário.",
                    }

            changed = False
            if existing.nome != nome:
                existing.nome = nome
                changed = True
            if existing.cpf != cpf_digits:
                existing.cpf = cpf_digits
                changed = True
            if existing.course_id != course_obj.id:
                existing.course_id = course_obj.id
                changed = True
            if has_ra_col and existing.ra != new_ra:
                existing.ra = new_ra
                changed = True
            if has_email_col and existing.email != new_email:
                existing.email = new_email
                changed = True

            if changed:
                db.session.commit()
                return {
                    **base_payload,
                    'status': 'updated',
                    'message': f"Usuário {existing.username} atualizado.",
                }

            db.session.rollback()
            return {
                **base_payload,
                'status': 'unchanged',
                'message': f"Usuário {existing.username} sem alteração.",
            }

        if not email:
            db.session.rollback()
            return {
                **base_payload,
                'status': 'error',
                'message': 'Novo aluno sem EMAIL, criação bloqueada.',
            }

        username = cpf_digits
        username_owner = self.user_repo.get_by_username(username)
        if username_owner:
            db.session.rollback()
            return {
                **base_payload,
                'status': 'error',
                'message': f"Username {username} já existe para outro usuário.",
            }

        new_ra = ra if has_ra_col else None
        if new_ra is not None and str(new_ra).strip() == '':
            new_ra = None

        if new_ra:
            ra_owner = User.query.filter_by(ra=new_ra).first()
            if ra_owner:
                db.session.rollback()
                return {
                    **base_payload,
                    'status': 'error',
                    'message': f"RA {new_ra} já cadastrado.",
                }

        user = User(
            username=username,
            email=email,
            nome=nome,
            cpf=cpf_masked,
            ra=new_ra,
            role='participante',
            course_id=course_obj.id,
            can_create_events=False,
        )
        user.set_password(cpf_digits)
        db.session.add(user)
        db.session.commit()
        return {
            **base_payload,
            'status': 'created',
            'message': f"Usuário {username} criado.",
        }

    def import_students_xlsx(self, file_stream):
        """
        Imports and upserts students from an academic XLSX file.

        Rules:
        - Upsert key: CPF
        - Existing users: update all mapped fields received from XLSX (nome, curso, ra, email)
        - New users: create only if email is present in the row
        - New users always receive role='participante'
        - Username for new users is CPF digits (no punctuation)
        """
        parsed = self.parse_students_xlsx(file_stream)
        if not parsed.get('ok'):
            return {
                'message': parsed.get('message', 'Falha ao ler XLSX.'),
                'total_rows': 0,
                'created': 0,
                'updated': 0,
                'unchanged': 0,
                'errors': parsed.get('errors', []),
                'ignored_columns': parsed.get('ignored_columns', []),
            }

        created = 0
        updated = 0
        unchanged = 0
        errors = []
        processed_rows = len(parsed.get('rows', []))

        for row_data in parsed.get('rows', []):
            outcome = self.process_student_record(row_data)
            status = outcome.get('status')
            if status == 'created':
                created += 1
            elif status == 'updated':
                updated += 1
            elif status == 'unchanged':
                unchanged += 1
            else:
                errors.append(f"Linha {outcome.get('row_number')}: {outcome.get('message')}")

        return {
            'message': f"Processadas {processed_rows} linhas.",
            'total_rows': processed_rows,
            'created': created,
            'updated': updated,
            'unchanged': unchanged,
            'errors': errors,
            'ignored_columns': parsed.get('ignored_columns', []),
        }

    def update_user_permissions(self, username, can_create_events):
        """Updates specific permission flags for a user."""
        user = self.user_repo.get_by_username(username)
        if not user:
            return False, "Usuário não encontrado."
            
        user.can_create_events = can_create_events
        self.user_repo.update()
        return True, "Permissões atualizadas."

    def bulk_update_permissions_by_course(self, course_id, can_create_events, role_filter='professor'):
        """
        Updates permissions for all users of a specific course and role.
        """
        users = User.query.filter_by(course_id=course_id, role=role_filter).all()
        count = 0
        for user in users:
            user.can_create_events = can_create_events
            count += 1
        
        db.session.commit()
        return count, f"{count} professores atualizados."
