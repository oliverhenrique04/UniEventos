from flask import Blueprint, request, jsonify, session
from datetime import datetime
import secrets
from app.db import get_db

events_bp = Blueprint('events', __name__)

@events_bp.route('/api/criar_evento', methods=['POST'])
def criar_evento():
    user = session.get('user')
    if user['role'] == 'participante': return jsonify({"erro": "Negado"}), 403
    
    d = request.json
    try:
        data_ini_obj = datetime.strptime(d.get('data_inicio'), '%Y-%m-%d').date()
        hoje_obj = datetime.now().date()
        if data_ini_obj < hoje_obj: return jsonify({"erro": "Data de início no passado!"}), 400
        if d.get('data_fim'):
            data_fim_obj = datetime.strptime(d.get('data_fim'), '%Y-%m-%d').date()
            if data_fim_obj < data_ini_obj: return jsonify({"erro": "Data fim menor que início"}), 400
    except ValueError: pass

    token = secrets.token_urlsafe(12)
    is_rapido = d.get('is_rapido')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO events (owner, nome, descricao, tipo, data_inicio, hora_inicio, data_fim, hora_fim, token_publico, status) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (user['username'], d.get('nome'), d.get('descricao'), 'RAPIDO' if is_rapido else 'PADRAO',
                    d.get('data_inicio'), d.get('hora_inicio'), d.get('data_fim'), d.get('hora_fim'), token, 'ABERTO'))
    event_id = cursor.lastrowid
    
    if is_rapido:
        cursor.execute('''INSERT INTO activities (event_id, nome, palestrante, local, descricao, data_atv, hora_atv, carga_horaria, vagas) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (event_id, "Check-in Presença", "", "", "Registro de presença.", d.get('data_inicio'), d.get('hora_inicio'), 0, -1))
    else:
        for atv in d.get('atividades', []):
            try: horas = int(atv.get('horas', 0))
            except: horas = 0
            try: vagas = int(atv.get('vagas', 0))
            except: vagas = -1
            cursor.execute('''INSERT INTO activities (event_id, nome, palestrante, local, descricao, data_atv, hora_atv, carga_horaria, vagas) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (event_id, atv['nome'], atv['palestrante'], atv['local'], atv['descricao'], atv.get('data_atv'), atv.get('hora_atv'), horas, vagas))
    conn.commit()
    conn.close()
    return jsonify({"mensagem": "Criado!", "link": f"/inscrever/{token}"})

@events_bp.route('/api/eventos', methods=['GET'])
def listar_eventos():
    user = session.get('user')
    if not user: return jsonify([]), 401
    conn = get_db()
    
    if user['role'] in ['admin', 'participante']:
        query = "SELECT * FROM events"
        params = ()
    else:
        query = "SELECT * FROM events WHERE owner = ?"
        params = (user['username'],)
        
    eventos_raw = conn.execute(query, params).fetchall()
    
    lista = []
    for ev in eventos_raw:
        ev_dict = dict(ev)
        atvs = conn.execute("SELECT * FROM activities WHERE event_id = ?", (ev['id'],)).fetchall()
        atvs_list = []
        for a in atvs:
            a_dict = dict(a)
            inscricao = conn.execute("SELECT * FROM activity_enrollments WHERE activity_id=? AND cpf=?", (a['id'], user['cpf'])).fetchone()
            total_inscritos = conn.execute("SELECT COUNT(*) FROM activity_enrollments WHERE activity_id=?", (a['id'],)).fetchone()[0]
            a_dict['inscrito'] = True if inscricao else False
            a_dict['total_inscritos'] = total_inscritos
            atvs_list.append(a_dict)
        ev_dict['atividades'] = atvs_list
        lista.append(ev_dict)
    conn.close()
    return jsonify(lista)

@events_bp.route('/api/editar_evento', methods=['POST'])
def editar_evento():
    user = session.get('user')
    d = request.json
    evt_id = d.get('id')
    conn = get_db()
    evt = conn.execute("SELECT * FROM events WHERE id=?", (evt_id,)).fetchone()
    
    if user['role'] != 'admin' and evt['owner'] != user['username']:
        conn.close()
        return jsonify({"erro": "Sem permissão"}), 403
        
    conn.execute('''UPDATE events SET nome=?, descricao=?, data_inicio=?, hora_inicio=?, data_fim=?, hora_fim=? WHERE id=?''', 
                   (d.get('nome'), d.get('descricao'), d.get('data_inicio'), d.get('hora_inicio'), d.get('data_fim'), d.get('hora_fim'), evt_id))
    
    conn.execute("DELETE FROM activities WHERE event_id=?", (evt_id,))
    
    for atv in d.get('atividades', []):
        try: horas = int(atv.get('horas', 0))
        except: horas = 0
        try: vagas = int(atv.get('vagas', 0))
        except: vagas = -1
        conn.execute('''INSERT INTO activities (event_id, nome, palestrante, local, descricao, data_atv, hora_atv, carga_horaria, vagas) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (evt_id, atv['nome'], atv['palestrante'], atv['local'], atv['descricao'], atv.get('data_atv'), atv.get('hora_atv'), horas, vagas))
    conn.commit()
    conn.close()
    return jsonify({"mensagem": "Atualizado!"})

@events_bp.route('/api/relatorio_inscritos/<int:evt_id>', methods=['GET'])
def relatorio_inscritos(evt_id):
    user = session.get('user')
    conn = get_db()
    evt = conn.execute("SELECT * FROM events WHERE id=?", (evt_id,)).fetchone()
    if user['role'] != 'admin' and evt['owner'] != user['username']:
        conn.close()
        return jsonify({"erro": "Sem permissão"}), 403
    atividades = conn.execute("SELECT * FROM activities WHERE event_id=?", (evt_id,)).fetchall()
    relatorio = []
    for atv in atividades:
        inscritos = conn.execute("SELECT nome, cpf, presente FROM activity_enrollments WHERE activity_id=?", (atv['id'],)).fetchall()
        relatorio.append({"atividade": atv['nome'], "inscritos": [dict(i) for i in inscritos]})
    conn.close()
    return jsonify(relatorio)