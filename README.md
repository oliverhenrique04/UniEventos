# UniEventos - Sistema de Gestão Acadêmica

Sistema completo para gerenciamento de eventos acadêmicos, controle de frequência via QR Code dinâmico e emissão automática de certificados.

## 🚀 Funcionalidades Principais

### 1. Hierarquia de Usuários
* *Admin:* Acesso total. Pode editar dados de qualquer usuário e promover participantes a professores ou coordenadores.
* **Coordenador:** Pode gerenciar eventos e visualizar usuários.
* **Professor:** Pode criar e gerenciar seus próprios eventos e atividades.
* **Participante (Aluno):** Pode se inscrever em atividades, escanear presença e baixar certificados.

### 2. Gestão de Eventos e Atividades
* **Evento Padrão:** Permite criar múltiplas atividades internas (palestras, workshops), cada uma com sua data, horário, local, palestrante e carga horária específica.
* **Evento Rápido (⚡):** Criação simplificada para lista de presença única. Gera automaticamente uma atividade oculta de check-in sem carga horária (ideal para reuniões ou aulas rápidas).
* **Controle de Vagas:** Opção para limitar a quantidade de inscritos por atividade ou deixar ilimitado (∞).
* **Validação de Datas:** O sistema impede a criação de eventos com datas no passado ou datas de fim anteriores ao início.

### 3. Sistema de Presença Anti-Fraude
* **QR Code Dinâmico:** O código projetado no telão muda a cada 30 segundos.
* **Validação de Token:** O link contido no QR Code possui um hash criptografado vinculado ao tempo. Um aluno não pode tirar foto do código e enviar para um colega que está em casa, pois o código expira rapidamente.
* **Scanner Integrado:** O sistema possui um leitor de QR Code embutido na interface do aluno (usa a câmera do celular), sem necessidade de apps externos.

### 4. Certificação e Relatórios
* **Cálculo de Horas:** O certificado soma automaticamente apenas a carga horária das atividades onde o aluno teve presença confirmada.
* **Certificado PDF:** Gerado instantaneamente com layout profissional usando a biblioteca `ReportLab`.
* **Relatório de Gestão:** O criador do evento pode visualizar a lista de inscritos e quem estava presente/ausente em tempo real.

---

## 🛠️ Instalação e Execução

1.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Execute a aplicação:**
    ```bash
    python app.py
    ```

3.  **Acesse no navegador:**
    * O sistema rodará em: `http://127.0.0.1:5000`
    * **Nota:** Para testar o Scanner em celulares na mesma rede, você precisará servir a aplicação via HTTPS ou usar o IP da máquina local (ex: `http://192.168.0.X:5000`), mas navegadores mobile podem bloquear a câmera se não houver HTTPS seguro.

### 🔐 Usuários Padrão (Para Teste)
O banco de dados é criado automaticamente com estes usuários na primeira execução:

| Usuário | Senha | Perfil |
| :--- | :--- | :--- |
| `admin` | `admin` | **Admin** |
| `prof` | `1234` | **Professor** |
| `aluno` | `1234` | **Participante** |

---

## 🗄️ Estrutura do Banco de Dados (SQLite)

O sistema utiliza o SQLite (`sistema_academico.db`), que é gerado automaticamente pelo arquivo `app.py`. Não é necessário instalar nenhum servidor de banco de dados.

### Tabelas e Relacionamentos

1.  **`users`**
    * Armazena as credenciais e dados pessoais.
    * Campos: `username` (PK), `password`, `role` (cargo), `nome`, `cpf`.

2.  **`events`**
    * Representa o "guarda-chuva" do evento (ex: "Semana da Tecnologia").
    * Campos: `id`, `owner` (quem criou), `nome`, `descricao`, `tipo` (PADRAO/RAPIDO), datas e horários globais.

3.  **`activities`** (O Coração do Sistema)
    * Representa o que acontece dentro do evento. É aqui que a presença é registrada.
    * **Relacionamento:** Vinculada a um `event_id`.
    * Campos:
        * `nome`, `palestrante`, `local`, `descricao`.
        * `data_atv`, `hora_atv`: Agenda específica daquela atividade.
        * `carga_horaria`: Horas que somam no certificado.
        * `vagas`: Quantidade limite (ou -1 para infinito).

4.  **`activity_enrollments`** (Tabela Pivô)
    * Registra a relação entre um **Aluno** e uma **Atividade**.
    * Campos:
        * `activity_id`: Qual atividade ele se inscreveu.
        * `event_id`: Para facilitar buscas.
        * `cpf`: Identificador do aluno.
        * `presente`: `0` (Inscrito) ou `1` (Confirmou Presença via QR Code).

---

## 🔒 Segurança do Token QR Code

A lógica de geração do QR Code segue este padrão para evitar fraudes:

```python
# Pseudo-código da lógica
timestamp = tempo_atual_segundos / 30  # Janela de 30s
token_bruto = f"{ID_ATIVIDADE}:{timestamp}:{CHAVE_SECRETA_DO_APP}"
hash_final = sha256(token_bruto)