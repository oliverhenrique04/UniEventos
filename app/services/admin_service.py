from app.models import User, Enrollment, Activity, Event, Course, db
from app.repositories.user_repository import UserRepository
from sqlalchemy import or_
import csv
import io

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
                query = query.filter(User.curso.ilike(f"%{filters['curso']}%"))
            if filters.get('cpf'):
                query = query.filter(User.cpf.ilike(f"%{filters['cpf']}%"))
            if filters.get('email'):
                query = query.filter(User.email.ilike(f"%{filters['email']}%"))
            if filters.get('nome'):
                query = query.filter(User.nome.ilike(f"%{filters['nome']}%"))
            
            # Filter by Event or Activity (requires joins)
            if filters.get('event_id') or filters.get('activity_id'):
                query = query.join(Enrollment, User.cpf == Enrollment.user_cpf)
                if filters.get('event_id'):
                    query = query.filter(Enrollment.event_id == filters['event_id'])
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
        if User.query.get(data.get('username')) or User.query.filter_by(cpf=data.get('cpf')).first():
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
        user.set_password(data.get('password', '123456'))
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
        user = User.query.get(username)
        if not user: return False
        db.session.delete(user)
        db.session.commit()
        return True

    def manual_enroll(self, user_cpf, activity_id):
        """Manually enrolls a user into an activity."""
        user = User.query.filter_by(cpf=user_cpf).first()
        activity = Activity.query.get(activity_id)
        
        if not user or not activity:
            return False, "Usuário ou Atividade não encontrados."
            
        existing = Enrollment.query.filter_by(user_cpf=user_cpf, activity_id=activity_id).first()
        if existing:
            return False, "Usuário já está inscrito nesta atividade."
            
        enrollment = Enrollment(
            activity_id=activity_id,
            event_id=activity.event_id,
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
                    curso=curso_nome, # Keep string for legacy
                    course_id=course_obj.id if course_obj else None,
                    can_create_events=(row.get('can_create_events', '0') == '1')
                )
                user.set_password(row.get('password', '123456')) # Default password
                
                db.session.add(user)
                success_count += 1
            except Exception as e:
                errors.append(f"Erro na linha {username}: {str(e)}")
        
        db.session.commit()
        return success_count, errors

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
