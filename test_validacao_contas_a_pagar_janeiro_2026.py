"""
Valida contas a pagar de janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao_janeiro_2026():
    """Valida contas a pagar de janeiro 2026"""
    print("=" * 80)
    print("VALIDACAO - Contas a pagar de janeiro 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total: R$ 138.296.707,40")
        print("\nTop 5 fornecedores:")
        print("1. FOLHA: R$ 51.846.684,97")
        print("2. COOP. TRES PONTAS: R$ 19.567.999,98")
        print("3. JUROS CTR CAMBIO: R$ 8.312.998,79")
        print("4. INSS: R$ 7.725.531,70")
        print("5. COMEXIM - OURO FINO: R$ 6.341.123,43")
        print()

        print("3. VERIFICACAO NO BANCO:")
        print("-" * 80)
        print("Consultando: IA_ContasAPagar WHERE vencimento >= '20260101'")

        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters={"vencimento": "20260101"})

        if not result:
            print("[ERRO] Nenhum resultado")
            return

        print(f"\nTotal de registros: {len(result)}")

        # Calcula total
        total_valor = 0
        for r in result:
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

            total_valor += valor

        print(f"Valor total a pagar: R$ {total_valor:,.2f}")

        # Agrupa por fornecedor
        por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0, "naturezas": set()})

        for r in result:
            fornecedor = r.get("fornecedor", "SEM FORNECEDOR").strip() or "SEM FORNECEDOR"
            valor = r.get("valor", 0)
            natureza = r.get("natureza", "").strip()

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
            if natureza:
                por_fornecedor[fornecedor]["naturezas"].add(natureza)

        # Ordena por valor absoluto
        fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

        print("\n" + "=" * 80)
        print("TOP 10 MAIORES FORNECEDORES A PAGAR:")
        print("=" * 80)
        for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
            nome_curto = fornecedor[:40] if len(fornecedor) > 40 else fornecedor
            naturezas = ", ".join(sorted(dados["naturezas"]))[:50]
            print(f"{i:2}. {nome_curto:40} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:>4} títulos)")
            if naturezas:
                print(f"     Naturezas: {naturezas}")

        print("\n" + "=" * 80)
        print("VALIDACAO DOS FORNECEDORES MENCIONADOS PELA IA:")
        print("=" * 80)

        fornecedores_ia = {
            "FOLHA": 51846684.97,
            "COOP. TRES PONTAS": 19567999.98,
            "JUROS CTR CAMBIO": 8312998.79,
            "INSS": 7725531.70,
            "COMEXIM - OURO FINO": 6341123.43
        }

        for nome_ia, valor_ia in fornecedores_ia.items():
            encontrado = False
            for fornecedor, dados in por_fornecedor.items():
                fornecedor_upper = fornecedor.upper().strip()
                if nome_ia.upper() in fornecedor_upper or fornecedor_upper in nome_ia.upper():
                    valor_banco = dados["valor"]
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

        valor_ia = 138296707.40
        diferenca_valor = abs(total_valor - valor_ia)

        if diferenca_valor < 1:
            print(f"[OK] Valor total: R$ {total_valor:,.2f} (correto)")
        else:
            print(f"[X] Valor total: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {total_valor:,.2f} (diferenca: R$ {diferenca_valor:,.2f})")

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
    test_validacao_janeiro_2026()
