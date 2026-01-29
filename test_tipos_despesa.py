"""
Testa agregação de todos os tipos de despesa
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_tipos_despesa():
    """Testa agregação por tipo de despesa"""
    print("=" * 80)
    print("TESTE - Tipos de despesa")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Testando: 'Quais os tipos de despesa que temos?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais os tipos de despesa que temos?"

        result = sql_tools._pesquisa_despesa_venda(contrato=None)

        print(f"[OK] Retornou resultado\n")

        # Converte resultado para verificar
        if isinstance(result, list):
            print(f"Total de tipos retornados: {len(result)}\n")
            print("Top 10 tipos de despesa:")
            print("-" * 80)
            for i, item in enumerate(result[:10], 1):
                tipo = item.get("tipo_despesa")
                reais = item.get("total_reais", 0)
                dolar = item.get("total_dolar", 0)
                qtd = item.get("quantidade", 0)
                contratos = item.get("numero_contratos", 0)

                print(f"{i}. {tipo}")
                print(f"   Reais: R$ {reais:,.2f}")
                if dolar > 0:
                    print(f"   Dólar: US$ {dolar:,.2f}")
                print(f"   Quantidade: {qtd} despesas em {contratos} contratos")
                print()
        else:
            print("Resultado não é uma lista!")
            print(result)

        print("\n3. VALIDAÇÃO COM RESPOSTA DA IA:")
        print("-" * 80)
        print("Verificando se os valores batem...")

        # Resposta esperada da IA (alguns exemplos)
        esperado = {
            "Capatazia": {"reais": 11838051.82, "dolar": 34450.33},
            "Pre Stacking": {"reais": 4246474.39, "dolar": 0},
            "Freight": {"reais": 4097617.46, "dolar": 653469.10},
            "Desembaraço Aduaneiro": {"reais": 423855.78, "dolar": 999.72},
            "Despesa com Fumigação": {"reais": 1222812.43, "dolar": 0}
        }

        if isinstance(result, list):
            for item in result:
                tipo = item.get("tipo_despesa")
                if tipo in esperado:
                    reais_real = item.get("total_reais", 0)
                    dolar_real = item.get("total_dolar", 0)
                    reais_esperado = esperado[tipo]["reais"]
                    dolar_esperado = esperado[tipo]["dolar"]

                    match_reais = abs(reais_real - reais_esperado) < 1
                    match_dolar = abs(dolar_real - dolar_esperado) < 1

                    if match_reais and match_dolar:
                        print(f"✓ {tipo}: OK")
                    else:
                        print(f"✗ {tipo}: ERRO")
                        print(f"  Esperado: R$ {reais_esperado:,.2f} / US$ {dolar_esperado:,.2f}")
                        print(f"  Recebido: R$ {reais_real:,.2f} / US$ {dolar_real:,.2f}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_tipos_despesa()
