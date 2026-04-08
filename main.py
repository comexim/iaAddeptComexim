"""
Agente Comexim IA - Aplicação Principal
Sistema inteligente de consulta ERP via WhatsApp
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import sql_client
from app.core.redis_client import redis_client
from app.api.webhook import router as webhook_router
from app.services.scheduler import criar_scheduler

# Configuração de logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agente-comexim.log")
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    logger.info("🚀 Iniciando Agente Comexim IA...")
    logger.info(f"Ambiente: {settings.env}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Model: {settings.ai_model}")

    # Testa conexões
    logger.info("Testando conexão SQL Server...")
    if sql_client.test_connection():
        logger.info("✅ SQL Server conectado")
    else:
        logger.error("❌ Falha ao conectar SQL Server")

    # Inicia scheduler de relatórios agendados
    scheduler = criar_scheduler()
    scheduler.start()
    logger.info("✅ Scheduler de relatórios iniciado (verifica a cada hora)")

    logger.info("✅ Agente Comexim IA iniciado com sucesso!")

    yield

    # Shutdown
    logger.info("🔄 Encerrando Agente Comexim IA...")
    scheduler.shutdown(wait=False)
    sql_client.close()
    await redis_client.close()
    logger.info("✅ Agente Comexim IA encerrado")


# Cria aplicação FastAPI
app = FastAPI(
    title="Agente Comexim IA",
    description="Sistema inteligente de consulta ERP via WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra rotas
app.include_router(webhook_router, tags=["Webhook"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Agente Comexim IA",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.env
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
