"""Review paid-smoke scope without interpreting a configuration as permission to spend."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from visual_platform.domain.schemas import Generation, Targets


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate configuration field")
        result[key] = value
    return result


class SmokeAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    authorization_id: UUID
    authorized_by: Annotated[str, Field(min_length=1, max_length=160)]
    authorized_at: datetime
    expires_at: datetime
    source_path: Annotated[str, Field(min_length=1, max_length=1000)]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    generation: Generation
    targets: Targets
    bfl_model: Literal["flux-3-image"] = "flux-3-image"
    gemini_model: Literal["gemini-3.8-flash"] = "gemini-3.8-flash"
    max_generate_calls: Annotated[int, Field(ge=1, le=1)] = 1
    max_detect_calls: Annotated[int, Field(ge=1, le=1)] = 1
    currency: Literal["USD"] = "USD"
    generate_ceiling: str
    detect_ceiling: str
    total_ceiling: str

    @field_validator("generate_ceiling", "detect_ceiling", "total_ceiling")
    @classmethod
    def money(cls, value):
        # Exact decimal strings only: no float rounding, infinity or exponent notation.
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?", value):
            raise ValueError("positive fixed-point decimal string required")
        if Decimal(value) <= 0:
            raise ValueError("cost ceiling must be positive")
        return value

    @field_validator("authorized_by", "source_path")
    @classmethod
    def text(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("blank or control characters rejected")
        return value

    @model_validator(mode="after")
    def scope(self):
        for value in (self.authorized_at, self.expires_at):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError("explicit UTC timestamps required")
        if not timedelta(0) < self.expires_at - self.authorized_at <= timedelta(hours=24):
            raise ValueError("authorization duration must be at most 24 hours")
        if Decimal(self.total_ceiling) < Decimal(self.generate_ceiling) + Decimal(
            self.detect_ceiling
        ):
            raise ValueError("total ceiling cannot cover both authorized requests")
        return self


def load_authorization(path: Path, *, now: datetime | None = None):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("regular configuration file of at most 64 KiB required")
    raw = path.read_bytes()
    if len(raw) > 65536:
        raise ValueError("configuration grew beyond limit")
    data = json.loads(raw, object_pairs_hook=unique_object)
    # JSON mode accepts UUID/ISO timestamps while retaining strict numeric/string types.
    scope = SmokeAuthorization.model_validate_json(json.dumps(data))
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None or not scope.authorized_at <= instant < scope.expires_at:
        raise ValueError("authorization is not currently valid")
    canonical = json.dumps(
        scope.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return scope, hashlib.sha256(canonical).hexdigest()


async def verify_sample(scope: SmokeAuthorization, config_path: Path):
    source = Path(scope.source_path)
    if not source.is_absolute():
        source = config_path.parent / source
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("regular canonical PNG of at most 20 MiB required")
    with source.open("rb") as stream:
        data = stream.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("source grew beyond limit")
    if hashlib.sha256(data).hexdigest() != scope.source_sha256:
        raise ValueError("source bytes differ from reviewed hash")
    # Full pixel/canonical validation belongs to the existing isolated decoder.
    from visual_platform.providers.bfl import BflRequest
    from visual_platform.services.upload import decode

    canonical, decoded = await decode(data, "image/png")
    if hashlib.sha256(canonical).hexdigest() != scope.source_sha256:
        raise ValueError("sample must already be the canonical PNG, not an original upload")
    generation = scope.generation
    if generation.protection_mode == "pixel_exact":
        if (generation.output.width, generation.output.height) != (
            decoded["width"],
            decoded["height"],
        ):
            raise ValueError("pixel_exact output must match canonical source dimensions")
        if any(
            region.source_x + region.width > decoded["width"]
            or region.source_y + region.height > decoded["height"]
            for region in generation.regions
        ):
            raise ValueError("source rectangle exceeds reviewed sample")
    BflRequest.from_canonical(generation.model_dump(mode="json"), canonical)
    return {"sha256": scope.source_sha256, "width": decoded["width"], "height": decoded["height"]}
