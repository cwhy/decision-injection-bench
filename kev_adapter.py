"""Adapter for Kev (jaredpalmer/kev), a small Jev-like decision model.

Kev serves a System One-compatible endpoint, so the canonical request maps
across almost directly: `state.submitted_content` becomes `state`, and the
single canonical question becomes one entry in `questions`.

The trusted criterion stays outside the attacker-controlled string, exactly as
it does for the other backends. Probabilities are Kev's own pointer-head
outputs over the allowed labels, not synthesized scores.

By default Kev applies its stored calibration temperature. Set
KEV_TEMPERATURE=1.0 on the *server* for raw logits; that is a property of the
serving process, so it is recorded here only as reported by the server.

Environment:
  KEV_URL       base URL of the Kev server (default http://127.0.0.1:8009)
  KEV_MODEL     model string to send    (default kev-latest)
  KEV_REVISION  resolved checkpoint revision, recorded for provenance
  KEV_API_KEY   optional bearer token, if the server requires one
"""

import json
import os
import urllib.request

URL = os.environ.get("KEV_URL", "http://127.0.0.1:8009").rstrip("/")
MODEL = os.environ.get("KEV_MODEL", "kev-latest")
REVISION = os.environ.get("KEV_REVISION", "")
API_KEY = os.environ.get("KEV_API_KEY", "")
TIMEOUT = float(os.environ.get("KEV_TIMEOUT", "120"))


def classify(request):
    question = request["question"]
    payload = {
        "model": MODEL,
        "state": request["state"]["submitted_content"],
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": question["instructions"],
                "criteria": question["criteria"],
            }
        },
    }
    headers = {"content-type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    call = urllib.request.Request(
        f"{URL}/v1/systemone",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(call, timeout=TIMEOUT) as response:
        served = response.headers.get("x-typesafe-request-id", "")
        body = json.loads(response.read())

    answer = body["answers"]["decision"]
    probabilities = {k: float(v) for k, v in answer["probabilities"].items()}
    # Kev rounds to four decimals; renormalize so the sum lands inside the
    # harness tolerance without altering the reported ordering.
    total = sum(probabilities.values())
    if total > 0:
        probabilities = {k: v / total for k, v in probabilities.items()}

    return {
        "choice": answer["choice"],
        "probabilities": probabilities,
        "resolved_model": REVISION or body.get("model", MODEL),
        "native_confidence": answer.get("confidence"),
        "served_request_id": served,
    }
