"""
Testa query sobre valor médio por linha em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_linha_jan2026():
    """Testa query sobre linha de café"""
    print("=" * 80)
    print("TESTE - VALOR MÉDIO POR LINHA EM JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Cria objeto fake de user
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Query: 'Qual o valor médio por saca de cada linha de café em janeiro 2026?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Qual o valor médio por saca de cada linha de café em janeiro 2026?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")
        print(f"DEBUG - Tamanho: {len(result) if isinstance(result, list) else len(str(result))}")

        # Verifica se é lista ou string JSON
        if isinstance(result, str):
            print(f"DEBUG - Primeiros 500 chars: {result[:500]}\n")
            # Salva resultado completo em arquivo
            with open("test_linha_result.txt", "w", encoding="utf-8") as f:
                f.write(result)
            print("Resultado completo salvo em: test_linha_result.txt\n")

            if not result or result.strip() == "":
                print("[ERRO] Resultado vazio!")
                return
            if result.startswith("PRECISA_"):
                print(f"[ERRO] {result}")
                return

            # Extrai JSON da resposta formatada
            if "[" in result:
                json_start = result.index("[")
                json_end = result.rindex("]") + 1
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
            else:
                data = json.loads(result)
        else:
            data = result

        print(f"3. Total de registros retornados: {len(data)}\n")

        # Verifica se tem campo "linha" ou "linhas"
        print("4. VERIFICANDO CAMPOS NO PRIMEIRO REGISTRO:")
        print("-" * 80)

        if data:
            primeiro = data[0]
            print(f"\nPrimeiro registro:")
            for key in sorted(primeiro.keys()):
                value = primeiro[key]
                if isinstance(value, (list, str)) and len(str(value)) > 100:
                    print(f"  - {key}: {str(value)[:100]}...")
                else:
                    print(f"  - {key}: {value}")

            # Procura por campos relacionados a "linha"
            print("\n5. CAMPOS RELACIONADOS A 'LINHA':")
            print("-" * 80)
            for key in primeiro.keys():
                if "linha" in key.lower():
                    print(f"  ✓ Campo encontrado: {key} = {primeiro[key]}")

        # Tenta agregar por linha manualmente
        print("\n\n6. AGREGANDO POR LINHA (MANUAL):")
        print("-" * 80)

        por_linha = {}
        for item in data:
            linhas = item.get("linhas", [])
            valor = item.get("total_valor", 0)
            sacas = item.get("total_sacas", 0)

            if not linhas:
                linhas = ["SEM LINHA"]

            for linha in linhas:
                if linha not in por_linha:
                    por_linha[linha] = {"valor": 0, "sacas": 0}
                por_linha[linha]["valor"] += valor
                por_linha[linha]["sacas"] += sacas

        print(f"\nTotal de linhas encontradas: {len(por_linha)}\n")

        for i, (linha, totais) in enumerate(sorted(por_linha.items(), key=lambda x: x[1]["valor"], reverse=True), 1):
            media_saca = totais["valor"] / totais["sacas"] if totais["sacas"] > 0 else 0
            print(f"{i}. {linha}:")
            print(f"   Valor total: R$ {totais['valor']:,.2f}")
            print(f"   Sacas: {totais['sacas']:,.2f}")
            print(f"   Média por saca: R$ {media_saca:,.2f}")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_linha_jan2026()
