"""Account-scoped browser storage. Native Mac memory remains local to the Mac."""
import hashlib
import secrets
import time
from threading import Lock
from uuid import uuid4

from sqlalchemy import (JSON, Boolean, Column, Float, ForeignKey, Integer, MetaData,
                        String, Table, UniqueConstraint, create_engine, delete, insert, select, update)
from sqlalchemy.engine import make_url
from werkzeug.exceptions import Conflict, NotFound, TooManyRequests

metadata = MetaData()
users = Table("swift_web_users", metadata,
    Column("id", String(255), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("speak", Boolean, nullable=False, default=True))
sessions = Table("swift_web_sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", ForeignKey(users.c.id), nullable=False, index=True),
    Column("expires", Float, nullable=False, index=True))
chats = Table("swift_web_chats", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", ForeignKey(users.c.id), nullable=False, index=True),
    Column("title", String(80), nullable=False),
    Column("messages", JSON, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("updated", Float, nullable=False))
memories = Table("swift_web_memories", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", ForeignKey(users.c.id), nullable=False, index=True),
    Column("topic", String(80), nullable=False),
    Column("fact", String(500), nullable=False),
    Column("updated", Float, nullable=False),
    UniqueConstraint("user_id", "topic", name="swift_memory_user_topic"))
memory_settings = Table("swift_web_memory_settings", metadata,
    Column("user_id", ForeignKey(users.c.id), primary_key=True),
    Column("enabled", Boolean, nullable=False))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, database_url):
        url = make_url(database_url)
        if url.drivername in ("postgres", "postgresql"):
            url = url.set(drivername="postgresql+psycopg")
        options = {"connect_args": {"connect_timeout": 8}} if url.get_backend_name() == "postgresql" else {}
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, **options)
        self._ready = False
        self._lock = Lock()

    def ensure_schema(self):
        with self._lock:
            if not self._ready:
                metadata.create_all(self.engine)
                self._ready = True

    def sign_in(self, subject, name):
        self.ensure_schema()
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.engine.begin() as conn:
            # Upsert also handles two simultaneous callbacks for the same user.
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as upsert
            else:
                from sqlalchemy.dialects.sqlite import insert as upsert
            conn.execute(upsert(users).values(id=subject, name=name, speak=True)
                         .on_conflict_do_update(index_elements=[users.c.id], set_={"name": name}))
            conn.execute(delete(sessions).where(sessions.c.expires < now))
            conn.execute(insert(sessions).values(token_hash=token_hash(token), user_id=subject, expires=now + 86400))
        return token

    def user_for_session(self, token):
        self.ensure_schema()
        with self.engine.connect() as conn:
            row = conn.execute(select(users).join(sessions, sessions.c.user_id == users.c.id)
                .where(sessions.c.token_hash == token_hash(token), sessions.c.expires > time.time())).mappings().first()
            return dict(row) if row else None

    def sign_out(self, token):
        with self.engine.begin() as conn:
            conn.execute(delete(sessions).where(sessions.c.token_hash == token_hash(token)))

    def preferences(self, user_id, speak):
        with self.engine.begin() as conn:
            conn.execute(update(users).where(users.c.id == user_id).values(speak=speak))

    def list_chats(self, user_id):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(chats.c.id, chats.c.title, chats.c.updated)
                .where(chats.c.user_id == user_id).order_by(chats.c.updated.desc()).limit(100)).mappings()]

    def get_chat(self, user_id, chat_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(chats).where(chats.c.id == chat_id, chats.c.user_id == user_id)).mappings().first()
            if not row:
                raise NotFound("This conversation is unavailable.")
            return {key: row[key] for key in ("id", "title", "messages", "revision", "updated")}

    def save_turn(self, user_id, previous, message, answer):
        messages = (previous["messages"] if previous else []) + [
            {"role": "user", "text": message},
            {"role": "model", "text": answer["reply"][:8000], "links": answer.get("links", [])}]
        if len(messages) > 200:
            raise Conflict("This conversation is full. Start a new chat.")
        chat_id = previous["id"] if previous else str(uuid4())
        revision = previous["revision"] + 1 if previous else 1
        with self.engine.begin() as conn:
            if previous:
                result = conn.execute(update(chats).where(chats.c.id == chat_id, chats.c.user_id == user_id,
                    chats.c.revision == previous["revision"]).values(messages=messages, revision=revision, updated=time.time()))
                if result.rowcount != 1:
                    raise Conflict("This chat changed in another tab. Reload it before sending again.")
            else:
                # Lock the owner, serializing the per-account chat quota across workers.
                conn.execute(select(users.c.id).where(users.c.id == user_id).with_for_update()).first()
                count = len(conn.execute(select(chats.c.id).where(chats.c.user_id == user_id).limit(100)).all())
                if count >= 100:
                    raise TooManyRequests("Your account has 100 conversations. Delete one before starting another.")
                conn.execute(insert(chats).values(id=chat_id, user_id=user_id, title=message[:80],
                    messages=messages, revision=revision, updated=time.time()))
        return {"id": chat_id, "revision": revision}

    def delete_chat(self, user_id, chat_id):
        with self.engine.begin() as conn:
            result = conn.execute(delete(chats).where(chats.c.id == chat_id, chats.c.user_id == user_id))
            if result.rowcount != 1:
                raise NotFound("This conversation is unavailable.")

    def memory_enabled(self, user_id, conn=None):
        if conn is None:
            with self.engine.connect() as connection:
                return self.memory_enabled(user_id, connection)
        value = conn.execute(select(memory_settings.c.enabled).where(memory_settings.c.user_id == user_id)).scalar()
        return value is not False

    def list_memories(self, user_id):
        self.ensure_schema()
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(select(memories.c.id, memories.c.topic,
                memories.c.fact, memories.c.updated).where(memories.c.user_id == user_id)
                .order_by(memories.c.updated.desc()).limit(50)).mappings()]

    def set_memory_enabled(self, user_id, enabled):
        with self.engine.begin() as conn:
            conn.execute(select(users.c.id).where(users.c.id == user_id).with_for_update()).first()
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as upsert
            else:
                from sqlalchemy.dialects.sqlite import insert as upsert
            conn.execute(upsert(memory_settings).values(user_id=user_id, enabled=enabled)
                .on_conflict_do_update(index_elements=[memory_settings.c.user_id], set_={"enabled": enabled}))

    def remember(self, user_id, topic, fact):
        # The same owner lock serializes preference changes, corrections and quota checks.
        with self.engine.begin() as conn:
            conn.execute(select(users.c.id).where(users.c.id == user_id).with_for_update()).first()
            if not self.memory_enabled(user_id, conn):
                return {"success": False, "message": "Memory is paused. Nothing was saved."}
            existing = conn.execute(select(memories.c.id).where(memories.c.user_id == user_id,
                memories.c.topic == topic)).scalar()
            now = time.time()
            if existing:
                conn.execute(update(memories).where(memories.c.id == existing, memories.c.user_id == user_id)
                    .values(fact=fact, updated=now))
                return {"success": True, "id": existing, "message": "Memory updated for this account."}
            count = len(conn.execute(select(memories.c.id).where(memories.c.user_id == user_id).limit(50)).all())
            if count >= 50:
                return {"success": False, "message": "Memory is full. Remove a fact in Memory before adding another."}
            fact_id = str(uuid4())
            conn.execute(insert(memories).values(id=fact_id, user_id=user_id, topic=topic, fact=fact, updated=now))
            return {"success": True, "id": fact_id, "message": "Memory saved for this account."}

    def forget(self, user_id, fact_id):
        with self.engine.begin() as conn:
            result = conn.execute(delete(memories).where(memories.c.id == fact_id, memories.c.user_id == user_id))
            if result.rowcount != 1:
                raise NotFound("This memory is unavailable.")
