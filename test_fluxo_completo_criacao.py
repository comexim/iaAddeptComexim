"""
Teste de fluxo completo de criação de contrato via conversa
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Configuração de path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load environment
load_dotenv()

from app.agents.orchestrator import AgentOrchestrator
from app.models.user import UserPermissions

async def test_fluxo_completo():
    """Testa criação completa de contrato em múltiplas mensagens"""
    print("=" * 80)
    print("TESTE: Fluxo Completo de Criação de Contrato")
    print("=" * 80)
    
    # Criar permissões de teste
    user = UserPermissions(
        telefone="5511999999999",
        nome="Teste Contrato",
        email="teste@comexim.com.br",
        direitos=["Vendas"]
    )
    
    agent = AgentOrchestrator(user=user, session_id=user.telefone)
    
    # Conversação simulada
    mensagens = [
        "Quero criar um contrato",
        "Cliente Bernhard Schmidt, quantidade 36000 kg, condição FOB",
        "Embarque em abril de 2026, modalidade parcial, embalagem 5C",
    ]
    
    for i, msg in enumerate(mensagens, 1):
        print(f"\n{'=' * 80}")
        print(f"👤 MENSAGEM {i}: {msg}")
        print(f"{'=' * 80}\n")
        
        try:
            resposta = await agent.process_message(msg)
            print(f"🤖 RESPOSTA:\n{resposta}\n")
            
        except Exception as e:
            print(f"❌ Erro: {e}\n")
            import traceback
            traceback.print_exc()
            break
    
    print("=" * 80)
    print("✅ Teste finalizado")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_fluxo_completo())
