import os
import time
import hashlib
import secrets
import sqlite3
from io import BytesIO
from datetime import datetime, date
from flask import Flask, request, jsonify, render_template, session, redirect, send_file
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key = "chave_mestra_v16_certificado_fix"
DB_NAME = "sistema_academico.db"

# ================= BANCO DE DADOS =================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT PRIMARY KEY, password TEXT, role TEXT, nome TEXT, cpf TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS events 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, nome TEXT, descricao TEXT, 
                      tipo TEXT, data_inicio TEXT, hora_inicio TEXT, data_fim TEXT, hora_fim TEXT,
                      token_publico TEXT, status TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS activities 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, nome TEXT, 
                      palestrante TEXT, local TEXT, descricao TEXT, 
                      data_atv TEXT, hora_atv TEXT, 
                      carga_horaria INTEGER, vagas INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS activity_enrollments 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, activity_id INTEGER, event_id INTEGER, 
                      cpf TEXT, nome TEXT, presente INTEGER)''')
        
        c.execute("SELECT * FROM users WHERE username = 'admin'")
        if not c.fetchone():
            c.execute("INSERT INTO users VALUES ('admin', 'admin', 'admin', 'Super Admin', '000.000.000-00')")
            c.execute("INSERT INTO users VALUES ('prof', '1234', 'professor', 'Prof. Pardal', '111.111.111-11')")
            c.execute("INSERT INTO users VALUES ('aluno', '1234', 'participante', 'Lucas Aluno', '222.222.222-22')")
        conn.commit()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ================= AUXILIARES =================
def gerar_hash_dinamico(activity_id):
    timestamp = int(time.time() / 30)
    raw = f"{activity_id}:{timestamp}:{app.secret_key}"
    return hashlib.sha256(raw.encode()).hexdigest()

def validar_hash_dinamico(activity_id, token_recebido):
    timestamp_atual = int(time.time() / 30)
    for t in [timestamp_atual, timestamp_atual - 1]:
        raw = f"{activity_id}:{t}:{app.secret_key}"
        if token_recebido == hashlib.sha256(raw.encode()).hexdigest():
            return True
    return False

# ================= ROTAS =================
@app.route('/')
def index():
    if not os.path.exists(DB_NAME): init_db()
    if 'user' not in session: return render_template('login_register.html')
    return render_template('index.html', user=session['user'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- AUTH ---
@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (d.get('username'),)).fetchone()
    conn.close()
    if user and user['password'] == d.get('password'):
        session['user'] = dict(user)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Dados inválidos"}), 401

@app.route('/api/registrar', methods=['POST'])
def registrar():
    d = request.json
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                        (d.get('username'), d.get('password'), 'participante', d.get('nome'), d.get('cpf')))
        return jsonify({"mensagem": "Cadastrado!"})
    except: return jsonify({"erro": "Usuário já existe"}), 400

# --- ADMIN ---
@app.route('/api/listar_usuarios', methods=['GET'])
def listar_usuarios():
    if session.get('user')['role'] not in ['admin', 'coordenador']: return jsonify([]), 403
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/editar_usuario', methods=['POST'])
def editar_usuario():
    if session.get('user')['role'] != 'admin': return jsonify({"erro": "Negado"}), 403
    d = request.json
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE users SET nome=?, cpf=?, role=? WHERE username=?",
                    (d.get('nome'), d.get('cpf'), d.get('role'), d.get('username_alvo')))
    return jsonify({"mensagem": "Atualizado!"})

# --- RELATÓRIOS ---
@app.route('/api/relatorio_inscritos/<int:evt_id>', methods=['GET'])
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

# --- EVENTOS ---
@app.route('/api/criar_evento', methods=['POST'])
def criar_evento():
    user = session.get('user')
    if user['role'] == 'participante': return jsonify({"erro": "Negado"}), 403
    
    d = request.json
    
    # Validação de Data
    try:
        data_ini_obj = datetime.strptime(d.get('data_inicio'), '%Y-%m-%d').date()
        hoje_obj = datetime.now().date()
        if data_ini_obj < hoje_obj: return jsonify({"erro": f"Data de início no passado!"}), 400
        if d.get('data_fim'):
            data_fim_obj = datetime.strptime(d.get('data_fim'), '%Y-%m-%d').date()
            if data_fim_obj < data_ini_obj: return jsonify({"erro": "Data fim menor que início"}), 400
    except ValueError: pass

    token = secrets.token_urlsafe(12)
    is_rapido = d.get('is_rapido')
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO events 
                          (owner, nome, descricao, tipo, data_inicio, hora_inicio, data_fim, hora_fim, token_publico, status) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (user['username'], d.get('nome'), d.get('descricao'), 
                        'RAPIDO' if is_rapido else 'PADRAO',
                        d.get('data_inicio'), d.get('hora_inicio'), d.get('data_fim'), d.get('hora_fim'), token, 'ABERTO'))
        event_id = cursor.lastrowid
        
        if is_rapido:
            # Evento rápido = 0 horas
            cursor.execute('''INSERT INTO activities (event_id, nome, palestrante, local, descricao, data_atv, hora_atv, carga_horaria, vagas) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (event_id, "Check-in Presença", "", "", "Registro de presença.", 
                            d.get('data_inicio'), d.get('hora_inicio'), 0, -1))
        else:
            for atv in d.get('atividades', []):
                try: horas = int(atv.get('horas', 0))
                except: horas = 0
                try: vagas = int(atv.get('vagas', 0))
                except: vagas = -1

                cursor.execute('''INSERT INTO activities (event_id, nome, palestrante, local, descricao, data_atv, hora_atv, carga_horaria, vagas) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               (event_id, atv['nome'], atv['palestrante'], atv['local'], atv['descricao'], 
                                atv.get('data_atv'), atv.get('hora_atv'), horas, vagas))
                           
    return jsonify({"mensagem": "Criado!", "link": f"/inscrever/{token}"})

@app.route('/api/editar_evento', methods=['POST'])
def editar_evento():
    user = session.get('user')
    d = request.json
    evt_id = d.get('id')
    conn = get_db()
    evt = conn.execute("SELECT * FROM events WHERE id=?", (evt_id,)).fetchone()
    
    if user['role'] != 'admin' and evt['owner'] != user['username']:
        conn.close()
        return jsonify({"erro": "Sem permissão"}), 403
        
    with sqlite3.connect(DB_NAME) as w_conn:
        w_conn.execute('''UPDATE events SET nome=?, descricao=?, data_inicio=?, hora_inicio=?, data_fim=?, hora_fim=? 
                          WHERE id=?''', 
                       (d.get('nome'), d.get('descricao'), d.get('data_inicio'), d.get('hora_inicio'), d.get('data_fim'), d.get('hora_fim'), evt_id))
        
        w_conn.execute("DELETE FROM activities WHERE event_id=?", (evt_id,))
        
        for atv in d.get('atividades', []):
            try: horas = int(atv.get('horas', 0))
            except: horas = 0
            try: vagas = int(atv.get('vagas', 0))
            except: vagas = -1

            w_conn.execute('''INSERT INTO activities (event_id, nome, palestrante, local, descricao, data_atv, hora_atv, carga_horaria, vagas) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (evt_id, atv['nome'], atv['palestrante'], atv['local'], atv['descricao'], atv.get('data_atv'), atv.get('hora_atv'), horas, vagas))
    
    return jsonify({"mensagem": "Atualizado!"})

