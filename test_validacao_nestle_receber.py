"""
Validação: Quanto a NESTLE me deve (contas a receber)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida valores da NESTLE"""
    print("=" * 80)
    print("VALIDACAO - Contas a receber da NESTLE")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        valores_ia = {
            "NESTLE ARARAS": 9181760.68,
            "NESTLE BRASIL LTDA.": 4465306.24,
            "NESTLE": 366672.83,
        }
        total_ia = 14013739.75

        print(f"Total: R$ {total_ia:,.2f}")
        for nome, valor in valores_ia.items():
            print(f"  - {nome}: R$ {valor:,.2f}")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca TODAS as contas a receber (sem filtro de data)
        result = sql_client.execute_function("dbo.IA_ContasAReceber", filters=None)
        print(f"Total de registros (sem filtro): {len(result) if result else 0}")

        if result:
            # Filtra apenas clientes com "NESTLE" no nome
            result_nestle = [r for r in result if "NESTLE" in str(r.get("cliente", "")).upper()]
            print(f"Registros com 'NESTLE' no nome: {len(result_nestle)}")

            # Agrega por cliente
            por_cliente = defaultdict(lambda: {"valor": 0, "saldo": 0, "contratos": set(), "vencimentos": []})

            for r in result_nestle:
                cliente = r.get("cliente", "").strip()
                valor = r.get("valor", 0)
                saldo = r.get("saldo", 0)

                # Converte valor
                if valor is None:
                    valor = 0
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0

                # Converte saldo
                if saldo is None:
                    saldo = 0
                elif isinstance(saldo, Decimal):
                    saldo = float(saldo)
                elif isinstance(saldo, str):
                    try:
                        saldo = float(saldo)
                    except:
                        saldo = 0

                por_cliente[cliente]["valor"] += valor
                por_cliente[cliente]["saldo"] += saldo

                contrato = r.get("contrato", "").strip()
                if contrato:
                    por_cliente[cliente]["contratos"].add(contrato)

                vencimento = r.get("vencimentoReal", "").strip()
                if vencimento:
                    por_cliente[cliente]["vencimentos"].append(vencimento)

            # Ordena por valor
            clientes_ordenados = sorted(por_cliente.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            print("\nClientes NESTLE encontrados:")
            print("-" * 80)

            total_banco = 0
            matches = 0

            for i, (cliente, dados) in enumerate(clientes_ordenados, 1):
                print(f"\n{i}. {cliente}")
                print(f"   Valor: R$ {dados['valor']:,.2f}")
                print(f"   Saldo: R$ {dados['saldo']:,.2f}")
                print(f"   Contratos: {len(dados['contratos'])} ({', '.join(sorted(list(dados['contratos']))[:8])})")

                vencimentos_unicos = sorted(set(dados["vencimentos"]))[:5]
                print(f"   Próximos vencimentos: {', '.join(vencimentos_unicos)}")

                total_banco += dados["valor"]

                # Verifica match com IA
                for nome_ia, valor_ia in valores_ia.items():
                    if nome_ia.upper() in cliente.upper() or cliente.upper() in nome_ia.upper():
                        diferenca = abs(dados['valor'] - valor_ia)
                        if diferenca < 1:
                            print(f"   [OK] IA: R$ {valor_ia:,.2f} - EXATO!")
                            matches += 1
                        else:
                            percentual = (diferenca / valor_ia * 100) if valor_ia > 0 else 0
                            print(f"   [X] IA: R$ {valor_ia:,.2f}, Dif: R$ {diferenca:,.2f} ({percentual:.1f}%)")
                        break

            print("\n" + "=" * 80)
            print("TOTAIS:")
            print("=" * 80)
            print(f"Total BANCO: R$ {total_banco:,.2f}")
            print(f"Total IA:    R$ {total_ia:,.2f}")

            diferenca_total = abs(total_banco - total_ia)
            if diferenca_total < 1:
                print(f"[OK] TOTAIS COINCIDEM!")
            else:
                percentual = (diferenca_total / total_ia * 100) if total_ia > 0 else 0
                print(f"[X] Diferença: R$ {diferenca_total:,.2f} ({percentual:.2f}%)")

            print("\n" + "=" * 80)
            if diferenca_total < 1 and matches == len(valores_ia):
                print(f"[OK] VALIDACAO 100% CORRETA - {matches}/{len(valores_ia)} clientes validados!")
            elif diferenca_total < 1:
                print(f"[OK] Total correto, {matches}/{len(valores_ia)} clientes validados")
            else:
                print(f"[INFO] {matches}/{len(valores_ia)} clientes validados, diferença no total")

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
