import os
import secrets
import hashlib
import base64
import urllib.parse

import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

app = Flask(__name__, template_folder='.')
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable must be set")

USERNAME = os.getenv("APP_USERNAME", "admin")
PASSWORD = os.getenv("APP_PASSWORD", "pass123")

# VK ID OAuth configuration
VK_APP_ID = os.getenv("VK_APP_ID", "")
VK_APP_SECRET = os.getenv("VK_APP_SECRET", "")
VK_SERVICE_TOKEN = os.getenv("VK_SERVICE_TOKEN", "")

# ESIA OAuth configuration
ESIA_CLIENT_ID = os.getenv("ESIA_CLIENT_ID", "")
ESIA_CLIENT_SECRET = os.getenv("ESIA_CLIENT_SECRET", "")
ESIA_REDIRECT_URI = os.getenv("ESIA_REDIRECT_URI", "")
ESIA_AUTH_URL = os.getenv("ESIA_AUTH_URL", "https://esia-portal1.test.gosuslugi.ru/aas/oauth2/ac")

# App origin for OAuth (must be explicitly configured)
APP_ORIGIN = os.getenv("APP_ORIGIN", "")


@app.route("/", methods=["GET"])
def web():
    is_authed = session.get("is_authed", False)
    return render_template("index.html", is_authed=is_authed)


