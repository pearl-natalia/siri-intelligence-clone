"""Replit OpenID Connect login; all account APIs use a verified server session."""
import os
import secrets
import time
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import current_app, g, jsonify, redirect, request, session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, Forbidden, Unauthorized
from web_store import Store

ISSUER = "https://replit.com/oidc"
PUBLIC_HOST = "siri-intelligence-clone--pearlnatalia.replit.app"


def init_accounts(app):
    secret = os.getenv("SESSION_SECRET", "")
    database = os.getenv("DATABASE_URL", "")
    client_id = os.getenv("REPL_ID", "")
    app.config.update(SECRET_KEY=secret or None, SESSION_COOKIE_NAME="swift_session",
                      SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(days=1))
    app.config["SWIFT_AUTH_ENABLED"] = bool(database and client_id and len(secret) >= 32)
    app.config["SWIFT_AUTH_HOSTS"] = {PUBLIC_HOST} | {
        host.strip() for host in (os.getenv("REPLIT_DOMAINS", "") + "," + os.getenv("REPLIT_DEV_DOMAIN", "")).split(",") if host.strip()}
    app.extensions["swift_store"] = Store(database) if app.config["SWIFT_AUTH_ENABLED"] else None
    oauth = OAuth(app)
    app.extensions["swift_oidc"] = oauth.register("replit", client_id=client_id,
        server_metadata_url=ISSUER + "/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile", "token_endpoint_auth_method": "none", "code_challenge_method": "S256", "timeout": 15})

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        app.logger.warning("Account storage unavailable (%s)", type(error).__name__)
        return jsonify(error="Saved chats are temporarily unavailable. Please try again shortly."), 503

    @app.get("/api/account")
    def account():
        if not enabled():
            return jsonify(enabled=False, user=None)
        store().ensure_schema()
        user = current_user()
        if not user:
            session.pop("sid", None)
        session.setdefault("csrf", secrets.token_urlsafe(32))
        return jsonify(enabled=True, user={"name": user["name"]} if user else None,
                       preferences={"speak": user["speak"]} if user else None, csrf=session["csrf"])

    @app.get("/api/auth/login")
    def login():
        if not enabled():
            return redirect("/?signin=unavailable")
        if request.host not in app.config["SWIFT_AUTH_HOSTS"]:
            raise BadRequest("Sign in from Swift's published page or Replit preview.")
        store().ensure_schema()
        # Fixed scheme and allowlisted host, never forwarded-host input.
        callback = "https://" + request.host + "/api/auth/callback"
        session["login_started"] = time.time()
        try:
            return app.extensions["swift_oidc"].authorize_redirect(callback)
        except Exception as error:
            app.logger.warning("Sign-in start failed (%s)", type(error).__name__)
            return redirect("/?signin=unavailable")

    @app.get("/api/auth/callback")
    def callback():
        if not enabled() or request.host not in app.config["SWIFT_AUTH_HOSTS"]:
            raise BadRequest("Sign-in is unavailable here.")
        try:
            started = session.pop("login_started", 0)
            if not 0 <= time.time() - started < 600 or request.args.get("iss") != ISSUER:
                raise ValueError("Expired login or wrong issuer")
            # Authlib checks state, nonce, PKCE, token signature, issuer and audience.
            token = app.extensions["swift_oidc"].authorize_access_token()
            claims = token["userinfo"]
            subject = claims.get("sub")
            if not isinstance(subject, str) or not subject or len(subject) > 255:
                raise ValueError("Missing subject")
            name = claims.get("first_name") or claims.get("username") or "Your account"
            if not isinstance(name, str):
                name = "Your account"
            if session.get("sid"):
                store().sign_out(session["sid"])
            sid = store().sign_in(subject, name[:100])
            session.clear()
            session.permanent = True
            session.update(sid=sid, csrf=secrets.token_urlsafe(32))
            # Provider tokens are deliberately discarded: Swift needs only identity.
            return redirect("/")
        except Exception as error:
            app.logger.warning("Sign-in callback failed (%s)", type(error).__name__)
            for key in list(session):
                if key.startswith("_state_replit_"):
                    session.pop(key, None)
            return redirect("/?signin=failed")

    @app.post("/api/auth/logout")
    def logout():
        check_csrf()
        if enabled() and session.get("sid"):
            store().sign_out(session["sid"])
        session.clear()
        return jsonify(ok=True)

    @app.patch("/api/account/preferences")
    @account_required
    def preferences():
        check_csrf()
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("speak")) is not bool:
            raise BadRequest("Choose whether Swift should speak replies.")
        store().preferences(g.swift_user["id"], data["speak"])
        return jsonify(speak=data["speak"])

    @app.get("/api/conversations")
    @account_required
    def conversations():
        return jsonify(conversations=store().list_chats(g.swift_user["id"]))

    @app.get("/api/memory")
    @account_required
    def memory():
        return jsonify(enabled=store().memory_enabled(g.swift_user["id"]), facts=store().list_memories(g.swift_user["id"]))

    @app.patch("/api/memory")
    @account_required
    def memory_preference():
        check_csrf()
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("enabled")) is not bool:
            raise BadRequest("Choose whether Swift should remember facts.")
        store().set_memory_enabled(g.swift_user["id"], data["enabled"])
        return jsonify(enabled=data["enabled"])

    @app.delete("/api/memory/<fact_id>")
    @account_required
    def forget_memory(fact_id):
        check_csrf()
        store().forget(g.swift_user["id"], fact_id)
        return jsonify(ok=True)

    @app.get("/api/conversations/<chat_id>")
    @account_required
    def conversation(chat_id):
        return jsonify(store().get_chat(g.swift_user["id"], chat_id))

    @app.delete("/api/conversations/<chat_id>")
    @account_required
    def delete_conversation(chat_id):
        check_csrf()
        store().delete_chat(g.swift_user["id"], chat_id)
        return jsonify(ok=True)


