"""
Teste para verificar funcionalidade de LongShort
Testa diferentes cenários de consulta com filiais
"""
import asyncio
import sys
sys.path.insert(0, 'c:\\Users\\pedro\\Desktop\\agente-comexim')

from app.models.user import UserPermissions
from app.agents.orchestrator import AgentOrchestrator

async def test_longshort():
    """Testa consultas de LongShort com diferentes filiais"""

    # Simula usuário Marco (tem todas as permissões)
    user = UserPermissions(
        telefone="11915901500",
        nome="Marco Aurélio (TESTE)",
        email="marco.souza@comexim.com.br",
        direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento"]
    )

    session_id = "11915901500_test_longshort"

    print("=" * 80)
    print("TESTE: Funcionalidade LongShort")
    print("=" * 80)

    # Cria orchestrator
    orchestrator = AgentOrchestrator(user, session_id)

    # Teste 1: Consulta sem especificar filial (deve usar FILIAIS - totalizador)
    print("\n[TESTE 1] Qual a posição do LongShort?")
    print("-" * 80)
    try:
        resposta1 = await orchestrator.process_message("Qual a posição do LongShort?")
        print(f"[RESPOSTA 1]:\n{resposta1}")
        print("[OK] Teste 1 concluído")
    except Exception as e:
        print(f"[ERRO] Teste 1: {e}")
        import traceback
        traceback.print_exc()

    # Teste 2: Consulta com filial CUSA
    print("\n\n[TESTE 2] Qual o total do estoque do longshort da CUSA?")
    print("-" * 80)
    try:
        resposta2 = await orchestrator.process_message("Qual o total do estoque do longshort da CUSA?")
        print(f"[RESPOSTA 2]:\n{resposta2}")
        print("[OK] Teste 2 concluído")
    except Exception as e:
        print(f"[ERRO] Teste 2: {e}")
        import traceback
        traceback.print_exc()

    # Teste 3: Consulta com filial CEU (usando nome completo)
    print("\n\n[TESTE 3] Qual o total de vendas exportáveis da comexim europa?")
    print("-" * 80)
    try:
        resposta3 = await orchestrator.process_message("Qual o total de vendas exportáveis da comexim europa?")
        print(f"[RESPOSTA 3]:\n{resposta3}")
        print("[OK] Teste 3 concluído")
    except Exception as e:
        print(f"[ERRO] Teste 3: {e}")
        import traceback
        traceback.print_exc()

    # Teste 4: Consulta com filial COBRA (usando termo "brasil")
    print("\n\n[TESTE 4] Qual o total de compras de mercado interno da comexim brasil?")
    print("-" * 80)
    try:
        resposta4 = await orchestrator.process_message("Qual o total de compras de mercado interno da comexim brasil?")
        print(f"[RESPOSTA 4]:\n{resposta4}")
        print("[OK] Teste 4 concluído")
    except Exception as e:
        print(f"[ERRO] Teste 4: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Todos os testes finalizados")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_longshort())
