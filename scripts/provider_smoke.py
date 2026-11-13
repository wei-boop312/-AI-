"""Review minimum paid-smoke scope. No live execution is enabled by this command."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from visual_platform.providers.authorization import (
    UnitSmokeAuthorization,
    load_authorization,
    verify_sample,
)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if not args.preflight:
        print(
            json.dumps(
                {
                    "result": "WAITING_EXTERNAL",
                    "paid_calls": 0,
                    "reason": "live execution disabled; use --preflight for offline review",
                }
            )
        )
        return 3
    try:
        scope, digest = load_authorization(args.config)
        sample = await verify_sample(scope, args.config)
    except Exception as error:
        # Do not echo Pydantic inputs, paths or config contents into shared diagnostics.
        print(
            json.dumps(
                {
                    "result": "PREFLIGHT_REJECTED",
                    "paid_calls": 0,
                    "error_type": type(error).__name__,
                }
            )
        )
        return 1
    print(
        json.dumps(
            {
                "result": "SCOPE_REVIEW_READY",
                "paid_calls": 0,
                "configuration_sha256": digest,
                "authorization_id": str(scope.authorization_id),
                "sample": sample,
                "models": {"generate": scope.bfl_model, "detect": scope.gemini_model},
                "call_limits": {
                    "generate": scope.max_generate_calls,
                    "detect": scope.max_detect_calls,
                },
                "cost_ceiling": (
                    {
                        "step_budgets": scope.step_budgets.model_dump(mode="json"),
                        "currency_totals": [
                            row.model_dump(mode="json") for row in scope.currency_totals
                        ],
                    }
                    if isinstance(scope, UnitSmokeAuthorization)
                    else {
                        "currency": scope.currency,
                        "generate": scope.generate_ceiling,
                        "detect": scope.detect_ceiling,
                        "total": scope.total_ceiling,
                    }
                ),
                "expires_at": scope.expires_at.isoformat(),
                "execution_enabled": False,
                "not_verified": [
                    "operator spending authorization",
                    "atomic monetary budget",
                    "live Worker routing",
                    "supplier pricing and actual billing",
                    "real archived image and final report",
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
