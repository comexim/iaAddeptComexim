"""
Teste para verificar problema de contexto com contratos
Simula o caso:
1. "Quem é o vendedor do contrato 228/25?" - Funciona
2. "Preciso do total e da quantidade de sacas" - Dá erro
"""
import asyncio
import sys
sys.path.insert(0, 'c:\\Users\\pedro\\Desktop\\agente-comexim')

from app.models.user import UserPermissions
from app.agents.orchestrator import AgentOrchestrator

async def test_contexto_contrato():
    """Testa consulta com contexto de contrato anterior"""

    # Simula usuário Marco (tem todas as permissões)
    user = UserPermissions(
        telefone="11915901500",
        nome="Marco Aurélio (TESTE)",
        email="marco.souza@comexim.com.br",
        direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento"]
    )

    session_id = "11915901500_test_contexto"

    print("=" * 80)
    print("TESTE: Contexto de Contrato")
    print("=" * 80)

    # Cria orchestrator
    orchestrator = AgentOrchestrator(user, session_id)

    # Primeira pergunta: menciona contrato explicitamente
    print("\n[PERGUNTA 1] Quem é o vendedor do contrato 228/25?")
    print("-" * 80)
    try:
        resposta1 = await orchestrator.process_message("Quem é o vendedor do contrato 228/25?")
        print(f"[RESPOSTA 1]:\n{resposta1[:500]}...")
        print("[OK] Primeira pergunta funcionou")
    except Exception as e:
        print(f"[ERRO] Primeira pergunta: {e}")
        import traceback
        traceback.print_exc()

    # Segunda pergunta: NÃO menciona contrato (depende de contexto)
    print("\n\n[PERGUNTA 2] Preciso do total e da quantidade de sacas")
    print("-" * 80)
    try:
        resposta2 = await orchestrator.process_message("Preciso do total e da quantidade de sacas")
        print(f"[RESPOSTA 2]:\n{resposta2[:500]}...")
        if "erro" in resposta2.lower() or "desculpe" in resposta2.lower():
            print("[ERRO] Segunda pergunta deu erro!")
        else:
            print("[OK] Segunda pergunta funcionou")
    except Exception as e:
        print(f"[ERRO] Segunda pergunta: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Teste finalizado")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_contexto_contrato())