@app.route("/login", methods=["POST"])
def login():
    login_val = request.form.get("login", "")
    password_val = request.form.get("password", "")
    if login_val == USERNAME and password_val == PASSWORD:
        session["is_authed"] = True
        flash("Успешный вход", "success")
        return redirect(url_for("web"))
    flash("Неверный логин или пароль", "error")
    return redirect(url_for("web"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Вы вышли из системы", "info")
    return redirect(url_for("web"))


def generate_code_verifier():
    """Generate a random code_verifier for PKCE."""
    return secrets.token_urlsafe(32)


def generate_code_challenge(code_verifier):
    """Generate code_challenge from code_verifier using S256 method."""
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


@app.route("/oauth/vk/init", methods=["POST"])
def vk_oauth_init():
    """Initialize VK ID OAuth flow and return iframe URL for One Tap Auth."""
    if not VK_APP_ID:
        return jsonify({"success": False, "error": "VK_APP_ID not configured"}), 500

    if not APP_ORIGIN:
        return jsonify({"success": False, "error": "APP_ORIGIN not configured"}), 500

    # Generate PKCE code verifier and challenge
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store code_verifier in session for later token exchange
    session['vk_code_verifier'] = code_verifier

    # Generate unique UUID for this auth request
    uuid = secrets.token_urlsafe(16)
    session['vk_uuid'] = uuid

    # Build VK One Tap Auth iframe URL
    params = {
        'app_id': VK_APP_ID,
        'response_type': 'silent_token',
        'v': '1.61.2',
        'origin': APP_ORIGIN,
        'uuid': uuid,
        'display': 'default',
        'button_skin': 'primary',
        'show_agreements': '1',
        'show_alternative_login': '1',
        'style_height': '50',
        'style_border_radius': '8',
        'lang_id': '0',
        'code_challenge': code_challenge,
        'code_challenge_method': 's256',
    }

    iframe_url = f"https://id.vk.com/button_one_tap_auth?{urllib.parse.urlencode(params)}"

    return jsonify({
        "success": True,
        "iframe_url": iframe_url,
        "uuid": uuid
    })


@app.route("/oauth/vk/exchange", methods=["POST"])
def vk_oauth_exchange():
    """Exchange VK silent_token for access_token and authenticate user."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    silent_token = data.get('token')
    uuid = data.get('uuid')

    if not silent_token:
        return jsonify({"success": False, "error": "No token provided"}), 400

    # Verify UUID matches
    stored_uuid = session.get('vk_uuid')
    if uuid and stored_uuid and uuid != stored_uuid:
        return jsonify({"success": False, "error": "UUID mismatch"}), 400

    # VK_SERVICE_TOKEN is required for secure token exchange
    if not VK_SERVICE_TOKEN:
        return jsonify({"success": False, "error": "VK_SERVICE_TOKEN not configured"}), 500

    # Exchange silent_token for access_token using VK API
    try:
        exchange_response = requests.post(
            'https://api.vk.com/method/auth.exchangeSilentAuthToken',
            data={
                'v': '5.131',
                'token': silent_token,
                'access_token': VK_SERVICE_TOKEN,
                'uuid': uuid or stored_uuid,
            },
            timeout=10
        )
        result = exchange_response.json()

        if 'error' in result:
            return jsonify({
                "success": False,
                "error": result['error'].get('error_msg', 'Token exchange failed')
            }), 400

        # Successfully authenticated
        access_token = result.get('response', {}).get('access_token')
        user_id = result.get('response', {}).get('user_id')

        if access_token:
            session["is_authed"] = True
            session["auth_provider"] = "vk"
            session["vk_user_id"] = user_id
            # Clean up OAuth session data
            session.pop('vk_code_verifier', None)
            session.pop('vk_uuid', None)

            return jsonify({"success": True, "user_id": user_id})

        return jsonify({"success": False, "error": "No access token in response"}), 400

    except requests.RequestException as e:
        return jsonify({"success": False, "error": f"API error: {str(e)}"}), 500


@app.route("/oauth/esia/init", methods=["POST"])
def esia_oauth_init():
    """Initialize ESIA (Gosuslugi) OAuth flow."""
    if not ESIA_CLIENT_ID:
        return jsonify({"success": False, "error": "ESIA not configured"}), 500

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['esia_state'] = state

    # Build ESIA authorization URL
    params = {
        'client_id': ESIA_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': ESIA_REDIRECT_URI or f"{APP_ORIGIN}/oauth/esia/callback",
        'scope': 'openid fullname',
        'state': state,
        'access_type': 'online',
    }

    auth_url = f"{ESIA_AUTH_URL}?{urllib.parse.urlencode(params)}"

    return jsonify({
        "success": True,
        "iframe_url": auth_url,
        "state": state
    })


@app.route("/oauth/esia/callback", methods=["GET"])
def esia_oauth_callback():
    """Handle ESIA OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        flash(f"Ошибка авторизации Госуслуги: {error}", "error")
        return redirect(url_for("web"))

    # Verify state for CSRF protection
    stored_state = session.get('esia_state')
    if not state or state != stored_state:
        flash("Ошибка безопасности: неверный state параметр", "error")
        return redirect(url_for("web"))

    if not code:
        flash("Ошибка: не получен код авторизации", "error")
        return redirect(url_for("web"))

    # ESIA_CLIENT_SECRET is required for secure token exchange
    if not ESIA_CLIENT_SECRET:
        flash("Ошибка: ESIA не полностью настроен", "error")
        return redirect(url_for("web"))

    # Exchange code for access_token
    try:
        token_url = ESIA_AUTH_URL.replace('/ac', '/te')
        token_response = requests.post(
            token_url,
            data={
                'client_id': ESIA_CLIENT_ID,
                'client_secret': ESIA_CLIENT_SECRET,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': ESIA_REDIRECT_URI or f"{APP_ORIGIN}/oauth/esia/callback",
            },
            timeout=10
        )
        result = token_response.json()

        if 'error' in result:
            flash(f"Ошибка обмена токена: {result.get('error_description', 'Unknown error')}", "error")
            return redirect(url_for("web"))

        # Successfully authenticated
        session["is_authed"] = True
        session["auth_provider"] = "esia"
        session.pop('esia_state', None)

        flash("Успешная авторизация через Госуслуги", "success")
        return redirect(url_for("web"))

    except requests.RequestException as e:
        flash(f"Ошибка API: {str(e)}", "error")
        return redirect(url_for("web"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)