def enabled():
    return current_app.config["SWIFT_AUTH_ENABLED"]


def store():
    return current_app.extensions["swift_store"]


def current_user():
    if not enabled() or not session.get("sid"):
        return None
    if "swift_user" not in g:
        g.swift_user = store().user_for_session(session["sid"])
    return g.swift_user


def account_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            raise Unauthorized("Sign in again to access saved chats.")
        return fn(*args, **kwargs)
    return wrapped


def check_csrf():
    expected = session.get("csrf")
    supplied = request.headers.get("X-CSRF-Token", "")
    origin = request.headers.get("Origin")
    scheme = "https" if current_app.config["SESSION_COOKIE_SECURE"] else request.scheme
    if (not expected or not secrets.compare_digest(expected, supplied)
            or (origin and (urlparse(origin).scheme != scheme or urlparse(origin).netloc != request.host))):
        raise Forbidden("Refresh Swift before trying again.")


def chat_context(data):
    """Reject expired authenticated requests instead of silently making them guest chats."""
    user = current_user()
    if not user:
        if session.get("sid") or data.get("account_required") or data.get("conversation_id"):
            raise Unauthorized("Your session ended. Sign in again to continue this chat.")
        return None, None
    check_csrf()
    previous = None
    chat_id = data.get("conversation_id")
    if chat_id is not None:
        if not isinstance(chat_id, str) or len(chat_id) > 36:
            raise BadRequest("Invalid conversation.")
        previous = store().get_chat(user["id"], chat_id)
        if data.get("revision") != previous["revision"]:
            from werkzeug.exceptions import Conflict
            raise Conflict("This chat changed in another tab. Reload it before sending again.")
        if len(previous["messages"]) >= 200:
            from werkzeug.exceptions import Conflict
            raise Conflict("This conversation is full. Start a new chat.")
    return user, previous
