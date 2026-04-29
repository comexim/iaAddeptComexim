"""
Teste completo com TODAS as tools - sessão limpa
"""

import asyncio
import sys
import os
import uuid
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from app.core.config import settings
from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions


async def main():
    """Testa IA com TODAS as tools (SQL + ADA) - sessão limpa"""
    
    # Usuário fake
    user = UserPermissions(
        telefone=f"+5511{uuid.uuid4().hex[:9]}",  # Telefone único
        nome="Teste Contrato",
        email="teste@teste.com",
        direitos=["Financeiro", "Vendas"]
    )
    
    # LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",  # Modelo mais barato e rápido para teste
        temperature=0.1,
        api_key=settings.openai_api_key
    )
    
    # TODAS as tools (7 SQL + 1 ADA)
    sql_tools = SQLTools(user=user, session_id=user.telefone)
    tools = sql_tools.get_all_tools()
    
    print(f"✅ {len(tools)} tools carregadas:")
    for tool in tools:
        print(f"  • {tool.name}")
    
    # System prompt SIMPLES (sem histórico, sem contexto pesado)
    system_prompt = """Você é um assistente da empresa Comexim.

REGRAS IMPORTANTES:
- Para CONSULTAR vendas existentes → use pesquisa_vendas
- Para CRIAR novos contratos → use criar_contrato_venda_exportacao
- NUNCA confunda consulta com criação!

Quando usuário disser "quero criar um contrato":
1. Chame criar_contrato_venda_exportacao() IMEDIATAMENTE
2. NÃO chame pesquisa_vendas
3. NÃO carregue dados desnecessários"""
    
    # Criar agente
    agent = create_react_agent(llm, tools, state_modifier=system_prompt)
    
    # Mensagem do usuário
    mensagem = "Quero criar um contrato"
    
    print("\n" + "=" * 80)
    print(f"👤 USUÁRIO: {mensagem}")
    print("=" * 80)
    print("\n🤖 IA (gpt-4o-mini): Processando...\n")
    
    # Processar
    response = await agent.ainvoke({"messages": [HumanMessage(content=mensagem)]})
    
    # Pegar última mensagem
    ultima_msg = response["messages"][-1].content
    
    print("-" * 80)
    print(f"📨 RESPOSTA:\n\n{ultima_msg}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
