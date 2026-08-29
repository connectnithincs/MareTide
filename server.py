from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import timedelta
import uuid
import time
import os

app = Flask(__name__)

# Secret key for signing session cookies (production apps should use environment variables)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "maretide-secret-stability-key-2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# Memory store for active, single-use login tokens
# Structure: { token: { "user": email, "expires": expiration_timestamp } }
valid_tokens = {}

# Configuration flag for automatic login
# False = always display landing page first (Development Mode)
# True = preserve active session and auto-login to dashboard (Production Mode)
AUTO_LOGIN_IF_SESSION_EXISTS = False

# Authorized credentials list
CREDENTIALS = {
    "admin@maretide.com": "password123",
    "XXX": "1234",
    "admin": "admin"
}

@app.route('/')
def index():
    if request.headers.get("User-Agent") == "MareTide Poller":
        return "Flask Auth Server Ready"
    # Bypass login screen: immediately log in and redirect to React dashboard
    token = str(uuid.uuid4())
    valid_tokens[token] = {
        "user": "admin@maretide.com",
        "expires": time.time() + 60
    }
    session['user'] = "admin@maretide.com"
    return redirect(f"http://localhost:3000/?token={token}")

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    # Credentials validation
    if email in CREDENTIALS and CREDENTIALS[email] == password:
        session.permanent = True
        session['user'] = email

        # Generate a single-use token for the Streamlit dashboard redirect
        token = str(uuid.uuid4())
        valid_tokens[token] = {
            "user": email,
            "expires": time.time() + 60
        }
        
        return jsonify({
            "success": True,
            "redirect": f"http://localhost:3000/?token={token}"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Credentials not recognised. Please try again."
        }), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- API Endpoints for Streamlit Handshake ---

@app.route('/api/validate_token')
def validate_token():
    token = request.args.get('token')
    if not token:
        return jsonify({"valid": False, "message": "Token parameter missing"}), 400

    token_data = valid_tokens.get(token)
    if token_data:
        # Check token expiration
        if time.time() <= token_data['expires']:
            # Single-use: remove after validation
            del valid_tokens[token]
            return jsonify({
                "valid": True,
                "user": token_data['user']
            })
        else:
            del valid_tokens[token]
            return jsonify({"valid": False, "message": "Token expired"}), 401
    
    return jsonify({"valid": False, "message": "Invalid token"}), 401

@app.route('/api/check_session')
def check_session():
    # Streamlit forwards the Cookie header, allowing Flask to decrypt the session
    if 'user' in session:
        return jsonify({
            "authenticated": True,
            "user": session['user']
        })
    return jsonify({"authenticated": False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
