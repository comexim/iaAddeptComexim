"""
Teste de CONVERSA real multi-turno de criação de contrato.
Passa pelo AgentOrchestrator completo (LLM + tools + Redis).

Fluxo testado:
  1. Usuário: "Quero criar um contrato para Nestlé, 60000kg, FOB"
  2. IA: pergunta campos faltantes
  3. Usuário: responde com dados faltantes
  4. IA: confirma criação ou pede mais dados
"""
import asyncio
import sys
import uuid
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app.agents.orchestrator import AgentOrchestrator
from app.models.user import UserPermissions


async def test_conversa_criacao_contrato():
    """Testa conversa completa de criação de contrato pelo orquestrador"""

    print("\n" + "#" * 80)
    print("# TESTE DE CONVERSA: Criação de contrato multi-turno (via Orquestrador)")
    print("#" * 80)

    # Usuário de teste
    user = UserPermissions(
        telefone="+5511999999999",
        nome="Teste Conversa",
        email="teste@comexim.com.br",
        direitos=["Vendas", "Financeiro"]
    )

    # Session ID único para não poluir histórico
    session_id = f"test_conversa_{uuid.uuid4().hex[:8]}"

    # Limpa estado do contrato pendente no Redis
    from app.agents.ada_tools import create_ada_tools
    ada_cleanup = create_ada_tools(session_id=session_id)
    ada_cleanup._clear_pending_data()

    # Cria orquestrador
    orchestrator = AgentOrchestrator(user=user, session_id=session_id)

    # Mock da API ADA para não fazer chamada HTTP real
    mock_api_result = {
        "numero_contrato": "501/26",
        "mensagem": "Contrato criado com sucesso",
        "status": "OK"
    }

    # Mensagens da conversa simulada
    mensagens = [
        # Turno 1: Usuário pede para criar contrato com dados parciais
        "Quero criar um contrato de venda para Nestlé, 60000 kg, condição FOB",

        # Turno 2: Responde os campos faltantes que a IA deve perguntar
        "Embarque em maio de 2026, pagamento à vista, embalagem SSC70",

        # Turno 3: Responde os campos finais
        "Qualidade Premium, moeda USD, tipo exportação",
    ]

    with patch(
        'app.agents.ada_tools.ada_api_client.criar_contrato_venda',
        new_callable=AsyncMock,
        return_value=mock_api_result
    ):
        for i, msg in enumerate(mensagens, 1):
            print(f"\n{'=' * 80}")
            print(f"  TURNO {i}")
            print(f"{'=' * 80}")
            print(f"\n👤 USUÁRIO: {msg}\n")
            print("⏳ Processando...\n")

            try:
                resposta = await orchestrator.process_message(msg)
                print(f"🤖 IA: {resposta}\n")

                # Verifica resposta
                if "contrato" in resposta.lower() and ("criado" in resposta.lower() or "sucesso" in resposta.lower() or "501" in resposta):
                    print("✅ Contrato criado com sucesso na conversa!")
                    break
                elif "preciso" in resposta.lower() or "informe" in resposta.lower() or "qual" in resposta.lower():
                    print("📋 IA pediu mais dados (esperado)")
                else:
                    print(f"ℹ️  Resposta recebida, continuando...")

            except Exception as e:
                print(f"❌ Erro no turno {i}: {e}")
                import traceback
                traceback.print_exc()
                break

    # Limpa estado do teste
    ada_cleanup._clear_pending_data()
    
    # Limpa histórico de conversa do Redis
    try:
        orchestrator.message_history.clear()
    except:
        pass

    print(f"\n{'=' * 80}")
    print("✅ Teste de conversa concluído!")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    asyncio.run(test_conversa_criacao_contrato())
