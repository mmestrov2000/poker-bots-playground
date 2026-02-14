from __future__ import annotations

from typing import Final


ARGON2_PREFIX: Final[str] = "$argon2"
HASH_SCHEME_ARGON2ID: Final[str] = "argon2id"
HASH_SCHEME_BCRYPT: Final[str] = "bcrypt"


class PasswordHasher:
    def __init__(self) -> None:
        self._argon2 = None
        self._bcrypt = None
        self.scheme = HASH_SCHEME_BCRYPT

        try:
            from argon2 import PasswordHasher as Argon2PasswordHasher
            from argon2.low_level import Type

            self._argon2 = Argon2PasswordHasher(type=Type.ID)
            self.scheme = HASH_SCHEME_ARGON2ID
            return
        except ImportError:
            self._argon2 = None

        try:
            import bcrypt

            self._bcrypt = bcrypt
        except ImportError as exc:
            raise RuntimeError("Missing password hashing dependency (argon2-cffi or bcrypt)") from exc

    def hash_password(self, plain_password: str) -> str:
        if self._argon2 is not None:
            return self._argon2.hash(plain_password)
        return self._bcrypt.hashpw(plain_password.encode("utf-8"), self._bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password_hash: str, plain_password: str) -> bool:
        if password_hash.startswith(ARGON2_PREFIX):
            if self._argon2 is None:
                return False
            try:
                return bool(self._argon2.verify(password_hash, plain_password))
            except Exception:
                return False

        if self._bcrypt is None:
            return False
        try:
            return bool(self._bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8")))
        except ValueError:
            return False
