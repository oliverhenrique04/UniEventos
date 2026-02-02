import sqlite3
from app.db import DB_NAME

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
        
        # Admin padrão
        c.execute("SELECT * FROM users WHERE username = 'admin'")
        if not c.fetchone():
            c.execute("INSERT INTO users VALUES ('admin', 'admin', 'admin', 'Super Admin', '000.000.000-00')")
            c.execute("INSERT INTO users VALUES ('prof', '1234', 'professor', 'Prof. Pardal', '111.111.111-11')")
            c.execute("INSERT INTO users VALUES ('aluno', '1234', 'participante', 'Lucas Aluno', '222.222.222-22')")
        conn.commit()