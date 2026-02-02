from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Event, Activity, db
import secrets
from datetime import datetime

bp = Blueprint('events', __name__, url_prefix='/api')

@bp.route('/criar_evento', methods=['POST'])
@login_required
def criar_evento():
    if current_user.role == 'participante':
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    
    # Validation
    try:
        data_ini_obj = datetime.strptime(data.get('data_inicio'), '%Y-%m-%d').date()
        hoje_obj = datetime.now().date()
        if data_ini_obj < hoje_obj:
            return jsonify({"erro": f"Data de início no passado!"}), 400
        if data.get('data_fim'):
            data_fim_obj = datetime.strptime(data.get('data_fim'), '%Y-%m-%d').date()
            if data_fim_obj < data_ini_obj:
                return jsonify({"erro": "Data fim menor que início"}), 400
    except ValueError:
        pass # Ignore date parsing errors if fields are missing/empty, logic might fail later or db handles it

    token = secrets.token_urlsafe(12)
    is_rapido = data.get('is_rapido')
    
    event = Event(
        owner_username=current_user.username,
        nome=data.get('nome'),
        descricao=data.get('descricao'),
        tipo='RAPIDO' if is_rapido else 'PADRAO',
        data_inicio=data.get('data_inicio'),
        hora_inicio=data.get('hora_inicio'),
        data_fim=data.get('data_fim'),
        hora_fim=data.get('hora_fim'),
        token_publico=token,
        status='ABERTO'
    )
    
    db.session.add(event)
    db.session.flush() # Get ID
    
    if is_rapido:
        # Create default check-in activity
        activity = Activity(
            event_id=event.id,
            nome="Check-in Presença",
            palestrante="",
            local="",
            descricao="Registro de presença.",
            data_atv=data.get('data_inicio'),
            hora_atv=data.get('hora_inicio'),
            carga_horaria=0,
            vagas=-1
        )
        db.session.add(activity)
    else:
        for atv in data.get('atividades', []):
            try: horas = int(atv.get('horas', 0))
            except: horas = 0
            try: vagas = int(atv.get('vagas', 0))
            except: vagas = -1
            
            activity = Activity(
                event_id=event.id,
                nome=atv['nome'],
                palestrante=atv['palestrante'],
                local=atv['local'],
                descricao=atv['descricao'],
                data_atv=atv.get('data_atv'),
                hora_atv=atv.get('hora_atv'),
                carga_horaria=horas,
                vagas=vagas
            )
            db.session.add(activity)
            
    db.session.commit()
    return jsonify({"mensagem": "Criado!", "link": f"/inscrever/{token}"})

@bp.route('/editar_evento', methods=['POST'])
@login_required
def editar_evento():
    data = request.json
    evt_id = data.get('id')
    event = Event.query.get(evt_id)
    
    if not event:
        return jsonify({"erro": "Evento não encontrado"}), 404
        
    if current_user.role != 'admin' and event.owner_username != current_user.username:
        return jsonify({"erro": "Sem permissão"}), 403
        
    event.nome = data.get('nome')
    event.descricao = data.get('descricao')
    event.data_inicio = data.get('data_inicio')
    event.hora_inicio = data.get('hora_inicio')
    event.data_fim = data.get('data_fim')
    event.hora_fim = data.get('hora_fim')
    
    # Replace activities
    Activity.query.filter_by(event_id=evt_id).delete()
    
    for atv in data.get('atividades', []):
        try: horas = int(atv.get('horas', 0))
        except: horas = 0
        try: vagas = int(atv.get('vagas', 0))
        except: vagas = -1

        new_atv = Activity(
            event_id=evt_id,
            nome=atv['nome'],
            palestrante=atv['palestrante'],
            local=atv['local'],
            descricao=atv['descricao'],
            data_atv=atv.get('data_atv'),
            hora_atv=atv.get('hora_atv'),
            carga_horaria=horas,
            vagas=vagas
        )
        db.session.add(new_atv)
        
    db.session.commit()
    return jsonify({"mensagem": "Atualizado!"})

@bp.route('/eventos', methods=['GET'])
@login_required
def listar_eventos():
    if current_user.role in ['admin', 'participante']:
        events = Event.query.all()
    else:
        events = Event.query.filter_by(owner_username=current_user.username).all()
        
    return jsonify([e.to_dict(current_user) for e in events])