@app.route('/api/eventos', methods=['GET'])
def listar_eventos():
    user = session.get('user')
    if not user: return jsonify([]), 401
    conn = get_db()
    
    if user['role'] in ['admin', 'participante']:
        eventos_raw = conn.execute("SELECT * FROM events").fetchall()
    else:
        eventos_raw = conn.execute("SELECT * FROM events WHERE owner = ?", (user['username'],)).fetchall()
    
    lista = []
    for ev in eventos_raw:
        ev_dict = dict(ev)
        atvs = conn.execute("SELECT * FROM activities WHERE event_id = ?", (ev['id'],)).fetchall()
        atvs_list = []
        for a in atvs:
            a_dict = dict(a)
            inscricao = conn.execute("SELECT * FROM activity_enrollments WHERE activity_id=? AND cpf=?", 
                                    (a['id'], user['cpf'])).fetchone()
            total_inscritos = conn.execute("SELECT COUNT(*) FROM activity_enrollments WHERE activity_id=?", 
                                          (a['id'],)).fetchone()[0]
            a_dict['inscrito'] = True if inscricao else False
            a_dict['total_inscritos'] = total_inscritos
            atvs_list.append(a_dict)
        ev_dict['atividades'] = atvs_list
        lista.append(ev_dict)
    conn.close()
    return jsonify(lista)

