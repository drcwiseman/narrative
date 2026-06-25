import os


class Settings:
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production-32-char-key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "narrative")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "narrative-web")
    token_exp_minutes: int = int(os.getenv("TOKEN_EXP_MINUTES", "480"))
    refresh_token_exp_minutes: int = int(os.getenv("REFRESH_TOKEN_EXP_MINUTES", "10080"))
    webhook_timeout_seconds: int = int(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5"))
    webhook_signing_secret: str = os.getenv("WEBHOOK_SIGNING_SECRET", "change-webhook-secret")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    alert_error_rate_threshold: float = float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "0.2"))
    app_base_url: str = os.getenv("APP_BASE_URL", "")
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    slack_critical_webhook_url: str = os.getenv("SLACK_CRITICAL_WEBHOOK_URL", "")
    slack_signing_secret: str = os.getenv("SLACK_SIGNING_SECRET", "")
    slack_verification_token: str = os.getenv("SLACK_VERIFICATION_TOKEN", "")
    slack_alert_threshold: float = float(os.getenv("SLACK_ALERT_THRESHOLD", "0.5"))
    slack_critical_threshold: float = float(os.getenv("SLACK_CRITICAL_THRESHOLD", "0.8"))
    crm_webhook_url: str = os.getenv("CRM_WEBHOOK_URL", "")
    x_webhook_secret: str = os.getenv("X_WEBHOOK_SECRET", "")
    facebook_webhook_secret: str = os.getenv("FACEBOOK_WEBHOOK_SECRET", "")
    whatsapp_webhook_secret: str = os.getenv("WHATSAPP_WEBHOOK_SECRET", "")
    facebook_webhook_verify_token: str = os.getenv("FACEBOOK_WEBHOOK_VERIFY_TOKEN", "")
    whatsapp_webhook_verify_token: str = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
    google_cse_api_key: str = os.getenv("GOOGLE_CSE_API_KEY", "")
    google_cse_cx: str = os.getenv("GOOGLE_CSE_CX", "")
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")


settings = Settings()
