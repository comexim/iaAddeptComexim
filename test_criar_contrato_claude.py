"""
Teste simples: ver como IA responde quando usuário pede para criar contrato sem especificar dados
USA CLAUDE (limite maior de tokens)
"""

import asyncio
import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

# FORÇA usar Claude para este teste
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["AI_MODEL"] = "claude-sonnet-4-20250514"

from app.agents.orchestrator import AgentOrchestrator
from app.models.user import UserPermissions
from app.core.redis_client import redis_client


async def main():
    """Testa como a IA responde a pedido genérico de criação de contrato"""
    
    # Criar usuário fake
    user = UserPermissions(
        telefone="+5511999999999",
        nome="Teste",
        email="teste@teste.com",
        direitos=["Financeiro", "Vendas"]
    )
    
    # Session ID ÚNICO para não carregar histórico anterior
    import uuid
    session_id = f"test_contrato_claude_{uuid.uuid4().hex[:8]}"
    
    # Limpar qualquer cache Redis desta sessão
    print(f"Limpando cache da sessão {session_id}...")
    try:
        redis_client.delete(f"conversation:{session_id}")
        redis_client.delete(f"context:{session_id}")
    except:
        pass
    
    # Criar orchestrator
    print(f"Inicializando agente com Claude Sonnet 4...")
    orchestrator = AgentOrchestrator(user=user, session_id=session_id)
    
    # Mensagem genérica
    mensagem = "Quero criar um contrato"
    
    print("\n" + "=" * 80)
    print(f"👤 USUÁRIO: {mensagem}")
    print("=" * 80)
    print("\n🤖 AGENTE (Claude): Processando...\n")
    
    # Processar
    resposta = await orchestrator.process_message(mensagem)
    
    print("-" * 80)
    print(f"📨 RESPOSTA:\n\n{resposta}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
