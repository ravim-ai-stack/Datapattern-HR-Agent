"""Application settings, loaded from environment variables / the .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    system_sender_email: str = ""
    databricks_host: str = ""
    databricks_token: str = ""
    databricks_model: str = "databricks-meta-llama-3-3-70b-instruct"
    port: int = 5050
    log_level: str = "INFO"


settings = Settings()

# Static assets and letter templates shipped with the app
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
STATIC_DIR = os.path.join(SRC_DIR, "static")
LOGO_PATH = os.path.join(STATIC_DIR, "img", "datapattern-logo.png")
SIGNATURE_PATH = os.path.join(STATIC_DIR, "img", "indhirajith-signature.jpeg")
CERTIFICATE_TEMPLATE_PATH = os.path.join(STATIC_DIR, "img", "DataPattern Internship Certificate_.png")
TEMPLATE_DIR = os.path.join(STATIC_DIR, "letter_templates")
TEMPLATES_FOLDER = os.path.join(SRC_DIR, "templates")
