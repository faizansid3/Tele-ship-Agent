"""
Route B inference: all model calls go through the Hermes CLI.

We never talk to a provider directly. Hermes owns the qwen3-coder-next
provider, auth, and model config; we invoke it in one-shot mode with toolsets
disabled so it behaves as a pure text->text function.

    hermes -z "<prompt>" -m qwen3-coder-next -t "" --cli
"""

import json
import re
import shutil
import subprocess

from config import HERMES_BIN, HERMES_MODEL, HERMES_TIMEOUT


class HermesError(RuntimeError):
    pass


def _resolve_bin() -> str:
    path = shutil.which(HERMES_BIN)
    if not path:
        raise HermesError(
            f"Hermes CLI '{HERMES_BIN}' not found on PATH. "
            "Set HERMES_BIN to the absolute path in config.py."
        )
    return path


def complete(prompt: str) -> str:
    """Run a one-shot Hermes completion and return raw stdout text."""
    # NB: we deliberately do NOT pass `-m`. Hermes' configured default is
    # already qwen3-coder-next via the ollama-cloud provider; forcing the
    # model by name re-routes it to a different provider (alibaba/DashScope)
    # that needs a separate API key. Let Hermes use its default routing.
    cmd = [
        _resolve_bin(),
        "-z", prompt,
        "-t", "",          # no toolsets -> pure LLM
        "--cli",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=HERMES_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        raise HermesError(f"Hermes timed out after {HERMES_TIMEOUT}s") from e

    if proc.returncode != 0:
        raise HermesError(
            f"Hermes exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    return proc.stdout.strip()


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def complete_json(prompt: str) -> dict:
    """Run a completion and parse the first JSON object out of the reply.

    Tolerates code fences and surrounding prose, which small models add.
    """
    raw = complete(prompt)

    # Prefer fenced block if present.
    m = _FENCE_RE.search(raw)
    candidate = m.group(1) if m else raw

    # Fall back to the outermost {...} span.
    if not candidate.lstrip().startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1:
            candidate = candidate[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise HermesError(
            f"Could not parse JSON from Hermes reply: {e}\n--- reply ---\n{raw[:500]}"
        ) from e


if __name__ == "__main__":
    print("Testing Hermes route B...")
    out = complete_json(
        'Return JSON only: {"status":"ok","model":"<the model you are>"}'
    )
    print("Parsed:", out)
