"""
Teste de criação de contrato via API ADA
"""
import asyncio
from app.agents.orchestrator import AgentOrchestrator
from app.services.auth import auth_service


async def test_criar_contrato():
    """Testa criação de contrato passo a passo"""
    print("\n" + "="*80)
    print("🧪 TESTE - CRIAÇÃO DE CONTRATO VIA API ADA")
    print("="*80 + "\n")
    
    # Autentica usuário
    telefone = "6182563956"
    user = await auth_service.authenticate_user(telefone)
    
    if not user:
        print("❌ Erro na autenticação")
        return
    
    print(f"✅ Autenticado como: {user.nome}\n")
    
    # Cria orquestrador
    orchestrator = AgentOrchestrator(user=user, session_id=telefone)
    
    print("="*80)
    print("TESTE 1: Criação de contrato COM todos os dados")
    print("="*80 + "\n")
    
    mensagem1 = """
Quero criar um contrato de venda com os seguintes dados:
- Cliente: Nestlé
- Quantidade: 60.000 kg
- Padrão de qualidade: Premium
- Modalidade de pagamento: À vista
- Quantidade de containers: 2
- Mês de embarque: maio/2026
- Condição de entrega: FOB
- Moeda de fixação: USD
- Tipo de contrato: Exportação
"""
    
    print(f"💬 Mensagem:\n{mensagem1}\n")
    print("⏳ Processando...\n")
    
    response1 = await orchestrator.process_message(mensagem1)
    print(f"🤖 Resposta:\n{response1}\n")
    
    print("\n" + "="*80)
    print("TESTE 2: Criação de contrato SEM dados obrigatórios (IA deve perguntar)")
    print("="*80 + "\n")
    
    mensagem2 = """
Quero criar um novo contrato de venda
"""
    
    print(f"💬 Mensagem:\n{mensagem2}\n")
    print("⏳ Processando...\n")
    
    response2 = await orchestrator.process_message(mensagem2)
    print(f"🤖 Resposta:\n{response2}\n")
    
    # Se a IA pediu dados, vamos fornecer
    if "preciso" in response2.lower() or "falta" in response2.lower():
        print("\n" + "-"*80)
        print("A IA solicitou mais dados. Fornecendo...")
        print("-"*80 + "\n")
        
        mensagem3 = """
O cliente é Starbucks, quantidade é 45.000 kg, condição de entrega é FOB
"""
        
        print(f"💬 Mensagem:\n{mensagem3}\n")
        print("⏳ Processando...\n")
        
        response3 = await orchestrator.process_message(mensagem3)
        print(f"🤖 Resposta:\n{response3}\n")
    
    print("\n" + "="*80)
    print("TESTE 3: Criação de contrato COM condição ENT (requer data)")
    print("="*80 + "\n")
    
    mensagem4 = """
Criar contrato:
- Cliente: UCC
- Quantidade: 30.000 kg
- Condição de entrega: ENT
- Data de entrega: 15/06/2026
- Modalidade: À vista
"""
    
    print(f"💬 Mensagem:\n{mensagem4}\n")
    print("⏳ Processando...\n")
    
    response4 = await orchestrator.process_message(mensagem4)
    print(f"🤖 Resposta:\n{response4}\n")
    
    print("\n" + "="*80)
    print("✅ TESTE CONCLUÍDO!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_criar_contrato())
