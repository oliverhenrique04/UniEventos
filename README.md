
# UniEventos - Sistema de Gestão Acadêmica

O **UniEventos** é uma plataforma completa para gerenciamento de eventos acadêmicos, workshops e aulas magnas. O sistema gerencia todo o ciclo de vida do evento: desde a criação e inscrição até o controle de presença via **QR Code Dinâmico** e emissão automática de certificados em PDF.

> **Versão:** 

---

## Funcionalidades Principais

### Controle de Acesso e Perfis
* **Admin:** Acesso total ao sistema. Pode promover usuários, gerenciar todos os eventos e visualizar relatórios globais.
* **Professor/Coordenador:** Cria e edita eventos, projeta QR Codes para chamada e monitora inscritos.
* **Participante (Aluno):** Inscreve-se em atividades, registra presença via câmera (QR Code) e baixa certificados.

### Gestão de Eventos Inteligente
* **Evento Padrão:** Para congressos ou semanas acadêmicas. Permite múltiplas atividades internas (palestras, minicursos), cada uma com sua própria carga horária e local.
* **Evento Rápido:** Criação expressa para reuniões ou aulas únicas. Gera automaticamente uma atividade de "Check-in Geral" oculta.
* **Controle de Vagas:** Defina limites de participantes ou marque como ilimitado (∞).
* **Validação de Datas:** Bloqueio automático de datas passadas e validação de cronologia (Início < Fim).

### Sistema de Presença Anti-Fraude
* **QR Code Dinâmico:** O código projetado no telão muda seu *hash* criptográfico a cada **30 segundos**. Fotos ou prints antigos não funcionam.
* **Scanner Integrado (Turbo):** O aluno usa a câmera do próprio celular/computador dentro do sistema.
    * *Tecnologia:* Html5QrcodeScanner otimizado para leitura rápida.
    * *Feedback:* Avisos visuais e sonoros de sucesso ou erro.

### Certificação Automática
* **Cálculo de Horas:** O sistema soma apenas as horas das atividades onde o aluno *realmente* esteve presente.
* **PDF Instantâneo:** Geração de certificado profissional usando a biblioteca `ReportLab`.
* **Lógica Inteligente:** Se o evento for "Rápido" (0 horas), o certificado omite a linha de carga horária, servindo apenas como comprovante de presença.

---

## Estrutura do Projeto (MVC)

O projeto foi refatorado para garantir escalabilidade e organização:

```text
/UniEventos
│
├── run.py                  # Ponto de entrada da aplicação
├── config.py               # Configurações globais
├── requirements.txt        # Dependências do Python
│
└── app/
    ├── __init__.py         # Fábrica da Aplicação (App Factory)
    ├── db.py               # Conexão Singleton com SQLite
    │
    ├── models/             # MODEL: Definição e criação das tabelas
    │   └── database.py
    │
    ├── controllers/        # CONTROLLER: Lógica de Negócios (Blueprints)
    │   ├── auth.py         # Login e Registro
    │   ├── admin.py        # Gestão de Usuários
    │   ├── events.py       # CRUD de Eventos
    │   └── participant.py  # Lógica de Presença e Scanner
    │
    └── templates/          # VIEW: Interface Gráfica (HTML/Jinja2)
        ├── base.html       # Layout base (Navbar, Footer, Imports)
        ├── login.html      # Tela de Login/Cadastro
        └── dashboard.html  # Painel Principal (Single Page Application feel)

```

---

## Instalação e Execução

### 1. Pré-requisitos

* Python 3.x instalado.
* Navegador moderno com suporte a câmera (Chrome, Firefox, Safari).

### 2. Instalação

Clone o repositório e instale as dependências:

```bash
# Instalar bibliotecas
pip install -r requirements.txt

```

### 3. Rodando o Sistema

Execute o arquivo principal na raiz do projeto:

```bash
python run.py

```

O sistema estará acessível em: `http://127.0.0.1:5000`

> **Nota:** Ao rodar pela primeira vez, o arquivo `sistema_academico.db` será criado automaticamente com os usuários padrão.

---

## 🔐 Credenciais de Teste

O sistema já vem populado com usuários para facilitar os testes:

| Perfil | Usuário | Senha | Descrição |
| --- | --- | --- | --- |
| **Admin** | `admin` | `admin` | Acesso total ao sistema. |
| **Professor** | `prof` | `1234` | Pode criar eventos e projetar QR Codes. |
| **Aluno** | `aluno` | `1234` | Pode se inscrever e escanear presença. |

---

## Solução de Problemas Comuns

### 1. A câmera não abre no celular

Navegadores modernos bloqueiam o acesso à câmera em sites que não usam **HTTPS**, a menos que seja `localhost`.

* **Solução Local:** Se estiver testando no PC e acessando pelo celular na mesma rede Wi-Fi, a câmera pode não abrir. Use ferramentas como `ngrok` para criar um túnel HTTPS ou teste no próprio PC.
* **Solução Codespaces:** O GitHub Codespaces fornece HTTPS automaticamente, então funciona nativamente.

### 2. Erro de Banco de Dados / Tabela não encontrada

Se você mudou de versão recentemente:

* Pare o servidor (`Ctrl + C`).
* Delete o arquivo `sistema_academico.db`.
* Reinicie o servidor (`python run.py`). O banco será recriado do zero.

---

## Tecnologias Utilizadas

* **Backend:** Python, Flask (Micro-framework).
* **Database:** SQLite (SQL nativo, sem ORM pesado).
* **Frontend:** HTML5, CSS3 (Bootstrap 5), JavaScript (Vanilla).
* **Libs:** `reportlab` (PDF), `qrcode` (Imagem), `html5-qrcode` (Scanner JS).

---

**Desenvolvido para fins educacionais e acadêmicos.**
