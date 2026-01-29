"""
Testa se a agregação inclui contratos baixados
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
import json
from decimal import Decimal
from collections import defaultdict

def test_agregacao_baixados():
    """Verifica se agregação inclui contratos baixados"""
    print("=" * 80)
    print("TESTE - AGREGACAO COM CONTRATOS BAIXADOS")
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

        print(f"[OK] {len(results)} registros encontrados")
        print(f"    (>50 registros, vai acionar AGREGAÇÃO POR CLIENTE)\n")

        # Replica lógica de _aggregate_by_client (versão simplificada focada em baixados)
        aggregated = defaultdict(lambda: {
            "total_contratos": 0,
            "contratos": [],
            "contratos_baixados": [],
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            data = aggregated[cliente]

            contrato = row.get("contrato", "")
            data["total_contratos"] += 1
            data["contratos"].append(contrato)

            # Contratos baixados financeiramente
            if row.get("baixaReceber") and str(row["baixaReceber"]).strip():
                data["contratos_baixados"].append(contrato)

        # Converte para lista
        result_list = []
        for cliente, data in aggregated.items():
            result_list.append({
                "cliente": cliente,
                "total_contratos": data["total_contratos"],
                "contratos_baixados": ", ".join(data["contratos_baixados"][:20]) if data["contratos_baixados"] else "",
                "total_contratos_baixados": len(data["contratos_baixados"]),
            })

        result_list.sort(key=lambda x: x["total_contratos_baixados"], reverse=True)

        # Formata como JSON
        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        formatted_output = json.dumps(result_list, ensure_ascii=False, indent=2, default=convert_decimals)

        # Salva em arquivo
        with open("agregacao_baixados_output.txt", "w", encoding="utf-8") as f:
            f.write(formatted_output)

        print("3. CLIENTES COM CONTRATOS BAIXADOS:")
        print("-" * 80)

        clientes_com_baixados = [c for c in result_list if c.get("total_contratos_baixados", 0) > 0]

        if clientes_com_baixados:
            print(f"\nTotal: {len(clientes_com_baixados)} clientes com contratos baixados\n")

            for i, cliente_data in enumerate(clientes_com_baixados, 1):
                cliente = cliente_data.get("cliente", "N/A")
                total_baixados = cliente_data.get("total_contratos_baixados", 0)
                contratos_baixados = cliente_data.get("contratos_baixados", "")

                print(f"{i}. {cliente}:")
                print(f"   Total contratos: {cliente_data.get('total_contratos', 0)}")
                print(f"   Contratos baixados: {total_baixados}")
                if contratos_baixados:
                    print(f"   Lista: {contratos_baixados}")
                print()
        else:
            print("\nNenhum cliente com contratos baixados")

        # Validação com dados reais
        print("4. VALIDACAO COM DADOS REAIS:")
        print("-" * 80)

        baixados_real = [r for r in results if r.get("baixaReceber") and str(r.get("baixaReceber")).strip()]

        print(f"Registros totais: {len(results)}")
        print(f"Contratos baixados (dados brutos): {len(baixados_real)}")

        por_cliente_real = defaultdict(list)
        for row in baixados_real:
            cliente = row.get("cliente", "N/A")
            contrato = row.get("contrato", "N/A")
            por_cliente_real[cliente].append(contrato)

        print(f"Clientes com baixados (dados brutos): {len(por_cliente_real)}")

        # Comparação
        print("\n5. COMPARACAO AGREGACAO vs BRUTO:")
        print("-" * 80)

        total_agregado = sum(c["total_contratos_baixados"] for c in result_list)
        print(f"Total na agregação: {total_agregado}")
        print(f"Total no bruto: {len(baixados_real)}")

        if total_agregado == len(baixados_real):
            print("\n[OK] Agregação está CORRETA!")
        else:
            print(f"\n[ERRO] Agregação tem {total_agregado}, mas deveria ter {len(baixados_real)}")

        # Verifica se campo está presente
        print("\n6. VERIFICANDO PRESENCA DO CAMPO NO JSON:")
        print("-" * 80)

        if "contratos_baixados" in formatted_output:
            print("[OK] Campo 'contratos_baixados' presente no JSON")
        else:
            print("[ERRO] Campo 'contratos_baixados' NAO encontrado no JSON")

        if "total_contratos_baixados" in formatted_output:
            print("[OK] Campo 'total_contratos_baixados' presente no JSON")
        else:
            print("[ERRO] Campo 'total_contratos_baixados' NAO encontrado no JSON")

        # Conta quantos clientes têm total > 0
        clientes_com_total = sum(1 for c in result_list if c.get("total_contratos_baixados", 0) > 0)
        print(f"\nClientes com total_contratos_baixados > 0: {clientes_com_total}")

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
    test_agregacao_baixados()
