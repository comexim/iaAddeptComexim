"""
Valida contas a pagar nos próximos 7 dias
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict
from datetime import datetime, timedelta

def test_validacao_proximos_7_dias():
    """Valida contas a pagar nos próximos 7 dias"""
    print("=" * 80)
    print("VALIDACAO - Contas a pagar nos próximos 7 dias")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total: R$ 128.781.164,62")
        print("\nTop 5 fornecedores:")
        print("1. FOLHA: R$ 51.846.684,97")
        print("2. COOP. TRES PONTAS: R$ 19.567.999,98")
        print("3. JUROS CTR CAMBIO: R$ 7.163.396,49")
        print("4. COMEXIM - OURO FINO: R$ 6.341.123,43")
        print("5. BRADESCO SAUDE S/A: R$ 5.194.924,16")
        print()

        # Calcula data de hoje + 7 dias
        from datetime import datetime
        import pytz
        tz_sp = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(tz_sp)
        data_limite = hoje + timedelta(days=7)

        print("3. CALCULANDO PERIODO:")
        print("-" * 80)
        print(f"Hoje: {hoje.strftime('%Y-%m-%d')}")
        print(f"Data limite (hoje + 7 dias): {data_limite.strftime('%Y-%m-%d')}")
        print(f"Formato SQL: vencimento >= {hoje.strftime('%Y%m%d')} AND vencimento <= {data_limite.strftime('%Y%m%d')}")
        print()

        print("4. VERIFICACAO NO BANCO (todas as contas a pagar):")
        print("-" * 80)

        # Busca todas as contas a pagar sem filtro primeiro
        result_all = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)
        print(f"Total de contas a pagar (sem filtro): {len(result_all) if result_all else 0}")

        # Busca desde hoje
        result_hoje = sql_client.execute_function("dbo.IA_ContasAPagar", filters={"vencimento": hoje.strftime('%Y%m%d')})
        print(f"Total de contas a pagar (desde hoje): {len(result_hoje) if result_hoje else 0}")

        # Filtra manualmente os próximos 7 dias
        if result_all:
            data_limite_str = data_limite.strftime('%Y%m%d')
            data_hoje_str = hoje.strftime('%Y%m%d')

            # CORRIGIDO: filtrar por >= hoje E <= data_limite
            proximos_7_dias = [r for r in result_all if data_hoje_str <= r.get("vencimento", "") <= data_limite_str]
            print(f"Total de contas nos próximos 7 dias (filtrado manualmente): {len(proximos_7_dias)}")

            # Calcula total
            total_valor = 0
            for r in proximos_7_dias:
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

            print(f"\nValor total a pagar (próximos 7 dias): R$ {total_valor:,.2f}")

            # Agrupa por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0, "naturezas": set()})

            for r in proximos_7_dias:
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
            print("TOP 10 FORNECEDORES (PRÓXIMOS 7 DIAS):")
            print("=" * 80)
            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
                nome_curto = fornecedor[:40] if len(fornecedor) > 40 else fornecedor
                print(f"{i:2}. {nome_curto:40} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:>4} títulos)")

            print("\n" + "=" * 80)
            print("VALIDACAO DOS FORNECEDORES MENCIONADOS PELA IA:")
            print("=" * 80)

            fornecedores_ia = {
                "FOLHA": 51846684.97,
                "COOP. TRES PONTAS": 19567999.98,
                "JUROS CTR CAMBIO": 7163396.49,
                "COMEXIM - OURO FINO": 6341123.43,
                "BRADESCO SAUDE S/A": 5194924.16
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
                    print(f"[X] {nome_ia}: NAO ENCONTRADO nos próximos 7 dias")

            print("\n" + "=" * 80)
            print("VALIDACAO GERAL:")
            print("=" * 80)

            valor_ia = 128781164.62
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
    test_validacao_proximos_7_dias()