# --- INSCRIÇÃO & PRESENÇA ---
@app.route('/api/toggle_inscricao', methods=['POST'])
def toggle_inscricao():
    user = session.get('user')
    d = request.json
    if not user: return jsonify({"erro": "Sessão expirada"}), 401
    atv_id = int(d.get('activity_id'))
    acao = d.get('acao')
    conn = get_db()
    atv = conn.execute("SELECT * FROM activities WHERE id=?", (atv_id,)).fetchone()
    if not atv: conn.close(); return jsonify({"erro": "Atividade não encontrada"}), 404

    if acao == 'inscrever':
        ja_inscrito = conn.execute("SELECT * FROM activity_enrollments WHERE activity_id=? AND cpf=?", (atv_id, user['cpf'])).fetchone()
        if ja_inscrito: conn.close(); return jsonify({"mensagem": "Já inscrito"})
        
        count = conn.execute("SELECT COUNT(*) FROM activity_enrollments WHERE activity_id=?", (atv_id,)).fetchone()[0]
        if atv['vagas'] != -1 and count >= atv['vagas']: conn.close(); return jsonify({"erro": "Lotado!"}), 400
        
        try:
            with sqlite3.connect(DB_NAME) as w_conn:
                w_conn.execute("INSERT INTO activity_enrollments (activity_id, event_id, cpf, nome, presente) VALUES (?, ?, ?, ?, 0)",
                              (atv_id, atv['event_id'], user['cpf'], user['nome']))
            return jsonify({"mensagem": "Inscrição Realizada!"})
        except: return jsonify({"erro": "Erro bd"}), 500

    elif acao == 'sair':
        with sqlite3.connect(DB_NAME) as w_conn:
            w_conn.execute("DELETE FROM activity_enrollments WHERE activity_id=? AND cpf=?", (atv_id, user['cpf']))
        return jsonify({"mensagem": "Desinscrição realizada."})
    return jsonify({"erro": "Ação inválida"}), 400

@app.route('/api/qrcode_atividade/<int:atv_id>')
def qrcode_atividade(atv_id):
    if not atv_id: return "ID Inválido", 404
    try:
        token = gerar_hash_dinamico(atv_id)
        conn = get_db()
        atv = conn.execute("SELECT event_id FROM activities WHERE id=?", (atv_id,)).fetchone()
        conn.close()
        
        if not atv: return "Atividade não encontrada", 404
        
        conteudo = f"CHECKIN:{atv['event_id']}:{atv_id}:{token}"
        qr = qrcode.QRCode(box_size=20, border=1)
        qr.add_data(conteudo)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except: return "Erro QR", 500

