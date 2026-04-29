"""
Teste de CONVERSA REAL com envio para API ADA.
Simula um usuário falando naturalmente com os dados do contrato JDE.
SEM mocks — envia de verdade para a API e mostra a resposta.

USO:
    py test_conversa_real_api.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S"
)

from app.agents.orchestrator import AgentOrchestrator
from app.models.user import UserPermissions


async def main():
    print("\n" + "#" * 80)
    print("# TESTE CONVERSA REAL: Criação de contrato JDE (envio real para API)")
    print("#" * 80)

    user = UserPermissions(
        telefone="+5511999999999",
        nome="Lucas",
        email="lucas@comexim.com.br",
        direitos=["Vendas", "Financeiro"]
    )

    session_id = f"test_real_{uuid.uuid4().hex[:8]}"

    # Limpa estado pendente
    from app.agents.ada_tools import create_ada_tools
    ada_cleanup = create_ada_tools(session_id=session_id)
    ada_cleanup._clear_pending_data()

    orchestrator = AgentOrchestrator(user=user, session_id=session_id)

    # ══════════════════════════════════════════════════════════════════
    # Conversa simulada — dados do JSON escritos como um usuário falaria
    # ══════════════════════════════════════════════════════════════════
    mensagens = [
        # Turno 1: Pede para criar e já passa os dados principais
        (
            "Quero adicionar um contrato de venda. Cliente JDE, código EX288915O loja 0001. "
            "São 38400 kg, qualidade GRD, condição de entrega EMB, embarque em 06/2026."
        ),

        # Turno 2: Responde o que a IA pedir — pagamento, moeda, tipo, peso, embalagem
        (
            "Pagamento INT, moeda USD, tipo de contrato ESCC, condição de peso NDW. "
            "Embalagem código 00316 com 40 unidades, 1 container, 0 pallets. "
            "Não exige EUDR e não precisa de amostra pré-embarque."
        ),

        # Turno 3: Fixação e comissão
        (
            "A fixação é de 300 sacas para 07/2026, tipo preço A fixar, fixador E, "
            "tipo valor C, referência bolsa NY 400. "
            "A comissão é para o agente INPS00030 loja 0001, percentual 0.5%, tipo LIB."
        ),
    ]

    for i, msg in enumerate(mensagens, 1):
        print(f"\n{'=' * 80}")
        print(f"  TURNO {i}")
        print(f"{'=' * 80}")
        print(f"\n👤 USUÁRIO:\n{msg}\n")
        print("⏳ Processando...\n")

        try:
            resposta = await orchestrator.process_message(msg)
            print(f"🤖 IA:\n{resposta}\n")

            # Se criou com sucesso, para
            if any(x in resposta.lower() for x in ["sucesso", "criado", "contrato"]) and \
               any(x in resposta for x in ["/26", "/25", "número"]):
                print("✅ CONTRATO CRIADO COM SUCESSO!")
                break

        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            break

    # Limpa
    ada_cleanup._clear_pending_data()
    try:
        orchestrator.message_history.clear()
    except:
        pass

    print(f"\n{'=' * 80}")
    print("FIM DO TESTE")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    asyncio.run(main())
