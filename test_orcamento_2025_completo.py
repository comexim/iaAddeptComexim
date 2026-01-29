"""
Verifica orçamento de 2025 completo (todos os 12 meses)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_orcamento_2025_completo():
    """Analisa orçamento de 2025 completo"""
    print("=" * 80)
    print("VERIFICACAO - ORCAMENTO 2025 COMPLETO")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta todos os meses de 2025
        print("2. Consultando todos os meses de 2025...")

        total_orcado_ano = 0
        total_realizado_ano = 0
        total_saldo_ano = 0
        total_registros = 0

        meses = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']

        resultados_por_mes = {}

        for mes in meses:
            filters = {"ano": 2025, "mes": mes}
            results = sql_client.execute_function("IA_Orcamento", filters)

            if results:
                # Soma valores do mês
                orcado_mes = sum(row.get("orcado", 0) or 0 for row in results)
                realizado_mes = sum(row.get("realizado", 0) or 0 for row in results)
                saldo_mes = sum(row.get("saldo", 0) or 0 for row in results)

                resultados_por_mes[mes] = {
                    "registros": len(results),
                    "orcado": orcado_mes,
                    "realizado": realizado_mes,
                    "saldo": saldo_mes
                }

                total_orcado_ano += orcado_mes
                total_realizado_ano += realizado_mes
                total_saldo_ano += saldo_mes
                total_registros += len(results)

                print(f"  Mes {mes}/2025: {len(results)} registros, Orcado: R$ {orcado_mes:,.2f}, Realizado: R$ {realizado_mes:,.2f}")
            else:
                print(f"  Mes {mes}/2025: Sem dados")
                resultados_por_mes[mes] = {
                    "registros": 0,
                    "orcado": 0,
                    "realizado": 0,
                    "saldo": 0
                }

        print(f"\n[OK] Total de registros: {total_registros}\n")

        # Calcula percentual
        percentual_realizado = 0
        if total_orcado_ano > 0:
            percentual_realizado = round((total_realizado_ano / total_orcado_ano) * 100, 1)

        # Mostra totais calculados
        print("3. TOTAIS CALCULADOS (PYTHON):")
        print("-" * 80)
        print(f"Total Orcado:    R$ {total_orcado_ano:,.2f}")
        print(f"Total Realizado: R$ {total_realizado_ano:,.2f}")
        print(f"Total Saldo:     R$ {total_saldo_ano:,.2f}")
        print(f"Percentual:      {percentual_realizado}%")

        # Comparação com resposta da IA
        print("\n4. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = {
            "orcado": 145647568.42,
            "realizado": 381737706.39,
            "saldo": -236090137.97,
            "percentual": 262.1
        }

        print("IA disse:")
        print(f"  Total Orcado:    R$ {ia_disse['orcado']:,.2f}")
        print(f"  Total Realizado: R$ {ia_disse['realizado']:,.2f}")
        print(f"  Total Saldo:     R$ {ia_disse['saldo']:,.2f}")
        print(f"  Percentual:      {ia_disse['percentual']}%")

        print("\nBanco tem:")
        print(f"  Total Orcado:    R$ {total_orcado_ano:,.2f}")
        print(f"  Total Realizado: R$ {total_realizado_ano:,.2f}")
        print(f"  Total Saldo:     R$ {total_saldo_ano:,.2f}")
        print(f"  Percentual:      {percentual_realizado}%")

        # Validação
        print("\n5. VALIDACAO:")
        print("-" * 80)

        validacoes = []

        # Orçado
        diff_orcado = abs(total_orcado_ano - ia_disse['orcado'])
        if diff_orcado < 1:
            print(f"[OK] Total Orcado: diferenca R$ {diff_orcado:.2f}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Total Orcado: diferenca R$ {diff_orcado:,.2f}")
            validacoes.append(False)

        # Realizado
        diff_realizado = abs(total_realizado_ano - ia_disse['realizado'])
        if diff_realizado < 1:
            print(f"[OK] Total Realizado: diferenca R$ {diff_realizado:.2f}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Total Realizado: diferenca R$ {diff_realizado:,.2f}")
            validacoes.append(False)

        # Saldo
        diff_saldo = abs(total_saldo_ano - ia_disse['saldo'])
        if diff_saldo < 1:
            print(f"[OK] Total Saldo: diferenca R$ {diff_saldo:.2f}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Total Saldo: diferenca R$ {diff_saldo:,.2f}")
            validacoes.append(False)

        # Percentual
        diff_percentual = abs(percentual_realizado - ia_disse['percentual'])
        if diff_percentual < 0.1:
            print(f"[OK] Percentual: diferenca {diff_percentual:.2f}%")
            validacoes.append(True)
        else:
            print(f"[ERRO] Percentual: diferenca {diff_percentual:.2f}%")
            validacoes.append(False)

        # Mostra distribuição por mês
        print("\n6. DISTRIBUICAO POR MES:")
        print("-" * 80)
        for mes in meses:
            dados = resultados_por_mes[mes]
            if dados["registros"] > 0:
                perc = round((dados["realizado"] / dados["orcado"] * 100), 1) if dados["orcado"] > 0 else 0
                print(f"  {mes}/2025: Orcado R$ {dados['orcado']:>14,.2f}, Realizado R$ {dados['realizado']:>14,.2f} ({perc:>6.1f}%)")

        # Resultado final
        print("\n7. RESULTADO FINAL:")
        print("-" * 80)

        if all(validacoes):
            print("[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif sum(validacoes) >= 3:
            print(f"[PARCIAL] Resposta da IA esta {sum(validacoes)}/4 correta")
        else:
            print(f"[ERRO] Resposta da IA tem problemas: {sum(validacoes)}/4 correto")

        print("\n" + "=" * 80)
        print("[OK] VERIFICACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_orcamento_2025_completo()
