from flask import Blueprint, request, jsonify, redirect, current_app, url_for
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app.utils import normalize_cpf

bp = Blueprint('auth', __name__, url_prefix='/api')
auth_service = AuthService()

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    login_value = data.get('cpf') or data.get('login') or data.get('username')
    password = data.get('password')
    
    user = auth_service.authenticate_user(login_value, password)
    
    if user:
        login_user(user)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Dados inválidos"}), 401

@bp.route('/registrar', methods=['POST'])
def registrar():
    data = request.json
    try:
        auth_service.register_user(data)
        return jsonify({"mensagem": "Cadastrado!"})
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": "Erro interno"}), 500

@bp.route('/logout')
def logout():
    logout_user()
    return redirect('/')


@bp.route('/ava')
def ava_login_redirect():
    """Redirects users to Moodle AVA login/launch URL."""
    if not current_app.config.get('MOODLE_LOGIN_ENABLED'):
        return jsonify({'status': 'error', 'message': 'Login AVA desativado.'}), 404

    moodle_url = (current_app.config.get('MOODLE_LOGIN_URL') or '').strip()
    if not moodle_url:
        return jsonify({'status': 'error', 'message': 'MOODLE_LOGIN_URL não configurado.'}), 500

    return redirect(moodle_url)


@bp.route('/ava/launch', methods=['GET', 'POST'])
def ava_launch_login():
    """Receives Moodle external tool launch and authenticates user by CPF."""
    if not current_app.config.get('MOODLE_LOGIN_ENABLED'):
        return jsonify({'status': 'error', 'message': 'Login AVA desativado.'}), 404

    if request.method == 'GET':
        query = request.args or {}
        is_lti13_registration = bool(query.get('openid_configuration') or query.get('registration_token'))

        if is_lti13_registration:
            return jsonify({
                'status': 'error',
                'message': (
                    'Fluxo LTI 1.3 (OIDC/dynamic registration) detectado. '
                    'Esta integracao usa LTI 1.0/1.1 com launch por POST. '
                    'No Moodle, configure a Ferramenta Externa para enviar launch em POST '
                    'para /api/ava/launch e envie o CPF no campo username (ou no campo configurado em MOODLE_CPF_FIELD).'
                ),
                'hint': 'Use /api/ava para iniciar pelo botao Entrar com o AVA no UniEventos.'
            }), 400

        return redirect(url_for('main.index'))

    payload = request.form or request.json or {}
    cpf_field = (current_app.config.get('MOODLE_CPF_FIELD') or 'custom_cpf').strip()

    cpf_raw = (
        payload.get(cpf_field)
        or payload.get('username')
        or payload.get('ext_user_username')
        or payload.get('custom_cpf')
        or payload.get('cpf')
        or payload.get('lis_person_sourcedid')
        or payload.get('user_id')
    )
    cpf = normalize_cpf(cpf_raw)

    if not cpf:
        return jsonify({'status': 'error', 'message': 'CPF não recebido do AVA.'}), 400

    email = (payload.get('lis_person_contact_email_primary') or payload.get('email') or '').strip().lower()
    allowed_domain = (current_app.config.get('MOODLE_ALLOWED_EMAIL_DOMAIN') or '').strip().lower()

    expected_consumer_key = (current_app.config.get('MOODLE_TOOL_CONSUMER_KEY') or '').strip()
    received_consumer_key = (
        payload.get('oauth_consumer_key')
        or payload.get('custom_oauth_consumer_key')
        or ''
    ).strip()

    if expected_consumer_key:
        if not received_consumer_key:
            return jsonify({
                'status': 'error',
                'message': 'oauth_consumer_key ausente no launch LTI.'
            }), 403
        if received_consumer_key != expected_consumer_key:
            return jsonify({'status': 'error', 'message': 'Consumer key da ferramenta externa inválido.'}), 403

    # Legacy/fallback validation for custom shared secret mode.
    shared_secret = (current_app.config.get('MOODLE_TOOL_SHARED_SECRET') or '').strip()
    if shared_secret and not expected_consumer_key:
        received_secret = (
            payload.get('custom_ava_secret')
            or payload.get('ava_secret')
            or received_consumer_key
            or ''
        ).strip()
        if not received_secret:
            return jsonify({
                'status': 'error',
                'message': 'Credencial da ferramenta externa ausente no launch (custom_ava_secret/oauth_consumer_key).'
            }), 403
        if received_secret != shared_secret:
            return jsonify({'status': 'error', 'message': 'Assinatura da ferramenta externa inválida.'}), 403

    nome = (
        payload.get('lis_person_name_full')
        or payload.get('name')
        or f"{payload.get('lis_person_name_given', '').strip()} {payload.get('lis_person_name_family', '').strip()}".strip()
    )

    user = auth_service.authenticate_or_provision_from_moodle(cpf=cpf, nome=nome, email=email)
    if not user:
        return jsonify({'status': 'error', 'message': 'Não foi possível autenticar via AVA.'}), 401

    login_user(user)
    return redirect(url_for('main.index'))


