"""
Validação: Quanto tenho a pagar de compra de café? (ATUALIZADA)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida resposta da IA sobre compra de café"""
    print("=" * 80)
    print("VALIDACAO - Quanto tenho a pagar de compra de café? (ATUALIZADA)")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA (NOVA):")
        print("-" * 80)
        valor_ia_total = 552529231.65
        print(f"Total: R$ {valor_ia_total:,.2f}")
        print("\nTop 5 fornecedores de compra de café:")

        fornecedores_ia = {
            "COOP. TRES PONTAS": 19567999.98,
            "COCAPEC - FRANCA": 10524325.00,
            "COMPANHIA NACIONAL DE ABASTECIMENTO": 8774669.38,
            "COOPROESTE": 8160900.00,
            "COFFEA IMPORTACAO": 7392407.42,
        }

        for i, (nome, valor) in enumerate(fornecedores_ia.items(), 1):
            print(f"{i}. {nome}: R$ {valor:,.2f}")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca todas as contas a pagar
        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)
        print(f"Total de registros SQL (todos): {len(result) if result else 0}")

        if result:
            # Filtra por natureza relacionada a café
            naturezas_cafe = ["COMPRA DE CAFE BENEFICIADO", "CAFE"]

            cafe_titulos = []
            for r in result:
                natureza = str(r.get("natureza", "")).upper()
                if any(n.upper() in natureza for n in naturezas_cafe) or "CAFE" in natureza:
                    cafe_titulos.append(r)

            print(f"Títulos com natureza relacionada a café: {len(cafe_titulos)}")

            # Agrega por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})
            total_cafe = 0

            for r in cafe_titulos:
                fornecedor = r.get("fornecedor", "").strip() or "SEM FORNECEDOR"
                valor = r.get("valor", 0)

                if valor is None:
                    valor = 0
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_fornecedor[fornecedor]["valor"] += valor
                por_fornecedor[fornecedor]["quantidade"] += 1
                total_cafe += valor

            print(f"Total a pagar em COMPRA DE CAFÉ: R$ {total_cafe:,.2f}")

            # Top 10
            print("\n" + "=" * 80)
            print("TOP 10 FORNECEDORES (COMPRA DE CAFÉ):")
            print("=" * 80)

            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
                nome_curto = fornecedor[:40]
                print(f"{i:2}. {nome_curto:40} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:3} títulos)")

            # Valida fornecedores mencionados pela IA
            print("\n" + "=" * 80)
            print("VALIDACAO DOS FORNECEDORES MENCIONADOS PELA IA:")
            print("=" * 80)

            matches = 0
            for nome_ia, valor_ia in fornecedores_ia.items():
                encontrado = False
                for fornecedor, dados in por_fornecedor.items():
                    if nome_ia.upper() in fornecedor.upper() or fornecedor.upper() in nome_ia.upper():
                        diferenca = abs(dados['valor'] - valor_ia)
                        if diferenca < 100:
                            print(f"[OK] {nome_ia}: R$ {dados['valor']:,.2f} (correto)")
                            matches += 1
                        else:
                            percentual = (diferenca / valor_ia * 100) if valor_ia > 0 else 0
                            print(f"[X] {nome_ia}: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {dados['valor']:,.2f} (dif: {percentual:.1f}%)")
                        encontrado = True
                        break
                if not encontrado:
                    print(f"[X] {nome_ia}: NAO ENCONTRADO")

            # Valida total
            print("\n" + "=" * 80)
            print("VALIDACAO GERAL:")
            print("=" * 80)

            diferenca_total = abs(total_cafe - valor_ia_total)
            percentual = (diferenca_total / valor_ia_total * 100) if valor_ia_total > 0 else 0

            print(f"IA disse: R$ {valor_ia_total:,.2f}")
            print(f"Banco (café): R$ {total_cafe:,.2f}")

            if diferenca_total < 1000:
                print(f"\n[OK] Total de compra de café: CORRETO!")
            else:
                print(f"\n[X] Total não bate: diferença de R$ {diferenca_total:,.2f} ({percentual:.1f}%)")

            print(f"\nTotal de fornecedores validados: {matches}/{len(fornecedores_ia)}")

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_validacao()
