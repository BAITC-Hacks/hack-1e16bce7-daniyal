from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://career_quest:career_quest_dev@127.0.0.1:55432/career_quest",
        repr=False,
    )
    demo_auth_enabled: bool = False
    demo_hr_password: SecretStr = Field(default=SecretStr(""), repr=False)
    jwt_secret: SecretStr = Field(default=SecretStr(""), repr=False)

    def validate_auth(self) -> None:
        if self.demo_auth_enabled:
            if len(self.jwt_secret.get_secret_value().encode()) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 bytes when DEMO_AUTH_ENABLED=true")
            if not self.demo_hr_password.get_secret_value().strip():
                raise ValueError("DEMO_HR_PASSWORD is required when DEMO_AUTH_ENABLED=true")