@bp.route('/ava/direct', methods=['POST'])
def ava_direct_login():
    """Direct login for community members when LTI activity is hidden/unavailable."""
    if not current_app.config.get('MOODLE_LOGIN_ENABLED'):
        return jsonify({'status': 'error', 'message': 'Login AVA desativado.'}), 404

    payload = request.form or request.json or {}
    cpf_field = (current_app.config.get('MOODLE_CPF_FIELD') or 'custom_cpf').strip()

    cpf_raw = (
        payload.get(cpf_field)
        or payload.get('username')
        or payload.get('ext_user_username')
        or payload.get('custom_cpf')
        or payload.get('cpf')
        or payload.get('lis_person_sourcedid')
        or payload.get('user_id')
    )
    cpf = normalize_cpf(cpf_raw)

    if not cpf:
        return jsonify({'status': 'error', 'message': 'CPF não recebido.'}), 400

    email = (payload.get('lis_person_contact_email_primary') or payload.get('email') or '').strip().lower()
    allowed_domain = (current_app.config.get('MOODLE_ALLOWED_EMAIL_DOMAIN') or '').strip().lower()

    if allowed_domain:
        if not email or not email.endswith(f'@{allowed_domain}'):
            return jsonify({'status': 'error', 'message': 'Acesso restrito à comunidade acadêmica Unieuro.'}), 403

    nome = (
        payload.get('lis_person_name_full')
        or payload.get('name')
        or f"{payload.get('lis_person_name_given', '').strip()} {payload.get('lis_person_name_family', '').strip()}".strip()
    )

    user = auth_service.authenticate_or_provision_from_moodle(cpf=cpf, nome=nome, email=email)
    if not user:
        return jsonify({'status': 'error', 'message': 'Não foi possível autenticar via AVA.'}), 401

    login_user(user)
    return redirect(url_for('main.index'))


@bp.route('/password/forgot', methods=['POST'])
def password_forgot():
    data = request.json or {}
    email = data.get('email')

    # Prevent account enumeration by always returning success response.
    auth_service.request_password_reset(email)
    return jsonify({
        'mensagem': 'Se o e-mail estiver cadastrado, enviaremos as instruções de recuperação.'
    })


@bp.route('/password/reset', methods=['POST'])
def password_reset():
    data = request.json or {}
    token = data.get('token')
    new_password = data.get('password')

    success, msg = auth_service.reset_password_with_token(token, new_password)
    if success:
        return jsonify({'mensagem': msg})
    return jsonify({'erro': msg}), 400


@bp.route('/me/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.json or {}
    success, msg = auth_service.update_profile(
        current_user,
        data.get('nome'),
        data.get('email'),
    )
    if success:
        return jsonify({'mensagem': msg, 'nome': current_user.nome, 'email': current_user.email})
    return jsonify({'erro': msg}), 400


@bp.route('/me/password', methods=['PUT'])
@login_required
def change_password():
    data = request.json or {}
    success, msg = auth_service.change_password(
        current_user,
        data.get('current_password'),
        data.get('new_password'),
    )
    if success:
        return jsonify({'mensagem': msg})
    return jsonify({'erro': msg}), 400
