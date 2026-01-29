"""
Verifica contratos de janeiro 2026 já baixados no contas a receber
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_baixados_jan2026():
    """Lista contratos baixados no contas a receber em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - CONTRATOS BAIXADOS NO CONTAS A RECEBER JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026
        print("2. Consultando vendas de janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Separa contratos baixados e não baixados
        baixados = []
        nao_baixados = []

        for row in results:
            contrato = row.get("contrato", "N/A")
            cliente = row.get("cliente", "N/A")
            baixa = row.get("baixaReceber")

            # Verifica se foi baixado
            tem_baixa = baixa and str(baixa).strip()

            if tem_baixa:
                baixados.append({
                    "cliente": cliente,
                    "contrato": contrato,
                    "baixaReceber": baixa,
                    "valorTotal": row.get("valorTotal", 0),
                })
            else:
                nao_baixados.append({
                    "cliente": cliente,
                    "contrato": contrato,
                })

        # Mostra contratos BAIXADOS
        print("3. CONTRATOS BAIXADOS NO CONTAS A RECEBER:")
        print("-" * 80)

        if baixados:
            # Agrupa por cliente
            por_cliente = defaultdict(list)
            for item in baixados:
                por_cliente[item["cliente"]].append(item["contrato"])

            for cliente in sorted(por_cliente.keys()):
                contratos = sorted(por_cliente[cliente])
                print(f"\n{cliente}:")
                for contrato in contratos:
                    # Mostra data de baixa
                    for item in baixados:
                        if item["contrato"] == contrato and item["cliente"] == cliente:
                            print(f"  - {contrato} (Baixa: {item['baixaReceber']}, Valor: R$ {item['valorTotal']:,.2f})")
                            break

            print(f"\nTotal: {len(baixados)} contratos de {len(por_cliente)} clientes")
        else:
            print("\nNenhum contrato baixado")

        # Mostra estatísticas
        print("\n4. ESTATISTICAS GERAIS:")
        print("-" * 80)
        print(f"Total de contratos janeiro 2026: {len(results)}")
        print(f"Contratos BAIXADOS no contas a receber: {len(baixados)}")
        print(f"Contratos NAO BAIXADOS: {len(nao_baixados)}")

        if baixados:
            valor_total_baixado = sum(item["valorTotal"] for item in baixados)
            print(f"Valor total baixado: R$ {valor_total_baixado:,.2f}")

        # Comparação com resposta da IA
        print("\n5. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        print("\nIA disse:")
        print("  'Não há contratos de janeiro de 2026 que já tenham sido baixados'")

        print("\nBanco tem:")
        if baixados:
            print(f"  {len(baixados)} contratos baixados de {len(por_cliente)} clientes")
            # Mostra alguns exemplos
            print("\n  Exemplos:")
            for i, item in enumerate(baixados[:10], 1):
                print(f"    {i}. {item['cliente']} - {item['contrato']} (R$ {item['valorTotal']:,.2f})")
        else:
            print("  Nenhum contrato baixado")

        # Validação
        print("\n6. VALIDACAO:")
        print("-" * 80)

        if len(baixados) == 0:
            print("[OK] RESPOSTA DA IA ESTA CORRETA!")
            print("    Realmente não há contratos baixados em janeiro 2026")
        else:
            print(f"[ERRO] RESPOSTA DA IA ESTA INCORRETA!")
            print(f"    IA disse: 0 contratos baixados")
            print(f"    Banco tem: {len(baixados)} contratos baixados")
            print(f"    Erro: IA não detectou os contratos baixados")

        # Mostra alguns contratos não baixados para comparar
        print("\n7. EXEMPLOS DE CONTRATOS NAO BAIXADOS (para comparação):")
        print("-" * 80)
        for i, item in enumerate(nao_baixados[:10], 1):
            print(f"  {i}. {item['cliente']} - {item['contrato']}")

        if len(nao_baixados) > 10:
            print(f"  ... e mais {len(nao_baixados) - 10} contratos não baixados")

        # Resultado final
        print("\n8. RESULTADO FINAL:")
        print("-" * 80)

        if len(baixados) == 0:
            print("[OK] Resposta correta: Não há contratos baixados")
        else:
            print(f"[ERRO] Resposta incorreta: Existem {len(baixados)} contratos baixados")
            taxa_erro = (len(baixados) / len(results) * 100)
            print(f"Taxa de erro: {taxa_erro:.1f}% dos contratos não foram detectados")

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
    test_baixados_jan2026()
