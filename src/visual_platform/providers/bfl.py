"""FLUX 3 protocol. Never retries POST; Worker must durably authorize each intent.

This module is not enabled in the offline Worker. Tests inject MockTransport.
"""

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from visual_platform.domain.schemas import Generation
from visual_platform.providers.contract import ProviderFailure, ProviderUncertain, Receipt


class BflRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    # Internal envelope includes our identity/background instruction. The public
    # Generation limit remains 4000; never truncate the customer's description.
    prompt: Annotated[str, Field(min_length=1, max_length=4096)]
    images: Annotated[list[str], Field(min_length=1, max_length=10)]
    width: Annotated[int, Field(ge=256, le=6256)]
    height: Annotated[int, Field(ge=256, le=6256)]
    grounding: Literal[False] = False

    @field_validator("grounding", mode="before")
    @classmethod
    def no_external_research(cls, value):
        if type(value) is not bool or value:
            raise ValueError("grounding must be false")
        return value

    @field_validator("prompt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("invalid prompt")
        return value

    @field_validator("images")
    @classmethod
    def inline_only(cls, values):
        # Caller supplies canonical source bytes. No localhost/signed S3 URLs leave server.
        size = 0
        for value in values:
            if len(value) > 28_000_000:
                raise ValueError("reference too large")
            try:
                data = base64.b64decode(value, validate=True)
            except ValueError:
                raise ValueError("base64 image required") from None
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("canonical PNG required")
            size += len(data)
        if size > 20 * 1024 * 1024:
            raise ValueError("references exceed limit")
        return values

    @model_validator(mode="after")
    def pixels(self):
        if self.width * self.height > 4_000_000:
            raise ValueError("editing limited to project 4MP budget")
        return self

    @classmethod
    def from_canonical(cls, generation, source_png):
        g = Generation.model_validate(generation)
        prompt = (
            "Use a plain white background. Preserve product identity. "
            if g.type == "white_background"
            else "Preserve the referenced product identity. "
        ) + g.prompt
        return cls(
            prompt=prompt,
            images=[base64.b64encode(source_png).decode("ascii")],
            width=g.output.width,
            height=g.output.height,
        )


def checked_url(value, kind, provider_id=None):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 8192
        or any(c.isspace() or ord(c) < 32 for c in value)
        or "\\" in value
    ):
        raise ValueError("invalid provider URL")
    try:
        u = urlsplit(value)
        if (
            u.scheme != "https"
            or u.username
            or u.password
            or u.port not in (None, 443)
            or u.fragment
        ):
            raise ValueError()
        pattern = (
            r"api(?:\.[a-z0-9-]+)?\.bfl\.ai" if kind == "poll" else r"delivery\.[a-z0-9-]+\.bfl\.ai"
        )
        if not u.hostname or not re.fullmatch(pattern, u.hostname):
            raise ValueError()
        if kind == "poll" and (
            u.path != "/v1/get_result" or parse_qs(u.query).get("id") != [provider_id]
        ):
            raise ValueError()
    except ValueError:
        raise ValueError("untrusted provider URL") from None
    return value


@dataclass(frozen=True)
class BflPoll:
    provider_id: str
    status: str
    sample_url: str | None = None


