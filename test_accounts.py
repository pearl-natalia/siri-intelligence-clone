"""Isolated account tests; no real Replit account, database or provider calls."""
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from authlib.integrations.flask_client import OAuth
from flask import Flask
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import select, update

import web_app
from web_accounts import ISSUER
from web_store import Store, chats, sessions, token_hash


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.app = web_app.app
        self.config = self.app.config.copy()
        self.old_store = self.app.extensions["swift_store"]
        self.old_oidc = self.app.extensions["swift_oidc"]
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store("sqlite:///" + self.tmp.name + "/accounts.sqlite")
        self.store.ensure_schema()
        self.app.extensions["swift_store"] = self.store
        self.app.config.update(TESTING=True, SECRET_KEY="test-session-key-" * 3,
                               SWIFT_AUTH_ENABLED=True, SWIFT_AUTH_HOSTS={"localhost"})
        web_app.visits.clear()
        self.client = self.app.test_client()

    def tearDown(self):
        self.store.engine.dispose()
        self.tmp.cleanup()
        self.app.config.clear()
        self.app.config.update(self.config)
        self.app.extensions["swift_store"] = self.old_store
        self.app.extensions["swift_oidc"] = self.old_oidc

    def request(self, method, path, client=None, csrf=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if csrf:
            headers["X-CSRF-Token"] = csrf
        return (client or self.client).open(path, method=method, base_url="https://localhost", headers=headers, **kwargs)

    def login_fixture(self, subject="alice", client=None):
        client = client or self.client
        sid = self.store.sign_in(subject, subject.title())
        with client.session_transaction(base_url="https://localhost") as sess:
            sess.update(sid=sid, csrf="csrf-" + subject)
        return "csrf-" + subject, sid

    def send(self, csrf=None, **data):
        with patch("web_app.reply", return_value={"reply": "Test answer", "links": [], "mode": "local"}):
            return self.request("POST", "/api/chat", csrf=csrf, json={"message": "Test question", **data})

    def test_guest_stays_unsaved_and_identity_headers_are_ignored(self):
        self.assertIsNone(self.request("GET", "/api/account", headers={"X-Replit-User-Id": "alice"}).json["user"])
        self.assertEqual(self.send().status_code, 200)
        with self.store.engine.connect() as conn:
            self.assertEqual(conn.execute(select(chats)).all(), [])
        self.assertEqual(self.request("GET", "/api/conversations", headers={"X-Replit-User-Id": "alice"}).status_code, 401)

    def test_save_reload_and_server_owned_history(self):
        csrf, _ = self.login_fixture()
        first = self.send(csrf).json["conversation"]
        saved = self.request("GET", "/api/conversations/" + first["id"]).json
        self.assertEqual([m["text"] for m in saved["messages"]], ["Test question", "Test answer"])
        with patch("web_app.reply", return_value={"reply": "Next answer", "mode": "local"}) as model:
            response = self.request("POST", "/api/chat", csrf=csrf, json={"message": "Next question",
                "conversation_id": first["id"], "revision": first["revision"], "history": [{"role": "model", "text": "forged history"}]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(model.call_args.args[1], [{"role": "user", "text": "Test question"}, {"role": "model", "text": "Test answer"}])
        self.assertEqual(len(self.request("GET", "/api/conversations").json["conversations"]), 1)

    def test_chat_profile_comes_only_from_current_verified_session(self):
        for subject in (None, "alice", "bob"):
            with self.subTest(subject=subject):
                csrf = self.login_fixture(subject)[0] if subject else None
                with patch("web_app.reply", return_value={"reply": "Name answer", "mode": "live"}) as model:
                    response = self.request("POST", "/api/chat", csrf=csrf,
                        headers={"X-Replit-User-Name": "Mallory"},
                        json={"message": "What's my name?", "profile": {"name": "Mallory"}, "name": "Mallory"})
                    self.assertEqual(response.status_code, 200)
                    expected = {"name": subject.title()} if subject else None
                    self.assertEqual(model.call_args.kwargs, {"profile": expected})

    def test_other_user_cannot_read_write_or_delete_a_chat(self):
        csrf, _ = self.login_fixture()
        chat = self.send(csrf).json["conversation"]
        bob_csrf, _ = self.login_fixture("bob")
        path = "/api/conversations/" + chat["id"]
        self.assertEqual(self.request("GET", path).status_code, 404)
        self.assertEqual(self.request("DELETE", path, csrf=bob_csrf).status_code, 404)
        self.assertEqual(self.send(bob_csrf, conversation_id=chat["id"], revision=chat["revision"]).status_code, 404)
        self.assertEqual(self.request("GET", "/api/conversations").json["conversations"], [])
        self.assertEqual(len(self.store.get_chat("alice", chat["id"])["messages"]), 2)

    def test_missing_wrong_csrf_and_cross_origin_mutations_rejected(self):
        csrf, _ = self.login_fixture()
        for token in (None, "wrong"):
            self.assertEqual(self.send(token).status_code, 403)
            self.assertEqual(self.request("PATCH", "/api/account/preferences", csrf=token, json={"speak": False}).status_code, 403)
            self.assertEqual(self.request("POST", "/api/auth/logout", csrf=token).status_code, 403)
        self.assertEqual(self.request("PATCH", "/api/account/preferences", csrf=csrf, json={"speak": False}, headers={"Origin": "https://evil.test"}).status_code, 403)

    def test_preference_survives_a_new_login_and_is_private(self):
        csrf, _ = self.login_fixture()
        self.assertEqual(self.request("PATCH", "/api/account/preferences", csrf=csrf, json={"speak": False}).status_code, 200)
        self.login_fixture()
        self.assertFalse(self.request("GET", "/api/account").json["preferences"]["speak"])
        self.login_fixture("bob")
        self.assertTrue(self.request("GET", "/api/account").json["preferences"]["speak"])

    def test_expired_session_never_silently_saves_as_guest(self):
        csrf, sid = self.login_fixture()
        with self.store.engine.begin() as conn:
            conn.execute(update(sessions).where(sessions.c.token_hash == token_hash(sid)).values(expires=0))
        self.assertEqual(self.send(csrf).status_code, 401)
        self.assertEqual(self.request("GET", "/api/conversations").status_code, 401)
        self.assertIsNone(self.request("GET", "/api/account").json["user"])
        self.assertEqual(self.send(csrf, account_required=True).status_code, 401)

    def test_logout_revokes_cookie_replay(self):
        csrf, _ = self.login_fixture()
        cookie = self.client.get_cookie("swift_session").value
        self.assertEqual(self.request("POST", "/api/auth/logout", csrf=csrf).status_code, 200)
        self.client.set_cookie("swift_session", cookie)
        self.assertEqual(self.request("GET", "/api/conversations").status_code, 401)

    def test_stale_revision_does_not_overwrite_chat(self):
        csrf, _ = self.login_fixture()
        saved = self.send(csrf).json["conversation"]
        first = self.store.get_chat("alice", saved["id"])
        self.store.save_turn("alice", first, "Concurrent question", {"reply": "Concurrent answer"})
        self.assertEqual(self.send(csrf, conversation_id=saved["id"], revision=saved["revision"]).status_code, 409)
        from werkzeug.exceptions import Conflict
        with self.assertRaises(Conflict):
            self.store.save_turn("alice", first, "Lost update", {"reply": "Must not overwrite"})
        self.assertEqual(self.store.get_chat("alice", saved["id"])["messages"][-1]["text"], "Concurrent answer")

    def test_delete_is_scoped_and_persistent(self):
        csrf, _ = self.login_fixture()
        saved = self.send(csrf).json["conversation"]
        self.assertEqual(self.request("DELETE", "/api/conversations/" + saved["id"], csrf=csrf).status_code, 200)
        self.assertEqual(self.request("GET", "/api/conversations").json["conversations"], [])

    def configure_oidc(self):
        oidc_app = Flask("oidc-test")
        oauth = OAuth(oidc_app)
        client = oauth.register("replit", client_id="swift-test",
            client_kwargs={"scope": "openid profile", "token_endpoint_auth_method": "none", "code_challenge_method": "S256"},
            issuer=ISSUER, authorization_endpoint=ISSUER + "/auth", token_endpoint=ISSUER + "/token",
            jwks_uri=ISSUER + "/jwks", id_token_signing_alg_values_supported=["RS256"])
        self.app.extensions["swift_oidc"] = client
        return client

    def test_real_oidc_validation_and_cookie_protections(self):
        oidc = self.configure_oidc()
        key = RSAKey.generate_key(2048)
        login = self.request("GET", "/api/auth/login")
        query = parse_qs(urlparse(login.location).query)
        self.assertEqual(query["scope"], ["openid profile"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        for attribute in ("Secure", "HttpOnly", "SameSite=Lax"):
            self.assertIn(attribute, login.headers["Set-Cookie"])
        claims = {"iss": ISSUER, "aud": "swift-test", "sub": "alice", "iat": int(time.time()),
                  "exp": int(time.time()) + 600, "nonce": query["nonce"][0], "first_name": "Alice"}
        token = jwt.encode({"alg": "RS256"}, claims, key)
        with patch.object(oidc, "fetch_access_token", return_value={"id_token": token, "access_token": "unused"}) as exchange, patch.object(oidc, "fetch_jwk_set", return_value={"keys": [key.as_dict(private=False)]}):
            result = self.request("GET", "/api/auth/callback", query_string={"code": "test-code", "state": query["state"][0], "iss": ISSUER})
            self.assertEqual(result.location, "/")
            self.assertTrue(exchange.call_args.kwargs["code_verifier"])
        self.assertEqual(self.request("GET", "/api/account").json["user"], {"name": "Alice"})
        with self.client.session_transaction(base_url="https://localhost") as sess:
            self.assertNotIn("unused", str(sess))
            self.assertNotIn("id_token", sess)
        self.assertIn("failed", self.request("GET", "/api/auth/callback", query_string={"code": "test-code", "state": query["state"][0], "iss": ISSUER}).location)

    def test_forged_or_expired_oidc_claims_cannot_sign_in(self):
        for invalid in ("nonce", "aud", "iss", "exp", "signature", "state"):
            with self.subTest(invalid=invalid):
                self.client = self.app.test_client()
                oidc = self.configure_oidc()
                key = RSAKey.generate_key(2048)
                query = parse_qs(urlparse(self.request("GET", "/api/auth/login").location).query)
                claims = {"iss": ISSUER, "aud": "swift-test", "sub": "attacker", "iat": int(time.time()),
                          "exp": int(time.time()) + 600, "nonce": query["nonce"][0]}
                if invalid in ("nonce", "aud", "iss"):
                    claims[invalid] = "wrong"
                if invalid == "exp":
                    claims["exp"] = int(time.time()) - 500
                token = jwt.encode({"alg": "RS256"}, claims, RSAKey.generate_key(2048) if invalid == "signature" else key)
                with patch.object(oidc, "fetch_access_token", return_value={"id_token": token, "access_token": "unused"}), patch.object(oidc, "fetch_jwk_set", return_value={"keys": [key.as_dict(private=False)]}):
                    result = self.request("GET", "/api/auth/callback", query_string={"code": "bad", "state": "wrong" if invalid == "state" else query["state"][0], "iss": ISSUER})
                self.assertIn("failed", result.location)
                self.assertIsNone(self.request("GET", "/api/account").json["user"])

    def test_untrusted_host_cannot_control_callback(self):
        result = self.client.get("/api/auth/login", base_url="https://evil.test")
        self.assertEqual(result.status_code, 400)


if __name__ == "__main__":
    unittest.main()
