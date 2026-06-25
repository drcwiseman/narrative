import os


class Settings:
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production-32-char-key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    token_exp_minutes: int = int(os.getenv("TOKEN_EXP_MINUTES", "480"))
    webhook_timeout_seconds: int = int(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5"))


settings = Settings()
