"""
Testa se a IA consegue detectar contratos baixados EM janeiro 2026 com novo formato
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict
import json
from decimal import Decimal

def test_nova_agregacao_baixados():
    """Testa agregação com data de baixa incluída"""
    print("=" * 80)
    print("TESTE - NOVA AGREGACAO COM DATA DE BAIXA")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Busca TODOS os contratos (simula query sem filtro)
        print("2. Buscando todos os contratos...")
        results = sql_client.execute_function("IA_Vendas", {})

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados")
        print(f"    (Vai acionar AGREGAÇÃO POR CLIENTE)\n")

        # Replica NOVA lógica de agregação
        aggregated = defaultdict(lambda: {
            "total_contratos": 0,
            "contratos_baixados": [],
            "contratos_baixados_por_mes": defaultdict(list),
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            data = aggregated[cliente]

            contrato = row.get("contrato", "")
            data["total_contratos"] += 1

            # NOVA LÓGICA: inclui data de baixa
            baixa_receber = row.get("baixaReceber")
            if baixa_receber and str(baixa_receber).strip():
                data_baixa = str(baixa_receber).strip()
                data["contratos_baixados"].append(f"{contrato} ({data_baixa})")

                # Agrupa por mês (YYYYMM)
                if len(data_baixa) >= 6:
                    ano_mes = data_baixa[:6]  # Exemplo: "202601" de "20260115"
                    data["contratos_baixados_por_mes"][ano_mes].append(contrato)

        # Filtra apenas clientes com contratos baixados
        result_list = []
        for cliente, data in aggregated.items():
            if data["contratos_baixados"]:
                result_list.append({
                    "cliente": cliente,
                    "total_contratos": data["total_contratos"],
                    "contratos_baixados": ", ".join(data["contratos_baixados"][:100]),
                    "total_contratos_baixados": len(data["contratos_baixados"]),
                    "contratos_baixados_jan2026": ", ".join(data["contratos_baixados_por_mes"].get("202601", [])[:100]),
                    "total_baixados_jan2026": len(data["contratos_baixados_por_mes"].get("202601", [])),
                })

        result_list.sort(key=lambda x: x["total_contratos_baixados"], reverse=True)

        # Mostra resultado
        print("3. AGREGACAO GERADA:")
        print("-" * 80)

        for i, item in enumerate(result_list[:10], 1):
            print(f"\n{i}. {item['cliente']}:")
            print(f"   Total contratos: {item['total_contratos']}")
            print(f"   Contratos baixados: {item['total_contratos_baixados']}")
            print(f"   Lista: {item['contratos_baixados'][:200]}...")

        # Verifica campos específicos por mês
        print("\n\n4. VERIFICANDO CAMPOS ESPECÍFICOS POR MÊS:")
        print("-" * 80)

        clientes_jan2026 = {}
        for item in result_list:
            cliente = item["cliente"]
            contratos_jan = item.get("contratos_baixados_jan2026", "")
            total_jan = item.get("total_baixados_jan2026", 0)

            if total_jan > 0:
                contratos_list = [c.strip() for c in contratos_jan.split(", ") if c.strip()]
                clientes_jan2026[cliente] = contratos_list

        print(f"\nClientes com contratos baixados em jan/2026: {len(clientes_jan2026)}\n")

        for i, (cliente, contratos) in enumerate(sorted(clientes_jan2026.items())[:20], 1):
            print(f"{i}. {cliente}: {len(contratos)} contrato(s)")
            print(f"   {', '.join(contratos[:10])}")
            if len(contratos) > 10:
                print(f"   ... e mais {len(contratos) - 10} contratos")

        # Validação com dados reais
        print("\n\n5. VALIDACAO COM DADOS REAIS:")
        print("-" * 80)

        baixados_jan2026_real = []
        for row in results:
            baixa = row.get("baixaReceber")
            if baixa and str(baixa).strip().startswith("202601"):
                baixados_jan2026_real.append({
                    "cliente": row.get("cliente", "N/A"),
                    "contrato": row.get("contrato", "N/A"),
                })

        por_cliente_real = defaultdict(list)
        for item in baixados_jan2026_real:
            por_cliente_real[item["cliente"]].append(item["contrato"])

        print(f"Total de contratos baixados em jan/2026 (banco): {len(baixados_jan2026_real)}")
        print(f"Clientes com baixados em jan/2026 (banco): {len(por_cliente_real)}")

        total_detectado = sum(len(c) for c in clientes_jan2026.values())
        print(f"\nTotal detectado pelos campos específicos: {total_detectado}")
        print(f"Clientes detectados: {len(clientes_jan2026)}")

        taxa_acerto = (total_detectado / len(baixados_jan2026_real) * 100) if baixados_jan2026_real else 0
        print(f"\nTaxa de acerto: {taxa_acerto:.1f}%")

        if taxa_acerto >= 90:
            print("\n[EXCELENTE] Novo formato funciona muito bem!")
        elif taxa_acerto >= 75:
            print("\n[BOM] Novo formato melhorou significativamente")
        elif taxa_acerto >= 50:
            print("\n[PARCIAL] Novo formato ajudou mas ainda tem limitações")
        else:
            print("\n[PROBLEMA] Novo formato não resolveu")

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
    test_nova_agregacao_baixados()
