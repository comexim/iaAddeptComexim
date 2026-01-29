"""
Valida resposta da IA sobre dezembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao_dezembro():
    """Valida dezembro 2025"""
    print("=" * 80)
    print("VALIDACAO - Dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total: R$ 70.031.396,67")
        print("Quantidade: 1.421 contas")
        print("\nTop 5 fornecedores:")
        print("1. Pedro Fernando Ferreira: R$ 6.175.955,00")
        print("2. Condominio Agropecuario Fernando Martins: R$ 4.880.830,00")
        print("3. Brascafe Comercio Exportacao e Importacao: R$ 4.206.730,00")
        print("4. Comexim - Londrina: R$ 4.070.076,00")
        print("5. Ribeiro S Cafes Comercio Importacao e Ex: R$ 3.407.500,00")
        print()

        print("3. VERIFICACAO NO BANCO:")
        print("-" * 80)
        print("Consultando: IA_ContasPagas WHERE emissao >= '20251201'")

        result = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251201"})

        if not result:
            print("[ERRO] Nenhum resultado")
            return

        # Calcula total
        total_valor = 0
        for r in result:
            valor = r.get("valor", 0)
            if isinstance(valor, Decimal):
                valor = float(valor)
            elif isinstance(valor, str):
                try:
                    valor = float(valor)
                except:
                    valor = 0
            total_valor += valor

        print(f"\nTotal de registros: {len(result)}")
        print(f"Valor total: R$ {abs(total_valor):,.2f}")

        # Agrupa por fornecedor
        por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

        for r in result:
            fornecedor = r.get("fornecedor", "SEM FORNECEDOR").strip() or "SEM FORNECEDOR"
            valor = r.get("valor", 0)

            if isinstance(valor, Decimal):
                valor = float(valor)
            elif isinstance(valor, str):
                try:
                    valor = float(valor)
                except:
                    valor = 0

            por_fornecedor[fornecedor]["valor"] += valor
            por_fornecedor[fornecedor]["quantidade"] += 1

        # Ordena por valor absoluto
        fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

        print("\n" + "=" * 80)
        print("TOP 10 MAIORES FORNECEDORES:")
        print("=" * 80)
        for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
            nome_curto = fornecedor[:50] if len(fornecedor) > 50 else fornecedor
            print(f"{i:2}. {nome_curto:50} R$ {abs(dados['valor']):>15,.2f}  ({dados['quantidade']:>4} pagamentos)")

        print("\n" + "=" * 80)
        print("VALIDACAO DOS FORNECEDORES MENCIONADOS PELA IA:")
        print("=" * 80)

        fornecedores_ia = {
            "PEDRO FERNANDO FERREIRA": 6175955.00,
            "CONDOMINIO AGROPECUARIO FERNANDO MARTINS": 4880830.00,
            "BRASCAFE COMERCIO EXPORTACAO E IMPORTACA": 4206730.00,
            "COMEXIM - LONDRINA": 4070076.00,
            "RIBEIRO S CAFES COMERCIO IMPORTACAO E EX": 3407500.00
        }

        for nome_ia, valor_ia in fornecedores_ia.items():
            encontrado = False
            for fornecedor, dados in por_fornecedor.items():
                fornecedor_upper = fornecedor.upper().strip()
                if nome_ia in fornecedor_upper or fornecedor_upper in nome_ia:
                    valor_banco = abs(dados["valor"])
                    diferenca = abs(valor_banco - valor_ia)
                    if diferenca < 1:
                        print(f"[OK] {nome_ia}: R$ {valor_banco:,.2f} (correto)")
                    else:
                        print(f"[X] {nome_ia}: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {valor_banco:,.2f} (diferenca: R$ {diferenca:,.2f})")
                    encontrado = True
                    break

            if not encontrado:
                print(f"[X] {nome_ia}: NAO ENCONTRADO no banco")

        print("\n" + "=" * 80)
        print("VALIDACAO GERAL:")
        print("=" * 80)

        valor_ia = 70031396.67
        total_ia = 1421

        diferenca_valor = abs(abs(total_valor) - valor_ia)
        diferenca_total = abs(len(result) - total_ia)

        if diferenca_valor < 1:
            print(f"[OK] Valor total: R$ {abs(total_valor):,.2f} (correto)")
        else:
            print(f"[X] Valor total: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {abs(total_valor):,.2f} (diferenca: R$ {diferenca_valor:,.2f})")

        if diferenca_total == 0:
            print(f"[OK] Total de contas: {len(result)} (correto)")
        else:
            print(f"[X] Total de contas: IA disse {total_ia}, Banco tem {len(result)} (diferenca: {diferenca_total})")

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
    test_validacao_dezembro()
