"""
Teste com IA - APENAS tool de criar contrato (sem SQL tools)
"""

import asyncio
import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from app.core.config import settings
from app.agents.ada_tools import ada_tools


async def main():
    """Testa IA com APENAS a tool de criar contrato"""
    
    # LLM
    llm = ChatOpenAI(
        model=settings.ai_model,
        temperature=0.1,
        api_key=settings.openai_api_key
    )
    
    # APENAS tool de criar contrato
    tools = [ada_tools.get_tool()]
    
    # System prompt simples
    system_prompt = """Você é um assistente para criação de contratos.

IMPORTANTE: Quando o usuário disser "quero criar um contrato", você DEVE:
1. IMEDIATAMENTE chamar a tool criar_contrato_venda_exportacao() SEM argumentos
2. A tool vai retornar "PRECISA_PERGUNTAR:" com lista de campos
3. Você pergunta os campos ao usuário
4. Quando usuário responder, chama a tool novamente com os dados fornecidos
5. Repete até contrato ser criado

NUNCA invente dados ou responda sem chamar a tool primeiro!"""
    
    # Criar agente
    agent = create_react_agent(llm, tools, state_modifier=system_prompt)
    
    # Mensagem do usuário
    mensagem = "Quero criar um contrato"
    
    print("=" * 80)
    print(f"👤 USUÁRIO: {mensagem}")
    print("=" * 80)
    print("\n🤖 IA: Processando...\n")
    
    # Processar
    response = await agent.ainvoke({"messages": [HumanMessage(content=mensagem)]})
    
    # Pegar última mensagem
    ultima_msg = response["messages"][-1].content
    
    print("-" * 80)
    print(f"📨 RESPOSTA:\n\n{ultima_msg}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
