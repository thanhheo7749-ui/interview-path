# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import time


def build_usage(provider: str, model: str, started_at: float) -> dict:
    return {
        "provider": provider,
        "model": model,
        "latency_ms": int((time.time() - started_at) * 1000),
    }