@dataclass(frozen=True)
class BflArtifact:
    data: bytes
    mime: str
    sha256: str


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class BflProvider:
    endpoint = "https://api.bfl.ai/v1/flux-3-image"

    def __init__(self, key, private_directory, *, transport=None):
        if not isinstance(key, str) or not key or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError("invalid BFL key")
        self._key = key
        self.offline_transport = isinstance(transport, httpx.MockTransport)
        self.directory = Path(private_directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        # No auth defaults, cookies from callers, environment proxy or redirects.
        self.client = httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(30, connect=5),
        )
        self.download_client = httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(30, connect=5),
        )

    def close(self):
        self.client.close()
        self.download_client.close()

    def _path(self, intent, suffix):
        return self.directory / (str(UUID(str(intent))) + suffix)

    def _write(self, path, value):
        with path.open("xb") as f:
            f.write(encoded(value))
            f.flush()
            os.fsync(f.fileno())

    def _json(self, method, url, *, payload=None):
        # There are deliberately no retry loops, including for 429 or connection errors.
        try:
            with self.client.stream(
                method,
                url,
                headers={
                    "x-key": self._key,
                    "accept": "application/json",
                    "accept-encoding": "identity",
                },
                json=payload,
            ) as response:
                if method == "POST" and response.status_code in (400, 401, 402, 403, 422, 429):
                    raise ProviderFailure("BFL submission explicitly rejected")
                if response.status_code != 200:
                    raise ProviderUncertain("BFL response unavailable")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ProviderUncertain("BFL compressed response rejected")
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        raise ProviderUncertain("BFL response exceeds limit")
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError()
                return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise ProviderUncertain("BFL response cannot be confirmed") from None

    def submit(self, intent_id, request):
        if not isinstance(request, BflRequest):
            raise TypeError("validated BflRequest required")
        payload = BflRequest.model_validate(request.model_dump()).model_dump()
        intent = UUID(str(intent_id))
        try:
            self._write(
                self._path(intent, ".intent"),
                {"request_sha256": hashlib.sha256(encoded(payload)).hexdigest()},
            )
        except FileExistsError:
            raise ProviderUncertain(
                "BFL intent already attempted; reconcile existing receipt"
            ) from None
        result = self._json("POST", self.endpoint, payload=payload)
        try:
            identity = result["id"]
            if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", identity):
                raise ValueError()
            polling = checked_url(result["polling_url"], "poll", identity)
            digest = hashlib.sha256(encoded(result)).hexdigest()
            cost = result.get("cost")
            invalid_cost = cost is not None and (
                type(cost) not in (int, float) or not Decimal(str(cost)).is_finite() or cost < 0
            )
            # OpenAPI defines cost as credits, not fiat currency or our internal wallet units.
            record = {
                "provider_id": identity,
                "polling_url": polling,
                "response_digest": digest,
                "cost": {
                    "quantity": str(Decimal(str(cost)))
                    if cost is not None and not invalid_cost
                    else None,
                    "validation": "invalid"
                    if invalid_cost
                    else "missing"
                    if cost is None
                    else "reported",
                    "unit": "BFL_CREDIT",
                    "money_amount": None,
                    "currency": None,
                    "source": "bfl_submit_response",
                    "source_digest": digest,
                },
            }
            self._write(self._path(intent, ".receipt.json"), record)
            if invalid_cost:
                raise ProviderUncertain(
                    "BFL cost malformed; existing receipt preserved for reconciliation"
                )
            return Receipt(identity, digest, polling)
        except (KeyError, ValueError, TypeError, OSError):
            raise ProviderUncertain("BFL receipt requires reconciliation") from None

    def receipt_record(self, intent_id):
        # Trusted private recovery metadata; never treat absence as permission to resubmit.
        try:
            value = json.loads(self._path(intent_id, ".receipt.json").read_bytes())
            checked_url(value["polling_url"], "poll", value["provider_id"])
            return value
        except (OSError, ValueError, KeyError, TypeError):
            raise ProviderUncertain("BFL receipt unavailable; do not resubmit") from None

    def poll(self, receipt):
        try:
            url = checked_url(receipt.polling_url, "poll", receipt.provider_id)
        except ValueError:
            raise ProviderUncertain("BFL polling URL rejected") from None
        result = self._json("GET", url)
        status = result.get("status")
        if status in ("Error", "Failed", "Request Moderated", "Content Moderated"):
            raise ProviderFailure("BFL terminal generation failure")
        if status in ("Pending", "Reasoning", "Generating"):
            return BflPoll(receipt.provider_id, status)
        if status != "Ready":
            raise ProviderUncertain("BFL status not recognized")
        try:
            sample = checked_url(result["result"]["sample"], "download")
        except (KeyError, TypeError, ValueError):
            raise ProviderUncertain("BFL ready result requires reconciliation") from None
        return BflPoll(receipt.provider_id, status, sample)

    def fetch_result(self, poll):
        if not isinstance(poll, BflPoll) or poll.status != "Ready":
            raise ValueError("Ready result required")
        try:
            url = checked_url(poll.sample_url, "download")
            # Fresh request has no x-key; only the trusted BFL delivery host may receive it.
            with self.download_client.stream(
                "GET",
                url,
                headers={"accept": "image/png,image/jpeg", "accept-encoding": "identity"},
            ) as response:
                if response.status_code != 200:
                    raise ProviderUncertain("BFL image unavailable")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ProviderUncertain("BFL compressed download rejected")
                mime = response.headers.get("content-type", "").split(";")[0].lower()
                if mime not in ("image/png", "image/jpeg"):
                    raise ProviderUncertain("BFL image MIME rejected")
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    data.extend(chunk)
                    if len(data) > 20 * 1024 * 1024:
                        raise ProviderUncertain("BFL image exceeds limit")
            raw = bytes(data)
            if not raw:
                raise ProviderUncertain("BFL empty image")
            # Caller must use isolated canonical decoder, check actual dimensions and pixel paste.
            return BflArtifact(raw, mime, hashlib.sha256(raw).hexdigest())
        except (httpx.HTTPError, ValueError):
            raise ProviderUncertain("BFL image download cannot be confirmed") from None
