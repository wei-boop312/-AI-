from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Settings:
    api_database_url: str
    auth_database_url: str
    private_key: str
    public_key: str
    origin: str
    cookie_secure: bool = True
    issuer: str = "visual-platform"
    audience: str = "visual-web"

    def __post_init__(self):
        u=urlsplit(self.origin)
        if u.scheme not in ("http","https") or not u.netloc or u.path or u.query or u.fragment:
            raise ValueError("APP_ORIGIN must be an exact origin")
        if not self.cookie_secure and (u.scheme!="http" or u.hostname not in ("localhost","127.0.0.1")):
            raise ValueError("insecure cookies allowed only on explicit local HTTP profile")

    @classmethod
    def from_env(cls):
        return cls(api_database_url=os.environ["API_DATABASE_URL"],auth_database_url=os.environ["AUTH_DATABASE_URL"],
                   private_key=Path(os.environ["JWT_PRIVATE_KEY_FILE"]).read_text(),public_key=Path(os.environ["JWT_PUBLIC_KEY_FILE"]).read_text(),
                   origin=os.environ["APP_ORIGIN"],cookie_secure=os.environ.get("COOKIE_SECURE","1")=="1")
