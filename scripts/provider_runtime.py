"""Review explicit provider bindings locally; never activate a live Worker or call models."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from visual_platform.providers.runtime import credential_status, load_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--check-credentials", action="store_true")
    args = parser.parse_args()
    try:
        runtime = load_runtime(args.config)
        keys = credential_status(runtime) if args.check_credentials else None
        ready = keys is None or all(keys.values())
        print(
            json.dumps(
                {
                    "result": "RUNTIME_BINDING_REVIEW_READY"
                    if ready
                    else "WAITING_PRIVATE_CREDENTIALS",
                    "configuration_sha256": runtime.digest(),
                    "models": runtime.execution_binding()["provider_models"],
                    "endpoints": runtime.execution_binding()["provider_endpoints"],
                    "key_environment": {
                        "generate": runtime.generate.key_environment,
                        "detect": runtime.detect.key_environment,
                    },
                    "reviewed_credential_present": keys,
                    "credential_identity_verified": False,
                    "merchant_identity_verified": False,
                    "supplier_compatibility_verified": False,
                    "execution_enabled": False,
                    "paid_calls": 0,
                }
            )
        )
        return 0 if ready else 3
    except Exception as error:
        print(
            json.dumps(
                {
                    "result": "RUNTIME_BINDING_REJECTED",
                    "error_type": type(error).__name__,
                    "paid_calls": 0,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
