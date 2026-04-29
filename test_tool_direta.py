"""
Teste DIRETO da tool de criação de contrato
Sem passar pelo orchestrator (sem risk de chamar outras tools)
"""

import asyncio
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.ada_tools import ada_tools


async def main():
    """Testa DIRETO a tool de criar contrato"""
    
    print("=" * 80)
    print("TESTE DIRETO - TOOL CRIAR CONTRATO")
    print("=" * 80)
    
    # Cenário 1: Nenhum dado
    print("\n📋 Cenário 1: Usuário não forneceu NENHUM dado")
    print("-" * 80)
    resultado1 = ada_tools.criar_contrato_venda()
    print(f"Resposta:\n{resultado1}")
    
    # Cenário 2: Usuário forneceu apenas nome do cliente
    print("\n" + "=" * 80)
    print("📋 Cenário 2: Usuário forneceu apenas NOME")
    print("-" * 80)
    resultado2 = ada_tools.criar_contrato_venda(nome_cliente="Nestlé")
    print(f"Resposta:\n{resultado2}")
    
    # Cenário 3: Usuário forneceu 3 dados
    print("\n" + "=" * 80)
    print("📋 Cenário 3: Usuário forneceu nome, quantidade e condição")
    print("-" * 80)
    resultado3 = ada_tools.criar_contrato_venda(
        nome_cliente="JDE",
        quantidade_kg=60000,
        condicao_entrega="FOB"
    )
    print(f"Resposta:\n{resultado3}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
