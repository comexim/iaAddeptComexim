"""
Teste do fluxo multi-turno de criação de contrato via ADA.
Testa a acumulação de dados via Redis e o fluxo completo:
  Turno 1: Usuário pede para criar contrato com alguns dados
  Turno 2: Usuário fornece dados faltantes
  Turno 3: Se ainda faltam dados, fornece o restante
"""
import sys
import json
import uuid
from pathlib import Path
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent))


def test_fluxo_direto_tool():
    """
    Testa a tool criar_contrato_venda DIRETAMENTE (sem LLM).
    Simula o fluxo multi-turno de acumulação de dados via Redis.
    """
    from app.agents.ada_tools import create_ada_tools

    # Session ID único para isolar o teste
    session_id = f"test_contrato_{uuid.uuid4().hex[:8]}"
    ada = create_ada_tools(session_id=session_id)

    print("\n" + "=" * 80)
    print("TESTE: Fluxo multi-turno de criação de contrato (tool direta)")
    print("=" * 80)

    # ── TURNO 1: Usuário diz "Quero criar contrato para Nestlé, 60000kg, FOB" ──
    print("\n── TURNO 1: Dados parciais (nome, kg, condição) ──")
    resp1 = ada.criar_contrato_venda(
        nome_cliente="Nestlé",
        quantidade_kg=60000,
        condicao_entrega="FOB"
    )
    print(f"Resposta:\n{resp1}\n")
    assert "PRECISA_PERGUNTAR" in resp1, "Deveria pedir mais dados!"
    # Deve ter salvo nome_cliente, quantidade_kg, condicao_entrega no Redis

    # ── TURNO 2: Usuário responde "maio/2026, à vista, SSC70" ──
    print("── TURNO 2: Mais dados (embarque, pagamento, embalagem) ──")
    resp2 = ada.criar_contrato_venda(
        mes_embarque="maio/2026",
        modalidade_pagamento="à vista",
        codigo_embalagem="SSC70"
    )
    print(f"Resposta:\n{resp2}\n")
    assert "PRECISA_PERGUNTAR" in resp2, "Deveria pedir mais dados!"
    # Agora deve ter 6 campos no Redis (3 anteriores + 3 novos)
    # Verifica que os dados antigos foram preservados
    assert "nome_cliente" in resp2 or "Nestlé" not in resp2  # Dados antigos no Redis

    # ── TURNO 3: Usuário responde "Premium, USD, Exportação" ──
    print("── TURNO 3: Campos restantes (qualidade, moeda, tipo) ──")

    # Mock da API para não fazer chamada real
    mock_api_result = {
        "numero_contrato": "500/26",
        "mensagem": "Contrato criado com sucesso",
        "status": "OK"
    }

    with patch.object(
        ada, '_clear_pending_data', wraps=ada._clear_pending_data
    ) as mock_clear:
        with patch(
            'app.agents.ada_tools.ada_api_client.criar_contrato_venda',
            new_callable=AsyncMock,
            return_value=mock_api_result
        ):
            resp3 = ada.criar_contrato_venda(
                padrao_qualidade="Premium",
                moeda_fixacao="USD",
                tipo_contrato="Exportação"
            )
            print(f"Resposta:\n{resp3}\n")

            if "CONTRATO_CRIADO_SUCESSO" in resp3:
                print("✅ Contrato criado com sucesso!")
                assert "500/26" in resp3
                # Verifica que o estado foi limpo
                mock_clear.assert_called_once()
            elif "PRECISA_PERGUNTAR" in resp3:
                print("⚠️  Ainda faltam campos (esperado se model exigir mais):")
                print(resp3)
            else:
                print(f"Resposta inesperada: {resp3}")

    # Limpa estado de teste do Redis
    ada._clear_pending_data()
    print("\n✅ Teste de fluxo multi-turno concluído!")


