"""Demo identities; no role or employee identity is accepted from login claims."""
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt

from app.auth.models import Role
from app.config import Settings

ISSUER = "career-quest-demo"
AUDIENCE = "career-quest-api"
TOKEN_SECONDS = 3600


@dataclass(frozen=True)
class Principal:
    role: Role
    employee_id: str | None = None


def issue_token(config: Settings, principal: Principal) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    subject = "demo:hr" if principal.role == Role.HR else f"employee:{principal.employee_id}"
    return jwt.encode({"sub": subject, "role": principal.role.value, "iat": now,
                       "exp": now + TOKEN_SECONDS, "iss": ISSUER, "aud": AUDIENCE},
                      config.jwt_secret.get_secret_value(), algorithm="HS256")


def read_token(config: Settings, token: str) -> Principal:
    claims = jwt.decode(token, config.jwt_secret.get_secret_value(), algorithms=["HS256"],
        issuer=ISSUER, audience=AUDIENCE,
        options={"require": ["sub", "role", "iat", "exp", "iss", "aud"], "strict_aud": True})
    if type(claims["iat"]) is not int or type(claims["exp"]) is not int or claims["exp"] <= claims["iat"]:
        raise jwt.InvalidTokenError("Invalid timestamps")
    if claims["role"] == Role.HR.value and claims["sub"] == "demo:hr":
        return Principal(Role.HR)
    if claims["role"] == Role.EMPLOYEE.value and claims["sub"].startswith("employee:"):
        employee_id = claims["sub"][len("employee:"):]
        if 1 <= len(employee_id) <= 200:
            return Principal(Role.EMPLOYEE, employee_id)
    raise jwt.InvalidTokenError("Invalid principal")
