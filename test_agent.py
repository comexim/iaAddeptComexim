import asyncio
from app.agents.orchestrator import AgentOrchestrator
from app.models.user import User, UserPermissions

async def test_agent():
    print("[INFO] Testando agente orquestrador...\n")

    # Criar usuario de teste
    user = User(
        telefone="5511972390860",
        nome="Pedro Silva",
        email="pedro.silva@comexim.com.br",
        permissions=UserPermissions(direitos=["Financeiro", "Vendas", "Estoque"])
    )

    # Criar orquestrador
    orchestrator = AgentOrchestrator(session_id=user.telefone, user=user)

    # Teste 1: Consulta simples
    print("[TEST 1] Consulta de saldo bancario...")
    response = await orchestrator.process_message("Qual o saldo bancario atual?")
    print(f"Resposta: {response[:200]}...\n")

    # Teste 2: Consulta com filtro
    print("[TEST 2] Consulta de vendas de dezembro...")
    response = await orchestrator.process_message("Mostre as vendas de dezembro de 2024")
    print(f"Resposta: {response[:200]}...\n")

    # Teste 3: Feedback de preferencia
    print("[TEST 3] Feedback 'diminua a mensagem'...")
    response = await orchestrator.process_message("diminua a mensagem")
    print(f"Resposta: {response[:200]}...\n")

    # Teste 4: Verificar se preferencia foi aplicada
    print("[TEST 4] Nova consulta (deve ser mais curta)...")
    response = await orchestrator.process_message("Qual o estoque de produtos?")
    print(f"Resposta: {response[:200]}...\n")

    print("[OK] Testes do agente concluidos!")

if __name__ == "__main__":
    asyncio.run(test_agent())
