
# EuroEventos - Sistema de Gestão Acadêmica

O **EuroEventos** é uma plataforma completa para gerenciamento de eventos acadêmicos, workshops e aulas magnas. O sistema gerencia todo o ciclo de vida do evento: desde a criação e inscrição até o controle de presença via **QR Code Dinâmico** e emissão automática de certificados em PDF.

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

## Estrutura do Projeto

```text
/EuroEventos
│
├── app/                    # App factory, blueprints, models, services e templates
├── migrations/             # Versionamento de schema com Alembic/Flask-Migrate
├── scripts/                # Scripts operacionais, incluindo migração SQLite -> PostgreSQL
├── tutorial/               # Sistema de geração de tutoriais automatizados
├── run.py                  # Ponto de entrada da aplicação Flask
├── config.py               # Configuração por ambiente e URI do banco
├── requirements.txt        # Dependências do Python
└── .env.example            # Exemplo de configuração local
```

---

## Instalação e Execução

### 1. Pré-requisitos

* Python 3.12+
* PostgreSQL local disponível em `localhost:5432`
* Navegador moderno com suporte a câmera (Chrome, Firefox, Safari)

### 2. Instalação

```bash
pip install -r requirements.txt
```

### 3. Configuração local

Crie um arquivo `.env` na raiz do projeto com base em `.env.example`.

Valores esperados para o ambiente local PostgreSQL:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=euro_eventos
DB_USER=postgres
DB_PASSWORD=sua-senha
BASE_URL=http://localhost:5000
```

Se preferir, você pode usar `DATABASE_URL` diretamente:

```env
DATABASE_URL=postgresql+psycopg://postgres:sua-senha@localhost:5432/euro_eventos
```

### 4. Aplicar schema no PostgreSQL

```bash
flask --app run.py db upgrade
```

### 4.1 (Opcional) Bootstrap do PostgreSQL com schema + dados

Este comando aplica migrations e copia os dados do SQLite legado em uma etapa controlada:

```bash
flask --app run.py bootstrap-postgres
```

Para aplicar apenas o schema, use:

```bash
flask --app run.py bootstrap-postgres --skip-data
```

### 5. Seed opcional de usuários locais

```bash
flask --app run.py seed-dev-data
```

### 6. Preparar o cenário canônico do tutorial do participante

O projeto possui um fluxo oficial de tutorial com reset determinístico da base atual. Este comando apaga o schema configurado no ambiente ativo, recria as tabelas e semeia um cenário fixo para geração de screenshots:

```bash
flask --app run.py tutorial-reset --yes
```

O seed oficial cria exatamente:

- 6 usuários, um para cada perfil principal
- 1 curso: `Ciência da Computação`
- 1 evento: `Evento Tutorial do Participante`
- 2 atividades, sendo uma já concluída com certificado emitido e outra pronta para demonstrar inscrição e check-in

### 7. Migrar dados legados do SQLite para PostgreSQL

```bash
python scripts/migrate_sqlite_to_postgres.py --target-uri "postgresql+psycopg://postgres:sua-senha@localhost:5432/euro_eventos"
```

### 8. Rodar a aplicação

```bash
python run.py
```

A aplicação ficará disponível em `http://localhost:5000`.

---

## Credenciais de Teste

Se você usar o seed local, estes usuários serão criados quando ausentes:

| Perfil | Usuário | Senha |
| --- | --- | --- |
| **Admin** | `admin` | `admin` |
| **Coordenador** | `coord` | `1234` |
| **Professor** | `prof` | `1234` |
| **Participante** | `aluno` | `1234` |

## Tutorial Oficial do Participante

O fluxo oficial de documentação automatizada fica em `tutorial/` e é focado apenas no participante/aluno.

### Gerar o tutorial completo

```bash
python tutorial/run_tutorial.py
```

Por padrão, o comando executa:

1. `reset + seed` do cenário canônico
2. Captura determinística das telas do participante
3. Geração de `tutorial/tutorial.md`
4. Escrita das imagens em `tutorial/screenshots/`

Durante depuração, é possível reaproveitar a base já preparada:

```bash
python tutorial/run_tutorial.py --skip-reset
```

### Credenciais do cenário canônico

| Perfil | Usuário | CPF | Senha |
| --- | --- | --- | --- |
| **Admin** | `admin` | `000.000.000-00` | `admin` |
| **Professor** | `prof.ana` | `111.222.333-44` | `1234` |
| **Coordenador** | `coord.marcos` | `555.666.777-88` | `1234` |
| **Extensão** | `extensao` | `222.333.444-55` | `1234` |
| **Gestor** | `gestor` | `999.888.777-66` | `1234` |
| **Participante** | `aluno.demo` | `444.555.666-77` | `1234` |

Os scripts históricos multi-perfil em `tutorial/` foram mantidos apenas como legado e não fazem mais parte do fluxo principal.

---

## Solução de Problemas Comuns

### 1. A câmera não abre no celular

Navegadores modernos bloqueiam o acesso à câmera em sites que não usam **HTTPS**, a menos que seja `localhost`.

* **Solução local:** se estiver acessando pelo celular na mesma rede, use um túnel HTTPS como `ngrok` ou teste diretamente no PC.
* **Solução em ambiente cloud:** use um endpoint HTTPS publicado pelo ambiente.

### 2. Erro de schema / tabela não encontrada

Garanta que as migrations foram aplicadas:

```bash
flask --app run.py db upgrade
```

### 3. Migração de dados falhando por legado inconsistente

O script `scripts/migrate_sqlite_to_postgres.py` cria placeholders para referências órfãs em usuários e responsáveis por eventos, o que permite concluir a migração mesmo quando o SQLite contém dados inconsistentes.

---

## Tecnologias Utilizadas

* **Backend:** Python, Flask, Flask-SQLAlchemy, Flask-Migrate
* **Database:** PostgreSQL
* **Frontend:** HTML5, CSS3 (Bootstrap 5), JavaScript
* **Libs principais:** `reportlab`, `qrcode`, `psycopg`

---

**Desenvolvido para fins educacionais e acadêmicos.**
