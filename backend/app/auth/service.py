from __future__ import annotations

import time

from app.auth.config import AuthSettings
from app.auth.security import PasswordHasher
from app.auth.store import AuthStore


class AuthError(Exception):
    pass


class AuthLockedError(AuthError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Too many failed login attempts. Retry in {retry_after_seconds} seconds.")


class AuthService:
    def __init__(self, store: AuthStore, settings: AuthSettings) -> None:
        self.store = store
        self.settings = settings
        self.password_hasher = PasswordHasher()
        self._bootstrap_default_user()

    def _now(self) -> int:
        return int(time.time())

    def _normalize_username(self, username: str) -> str:
        return username.strip().lower()

    def _public_user(self, user: dict) -> dict:
        return {"user_id": user["user_id"], "username": user["username"]}

    def _bootstrap_default_user(self) -> None:
        if self.store.has_users():
            return
        username = self._normalize_username(self.settings.bootstrap_username)
        password_hash = self.password_hasher.hash_password(self.settings.bootstrap_password)
        self.store.create_user(username=username, password_hash=password_hash, now_ts=self._now())

    def ensure_user(self, username: str, password: str) -> dict:
        normalized_username = self._normalize_username(username)
        existing = self.store.get_user_by_username(normalized_username)
        if existing is not None:
            return self._public_user(existing)
        password_hash = self.password_hasher.hash_password(password)
        user = self.store.create_user(
            username=normalized_username,
            password_hash=password_hash,
            now_ts=self._now(),
        )
        return self._public_user(user)

    def register(self, username: str, password: str) -> tuple[dict, dict]:
        normalized_username = self._normalize_username(username)
        if self.store.get_user_by_username(normalized_username) is not None:
            raise AuthError("Username is already taken")

        password_hash = self.password_hasher.hash_password(password)
        user = self.store.create_user(
            username=normalized_username,
            password_hash=password_hash,
            now_ts=self._now(),
        )
        self.store.clear_failures(normalized_username)
        session = self.store.create_session(
            user_id=user["user_id"],
            now_ts=self._now(),
            ttl_seconds=self.settings.session_ttl_seconds,
        )
        return self._public_user(user), session

    def login(self, username: str, password: str) -> tuple[dict, dict]:
        now_ts = self._now()
        normalized_username = self._normalize_username(username)
        locked_until = self.store.get_locked_until(normalized_username, now_ts)
        if locked_until is not None:
            raise AuthLockedError(max(1, locked_until - now_ts))

        user = self.store.get_user_by_username(normalized_username)
        if user is None or not self.password_hasher.verify_password(user["password_hash"], password):
            locked_until = self.store.register_login_failure(
                username=normalized_username,
                now_ts=now_ts,
                max_failures=self.settings.login_max_failures,
                window_seconds=self.settings.login_failure_window_seconds,
                lockout_seconds=self.settings.login_lockout_seconds,
            )
            if locked_until is not None:
                raise AuthLockedError(max(1, locked_until - now_ts))
            raise AuthError("Invalid username or password")

        self.store.clear_failures(normalized_username)
        session = self.store.create_session(
            user_id=user["user_id"],
            now_ts=now_ts,
            ttl_seconds=self.settings.session_ttl_seconds,
        )
        return self._public_user(user), session

    def get_user_from_session(self, session_id: str | None) -> dict | None:
        if not session_id:
            return None
        session = self.store.get_valid_session(session_id=session_id, now_ts=self._now())
        if session is None:
            return None
        user = self.store.get_user_by_id(session["user_id"])
        if user is None:
            return None
        return self._public_user(user)

    def logout(self, session_id: str | None) -> None:
        if not session_id:
            return
        self.store.invalidate_session(session_id=session_id, now_ts=self._now())
