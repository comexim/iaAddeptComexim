"""
Configurações centralizadas do sistema
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from dotenv import load_dotenv

# Force load .env file before anything else
load_dotenv(override=True)


class Settings(BaseSettings):
    """Configurações da aplicação"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "agente-comexim"
    env: Literal["development", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # SQL Server
    sql_server_host: str
    sql_server_port: int = 6776
    sql_server_database: str
    sql_server_user: str
    sql_server_password: str
    sql_server_driver: str = "ODBC Driver 17 for SQL Server"

    # Redis
    redis_host: str
    redis_port: int
    redis_password: str
    redis_db: int

    # Protheus API
    protheus_api_url: str
    protheus_api_token_endpoint: str = "/iaProtheus/getToken"

    # Evolution API
    evolution_api_url: str
    evolution_api_token: str
    evolution_instance_name: str = ""

    # LLM Provider
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # AI Configuration
    ai_model: str = "gpt-4o-mini"
    ai_temperature: float = 0.3
    ai_max_tokens: int = 4000
    formatter_model: str = "gpt-4o-mini"
    formatter_temperature: float = 0.0

    # Memory Configuration
    redis_memory_ttl: int = 7200  # 2 hours
    redis_memory_window: int = 10  # last 10 messages

    # Anti-Flood Configuration
    anti_flood_wait_seconds: int = 20
    message_delay_seconds: int = 3

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Features
    enable_audio_transcription: bool = True
    enable_response_formatter: bool = True
    enable_image_analysis: bool = False
    enable_preference_learning: bool = True

    @property
    def sql_server_connection_string(self) -> str:
        """Retorna connection string do SQL Server"""
        return (
            f"DRIVER={{{self.sql_server_driver}}};"
            f"SERVER={self.sql_server_host},{self.sql_server_port};"
            f"DATABASE={self.sql_server_database};"
            f"UID={self.sql_server_user};"
            f"PWD={self.sql_server_password};"
            f"TrustServerCertificate=yes;"
        )

    @property
    def redis_url(self) -> str:
        """Retorna URL do Redis"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG] redis_host={self.redis_host}, redis_port={self.redis_port}, redis_password={'***' if self.redis_password else 'None'}, redis_db={self.redis_db}")
        if self.redis_password:
            url = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            url = f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
        logger.info(f"[DEBUG] redis_url = {url}")
        return url

    @property
    def protheus_token_url(self) -> str:
        """URL completa do endpoint de token"""
        return f"{self.protheus_api_url}{self.protheus_api_token_endpoint}"


# Instância global de configurações
settings = Settings()