@app.route('/api/validar_presenca', methods=['POST'])
def validar_presenca():
    user = session.get('user')
    if not user: return jsonify({"erro": "Faça login novamente"}), 401
    token_full = request.json.get('token', '')
    try:
        parts = token_full.split(":")
        evt_id, atv_id, hash_rcv = int(parts[1]), int(parts[2]), parts[3]
    except: return jsonify({"erro": "QR Inválido"}), 400
        
    if not validar_hash_dinamico(atv_id, hash_rcv): return jsonify({"erro": "Código expirado"}), 400
    
    conn = get_db()
    inscricao = conn.execute("SELECT * FROM activity_enrollments WHERE activity_id=? AND cpf=?", (atv_id, user['cpf'])).fetchone()
    
    # Auto-inscrição para check-in rápido
    if not inscricao:
        atv = conn.execute("SELECT * FROM activities WHERE id=?", (atv_id,)).fetchone()
        if atv and atv['nome'] == "Check-in Presença":
             with sqlite3.connect(DB_NAME) as w_conn:
                w_conn.execute("INSERT INTO activity_enrollments (activity_id, event_id, cpf, nome, presente) VALUES (?, ?, ?, ?, 1)",
                              (atv_id, evt_id, user['cpf'], user['nome']))
             conn.close()
             return jsonify({"status": "success", "mensagem": "Presença Registrada!", "download_link": f"/certificado/{evt_id}/{user['cpf']}"})
        else:
            conn.close()
            return jsonify({"erro": "Você não se inscreveu."}), 403

    with sqlite3.connect(DB_NAME) as db:
        db.execute("UPDATE activity_enrollments SET presente=1 WHERE id=?", (inscricao['id'],))
        
    return jsonify({"status": "success", "mensagem": "Presença confirmada!", "download_link": f"/certificado/{evt_id}/{user['cpf']}"})

# --- CERTIFICADO (CORREÇÃO DE CARGA HORÁRIA) ---
@app.route('/certificado/<int:evt_id>/<cpf>')
def baixar_certificado(evt_id, cpf):
    conn = get_db()
    evt = conn.execute("SELECT * FROM events WHERE id=?", (evt_id,)).fetchone()
    presencas = conn.execute('''
        SELECT a.nome, a.carga_horaria, a.palestrante, a.data_atv 
        FROM activity_enrollments ae
        JOIN activities a ON ae.activity_id = a.id
        WHERE ae.event_id = ? AND ae.cpf = ? AND ae.presente = 1
    ''', (evt_id, cpf)).fetchall()
    
    user_dados = conn.execute("SELECT nome FROM users WHERE cpf=?", (cpf,)).fetchone()
    conn.close()
    
    if not presencas: return "<h1>Erro: Nenhuma presença confirmada.</h1>", 403
    
    total_horas = sum([p['carga_horaria'] for p in presencas])
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    
    p.setFont("Helvetica-Bold", 26)
    p.drawCentredString(w/2, 700, "CERTIFICADO DE EXTENSÃO")
    p.setFont("Helvetica", 14)
    p.drawCentredString(w/2, 620, "Certificamos que")
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(w/2, 590, user_dados['nome'] if user_dados else "Participante")
    p.setFont("Helvetica", 12)
    p.drawCentredString(w/2, 570, f"CPF: {cpf}")
    
    p.setFont("Helvetica", 14)
    p.drawCentredString(w/2, 520, f"Participou do evento: {evt['nome']}")
    
    # CORREÇÃO: Só mostra horas se > 0
    if total_horas > 0:
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(w/2, 490, f"Carga Horária Total: {total_horas} horas")
    else:
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(w/2, 490, "Participação Confirmada")
    
    y = 420
    p.setFont("Helvetica-Bold", 12)
    p.drawString(80, y, "Atividades Concluídas:")
    y -= 25
    p.setFont("Helvetica", 10)
    
    for item in presencas:
        texto = f"• {item['nome']}"
        if item['carga_horaria'] > 0: texto += f" ({item['carga_horaria']}h)"
        if item['data_atv']: texto += f" - {item['data_atv']}"
        if item['palestrante']: texto += f" | {item['palestrante']}"
        p.drawString(90, y, texto)
        y -= 15
        
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="certificado.pdf")

if __name__ == '__main__':
    if not os.path.exists(DB_NAME): init_db()
    app.run(debug=True, port=5000)