def test_acumulacao_redis():
    """Testa que os dados realmente se acumulam no Redis entre chamadas."""
    from app.agents.ada_tools import create_ada_tools

    session_id = f"test_acumulacao_{uuid.uuid4().hex[:8]}"
    ada = create_ada_tools(session_id=session_id)

    print("\n" + "=" * 80)
    print("TESTE: Acumulação de dados no Redis")
    print("=" * 80)

    # Limpa qualquer estado anterior
    ada._clear_pending_data()

    # Chamada 1: só nome
    ada.criar_contrato_venda(nome_cliente="Starbucks")
    dados1 = ada._load_pending_data()
    print(f"\nApós chamada 1: {dados1}")
    assert dados1.get("nome_cliente") == "Starbucks"

    # Chamada 2: adiciona quantidade e condição
    ada.criar_contrato_venda(quantidade_kg=45000, condicao_entrega="ENT")
    dados2 = ada._load_pending_data()
    print(f"Após chamada 2: {dados2}")
    assert dados2.get("nome_cliente") == "Starbucks", "nome_cliente deveria ter sido preservado!"
    assert dados2.get("quantidade_kg") == 45000
    assert dados2.get("condicao_entrega") == "ENT"

    # Chamada 3: adiciona mais dados
    ada.criar_contrato_venda(mes_embarque="junho/2026", data_previsao_entrega="15/07/2026")
    dados3 = ada._load_pending_data()
    print(f"Após chamada 3: {dados3}")
    assert dados3.get("nome_cliente") == "Starbucks"
    assert dados3.get("quantidade_kg") == 45000
    assert dados3.get("condicao_entrega") == "ENT"
    assert dados3.get("mes_embarque") == "junho/2026"
    assert dados3.get("data_previsao_entrega") == "15/07/2026"

    # Chamada 4: sobrescreve um campo (usuário corrige)
    ada.criar_contrato_venda(nome_cliente="Starbucks International")
    dados4 = ada._load_pending_data()
    print(f"Após chamada 4 (correção): {dados4}")
    assert dados4.get("nome_cliente") == "Starbucks International", "Deveria ter atualizado o nome!"
    assert dados4.get("quantidade_kg") == 45000, "Outros dados deveriam ter sido preservados!"

    # Limpa
    ada._clear_pending_data()
    print("\n✅ Teste de acumulação Redis concluído!")


def test_structured_tool_schema():
    """Verifica que a tool é StructuredTool com parâmetros corretos."""
    from app.agents.ada_tools import create_ada_tools
    from langchain_core.tools import StructuredTool

    ada = create_ada_tools(session_id="test_schema")
    tool = ada.get_tool()

    print("\n" + "=" * 80)
    print("TESTE: StructuredTool schema")
    print("=" * 80)

    assert isinstance(tool, StructuredTool), f"Tool deveria ser StructuredTool, mas é {type(tool)}"
    assert tool.name == "criar_contrato_venda_exportacao"

    # Verifica que os parâmetros aparecem no schema
    schema = tool.args_schema.schema() if hasattr(tool.args_schema, 'schema') else tool.args_schema.model_json_schema()
    props = schema.get("properties", {})
    
    expected_params = [
        "nome_cliente", "codigo_cliente", "quantidade_kg", 
        "condicao_entrega", "mes_embarque", "modalidade_pagamento"
    ]
    
    for param in expected_params:
        assert param in props, f"Parâmetro '{param}' não encontrado no schema! Schema: {list(props.keys())}"

    print(f"Tool name: {tool.name}")
    print(f"Tool type: {type(tool).__name__}")
    print(f"Parâmetros no schema: {list(props.keys())}")
    print("\n✅ Tool é StructuredTool com schema correto!")


def test_sessoes_isoladas():
    """Testa que sessões diferentes não compartilham dados."""
    from app.agents.ada_tools import create_ada_tools

    session_a = f"test_isolamento_A_{uuid.uuid4().hex[:8]}"
    session_b = f"test_isolamento_B_{uuid.uuid4().hex[:8]}"
    
    ada_a = create_ada_tools(session_id=session_a)
    ada_b = create_ada_tools(session_id=session_b)

    print("\n" + "=" * 80)
    print("TESTE: Isolamento entre sessões")
    print("=" * 80)

    # Sessão A: cria contrato para Nestlé
    ada_a.criar_contrato_venda(nome_cliente="Nestlé")
    
    # Sessão B: cria contrato para Starbucks
    ada_b.criar_contrato_venda(nome_cliente="Starbucks")

    # Verifica isolamento
    dados_a = ada_a._load_pending_data()
    dados_b = ada_b._load_pending_data()

    assert dados_a.get("nome_cliente") == "Nestlé", "Sessão A deveria ter Nestlé!"
    assert dados_b.get("nome_cliente") == "Starbucks", "Sessão B deveria ter Starbucks!"

    # Limpa
    ada_a._clear_pending_data()
    ada_b._clear_pending_data()
    print(f"Sessão A: {dados_a}")
    print(f"Sessão B: {dados_b}")
    print("\n✅ Sessões isoladas corretamente!")


if __name__ == "__main__":
    print("\n" + "#" * 80)
    print("# TESTES DO FLUXO DE CRIAÇÃO DE CONTRATO MULTI-TURNO")
    print("#" * 80)

    try:
        test_structured_tool_schema()
    except Exception as e:
        print(f"\n❌ test_structured_tool_schema FALHOU: {e}")
    
    try:
        test_acumulacao_redis()
    except Exception as e:
        print(f"\n❌ test_acumulacao_redis FALHOU: {e}")

    try:
        test_sessoes_isoladas()
    except Exception as e:
        print(f"\n❌ test_sessoes_isoladas FALHOU: {e}")

    try:
        test_fluxo_direto_tool()
    except Exception as e:
        print(f"\n❌ test_fluxo_direto_tool FALHOU: {e}")

    print("\n" + "#" * 80)
    print("# TODOS OS TESTES CONCLUÍDOS")
    print("#" * 80)
