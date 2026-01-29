"""
Validação: Contas a pagar desde 12/12/2025
Compara resposta da IA com dados do banco
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida resposta da IA contra banco de dados"""
    print("=" * 80)
    print("VALIDACAO - Contas a pagar desde 12/12/2025")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        resposta_ia = {
            "total": 161027736.37,
            "fornecedores": [
                {"nome": "FOLHA", "valor": 63537745.90},
                {"nome": "COOP. TRES PONTAS", "valor": 19567999.98},
                {"nome": "INSS", "valor": 14924444.61},
                {"nome": "JUROS CTR CAMBIO", "valor": 8840959.86},
                {"nome": "COMEXIM - OURO FINO", "valor": 6341123.43},
            ]
        }

        print(f"Total: R$ {resposta_ia['total']:,.2f}")
        print("\nTop 5 fornecedores:")
        for i, f in enumerate(resposta_ia['fornecedores'], 1):
            print(f"{i}. {f['nome']}: R$ {f['valor']:,.2f}")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca desde 12/12/2025
        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters={"vencimento": "20251212"})
        print(f"Total de registros retornados: {len(result) if result else 0}")

        if result:
            # Agrega por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            total_valor = 0
            for r in result:
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
                total_valor += valor

            print(f"Valor total a pagar (desde 12/12/2025): R$ {total_valor:,.2f}")

            # Top 10
            print("\n" + "=" * 80)
            print("TOP 10 FORNECEDORES (DESDE 12/12/2025):")
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
            for f_ia in resposta_ia['fornecedores']:
                nome_ia = f_ia['nome']
                valor_ia = f_ia['valor']

                encontrado = False
                for fornecedor, dados in por_fornecedor.items():
                    # Match flexível (contém o nome)
                    if nome_ia.upper() in fornecedor.upper() or fornecedor.upper() in nome_ia.upper():
                        diferenca = abs(dados['valor'] - valor_ia)
                        percentual = (diferenca / valor_ia * 100) if valor_ia > 0 else 0

                        if diferenca < 100:
                            print(f"[OK] {nome_ia}: R$ {dados['valor']:,.2f} (correto)")
                            matches += 1
                        else:
                            print(f"[X] {nome_ia}: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {dados['valor']:,.2f} (dif: R$ {diferenca:,.2f}, {percentual:.1f}%)")
                        encontrado = True
                        break

                if not encontrado:
                    print(f"[X] {nome_ia}: NAO ENCONTRADO")

            # Valida total
            print("\n" + "=" * 80)
            print("VALIDACAO GERAL:")
            print("=" * 80)

            diferenca_total = abs(total_valor - resposta_ia['total'])
            percentual = (diferenca_total / resposta_ia['total'] * 100) if resposta_ia['total'] > 0 else 0

            if diferenca_total < 100:
                print(f"[OK] Valor total: R$ {total_valor:,.2f} (correto)")
            else:
                print(f"[X] Valor total: IA disse R$ {resposta_ia['total']:,.2f}, Banco tem R$ {total_valor:,.2f}")
                print(f"    Diferenca: R$ {diferenca_total:,.2f} ({percentual:.1f}%)")

            print(f"\nTotal de fornecedores validados: {matches}/{len(resposta_ia['fornecedores'])}")

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
