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
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "visual-private"
    s3_region: str = "us-east-1"
    issuer: str = "visual-platform"
    audience: str = "visual-web"

    def __post_init__(self):
        u=urlsplit(self.origin)
        if u.scheme not in ("http","https") or not u.netloc or u.path or u.query or u.fragment:
            raise ValueError("APP_ORIGIN must be an exact origin")
        if not self.cookie_secure and (u.scheme!="http" or u.hostname not in ("localhost","127.0.0.1")):
            raise ValueError("insecure cookies allowed only on explicit local HTTP profile")

        if self.s3_endpoint:
            s3=urlsplit(self.s3_endpoint)
            if not self.s3_access_key or not self.s3_secret_key: raise ValueError("explicit S3 credentials required")
            if s3.scheme not in ("http","https") or not s3.hostname: raise ValueError("invalid S3 endpoint")
            if s3.scheme=="http" and s3.hostname not in ("localhost","127.0.0.1"): raise ValueError("remote S3 requires HTTPS")

    @classmethod
    def from_env(cls):
        return cls(api_database_url=os.environ["API_DATABASE_URL"],auth_database_url=os.environ["AUTH_DATABASE_URL"],
                   private_key=Path(os.environ["JWT_PRIVATE_KEY_FILE"]).read_text(),public_key=Path(os.environ["JWT_PUBLIC_KEY_FILE"]).read_text(),
                   origin=os.environ["APP_ORIGIN"],cookie_secure=os.environ.get("COOKIE_SECURE","1")=="1",s3_endpoint=os.environ.get("S3_ENDPOINT"),s3_access_key=os.environ.get("S3_ACCESS_KEY"),s3_secret_key=os.environ.get("S3_SECRET_KEY"),s3_bucket=os.environ.get("S3_BUCKET","visual-private"),s3_region=os.environ.get("S3_REGION","us-east-1"))
