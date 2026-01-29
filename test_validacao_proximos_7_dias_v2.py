"""
Validação: Contas a pagar nos próximos 7 dias
Compara resposta da IA com dados do banco
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict

def test_validacao():
    """Valida resposta da IA contra banco de dados"""
    print("=" * 80)
    print("VALIDACAO - Contas a pagar nos próximos 7 dias (ATUALIZADA)")
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
            "total": 92056087.58,
            "fornecedores": [
                {"nome": "FOLHA", "valor": 51846684.97},
                {"nome": "BRADESCO SAUDE S/A", "valor": 5194924.16},
                {"nome": "JUSCELINO ELIAS MENDES AZEVEDO", "valor": 5125000.00},
                {"nome": "MINASUL", "valor": 5084400.05},
                {"nome": "LUIZ CARLOS FIGUEIREDO", "valor": 4990000.00},
            ]
        }

        print(f"Total: R$ {resposta_ia['total']:,.2f}")
        print("\nTop 5 fornecedores:")
        for i, f in enumerate(resposta_ia['fornecedores'], 1):
            print(f"{i}. {f['nome']}: R$ {f['valor']:,.2f}")

        print("\n3. CALCULANDO PERIODO:")
        print("-" * 80)
        hoje = datetime.now()
        data_limite = hoje + timedelta(days=7)
        print(f"Hoje: {hoje.strftime('%Y-%m-%d')}")
        print(f"Data limite (hoje + 7 dias): {data_limite.strftime('%Y-%m-%d')}")
        data_limite_str = data_limite.strftime('%Y%m%d')
        data_hoje_str = hoje.strftime('%Y%m%d')
        print(f"Formato SQL: vencimento >= {data_hoje_str} AND vencimento <= {data_limite_str}")

        print("\n4. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca todas as contas a pagar
        result_all = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)
        print(f"Total de contas a pagar (sem filtro): {len(result_all)}")

        # Filtra desde hoje
        desde_hoje = [r for r in result_all if r.get("vencimento", "") >= data_hoje_str]
        print(f"Total de contas a pagar (desde hoje): {len(desde_hoje)}")

        # Filtra manualmente os próximos 7 dias
        if result_all:
            proximos_7_dias = [r for r in result_all if data_hoje_str <= r.get("vencimento", "") <= data_limite_str]
            print(f"Total de contas nos próximos 7 dias: {len(proximos_7_dias)}")

            # Agrega por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            total_valor = 0
            for r in proximos_7_dias:
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

            print(f"\nValor total a pagar (próximos 7 dias): R$ {total_valor:,.2f}")

            # Top 10
            print("\n" + "=" * 80)
            print("TOP 10 FORNECEDORES (PRÓXIMOS 7 DIAS):")
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
                        if diferenca < 1:
                            print(f"[OK] {nome_ia}: R$ {dados['valor']:,.2f} (correto)")
                            matches += 1
                        else:
                            print(f"[X] {nome_ia}: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {dados['valor']:,.2f} (diferenca: R$ {diferenca:,.2f})")
                        encontrado = True
                        break

                if not encontrado:
                    print(f"[X] {nome_ia}: NAO ENCONTRADO nos próximos 7 dias")

            # Valida total
            print("\n" + "=" * 80)
            print("VALIDACAO GERAL:")
            print("=" * 80)

            diferenca_total = abs(total_valor - resposta_ia['total'])
            percentual = (diferenca_total / resposta_ia['total'] * 100) if resposta_ia['total'] > 0 else 0

            if diferenca_total < 100:
                print(f"[OK] Valor total: R$ {total_valor:,.2f} (correto)")
            else:
                print(f"[X] Valor total: IA disse R$ {resposta_ia['total']:,.2f}, Banco tem R$ {total_valor:,.2f} (diferenca: R$ {diferenca_total:,.2f}, {percentual:.1f}%)")

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
