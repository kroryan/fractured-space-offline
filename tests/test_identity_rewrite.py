import base64
import importlib.util
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fso_linux", ROOT / "linux" / "fso_linux.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

recorded = json.loads((ROOT / "server" / "responses.json").read_text(encoding="utf-8"))
token_body = next(
    entry["response"]["content"]
    for entry in recorded
    if entry["request"]["url"].endswith("/auth/oauth2/token")
)

for identity in (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
):
    MODULE.ACTIVE_IDENTITY = identity
    response = json.loads(MODULE.rewrite_identity_payload(token_body.encode("utf-8")))
    assert response["identity_id"] == identity
    jwt_claims = response["access_token"].split(".")[1]
    jwt_claims += "=" * ((4 - len(jwt_claims) % 4) % 4)
    assert json.loads(base64.urlsafe_b64decode(jwt_claims))["sub"] == identity
    refresh = response["refresh_token"].split(".")[1]
    refresh += "=" * ((4 - len(refresh) % 4) % 4)
    assert json.loads(zlib.decompress(base64.urlsafe_b64decode(refresh)))["id"] == identity

print("Linux identity rewrite smoke test passed (body, JWT and refresh token).")
