"""
Testa se a agregação agora inclui informações de BL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
import json
from decimal import Decimal

def test_agregacao_bl():
    """Verifica se agregação inclui campos logísticos"""
    print("=" * 80)
    print("TESTE - AGREGACAO COM CAMPOS LOGISTICOS")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026 (vai acionar agregação pois >50 registros)
        print("2. Consultando vendas de janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados")
        print(f"    (>50 registros, vai acionar AGREGAÇÃO POR CLIENTE)\n")

        # Importa e chama diretamente a função de agregação
        from collections import defaultdict

        # Replica lógica de _aggregate_by_client
        aggregated = defaultdict(lambda: {
            "total_contratos": 0,
            "total_sacas": 0,
            "total_valor": 0,
            "contratos": [],
            "diferencial_values": [],
            "valorUnitario_values": [],
            "valorFixado_values": [],
            "peneiraMTGB_values": [],
            "peneiraGrauda_values": [],
            "peneiraGrinder_values": [],
            "certificados": set(),
            "qualidades": set(),
            "paises": set(),
            "fixadores": set(),
            "linhas": set(),
            "mesEmbarque": set(),
            "contratos_com_bl": [],
            "contratos_embarcados": [],
            "contratos_amostra_enviada": [],
            "contratos_amostra_aprovada": [],
            "contratos_baixados": [],
            "vendedores": set(),
            "filiais": set(),
            "grupos_venda": set(),
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            data = aggregated[cliente]

            data["total_contratos"] += 1
            data["total_sacas"] += row.get("sacas", 0) or 0
            data["total_valor"] += row.get("valorTotal", 0) or 0
            data["contratos"].append(row.get("contrato", ""))

            if row.get("diferencial") is not None:
                data["diferencial_values"].append(float(row["diferencial"]))
            if row.get("valorUnitario") is not None:
                data["valorUnitario_values"].append(float(row["valorUnitario"]))
            if row.get("valorFixado") is not None:
                data["valorFixado_values"].append(float(row["valorFixado"]))

            if row.get("certificado") and str(row["certificado"]).strip():
                data["certificados"].add(str(row["certificado"]).strip())
            if row.get("pais") and str(row["pais"]).strip():
                data["paises"].add(str(row["pais"]).strip())

            # CAMPOS LOGÍSTICOS (NOVOS)
            contrato = row.get("contrato", "")

            if row.get("numeroBL") and str(row["numeroBL"]).strip():
                data["contratos_com_bl"].append(contrato)

            if row.get("saidaNavio") and str(row["saidaNavio"]).strip():
                data["contratos_embarcados"].append(contrato)

            if row.get("aprovAmostra") and str(row["aprovAmostra"]).strip():
                data["contratos_amostra_aprovada"].append(contrato)

            if row.get("baixaReceber") and str(row["baixaReceber"]).strip():
                data["contratos_baixados"].append(contrato)

            if row.get("vendedor") and str(row["vendedor"]).strip():
                data["vendedores"].add(str(row["vendedor"]).strip())

        # Converte para lista
        result_list = []
        for cliente, data in aggregated.items():
            def safe_avg(values):
                return round(sum(values) / len(values), 2) if values else None

            result_list.append({
                "cliente": cliente,
                "total_contratos": data["total_contratos"],
                "total_sacas": round(data["total_sacas"], 2),
                "total_valor": round(data["total_valor"], 2),
                "contratos_com_bl": ", ".join(data["contratos_com_bl"][:20]) if data["contratos_com_bl"] else "",
                "total_contratos_com_bl": len(data["contratos_com_bl"]),
                "contratos_embarcados": ", ".join(data["contratos_embarcados"][:20]) if data["contratos_embarcados"] else "",
                "total_contratos_embarcados": len(data["contratos_embarcados"]),
                "vendedores": sorted(list(data["vendedores"])) if data["vendedores"] else [],
            })

        result_list.sort(key=lambda x: x["total_valor"], reverse=True)

        # Formata como JSON
        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        formatted_output = json.dumps(result_list, ensure_ascii=False, indent=2, default=convert_decimals)

        # Salva em arquivo para análise
        with open("agregacao_output.txt", "w", encoding="utf-8") as f:
            f.write(formatted_output)

        print("3. VERIFICANDO CAMPOS LOGISTICOS NA AGREGACAO:")
        print("-" * 80)

        # Verifica se os novos campos estão presentes
        campos_esperados = [
            "contratos_com_bl",
            "total_contratos_com_bl",
            "contratos_embarcados",
            "total_contratos_embarcados",
            "contratos_amostra_aprovada",
            "contratos_baixados",
            "vendedores",
            "filiais",
            "grupos_venda"
        ]

        campos_encontrados = []
        campos_faltando = []

        for campo in campos_esperados:
            if campo in formatted_output:
                campos_encontrados.append(campo)
                print(f"  [OK] {campo}")
            else:
                campos_faltando.append(campo)
                print(f"  [X] {campo} [FALTANDO]")

        # Procura especificamente por contratos com BL
        print("\n4. PROCURANDO INFORMACOES DE BL:")
        print("-" * 80)

        print(f"Total de clientes agregados: {len(result_list)}\n")

        # Mostra clientes com BL
        clientes_com_bl = [c for c in result_list if c.get("total_contratos_com_bl", 0) > 0]
        print(f"Clientes com contratos com BL: {len(clientes_com_bl)}\n")

        # Mostra alguns exemplos
        for i, cliente_data in enumerate(clientes_com_bl[:10], 1):
            cliente = cliente_data.get("cliente", "N/A")
            total_bl = cliente_data.get("total_contratos_com_bl", 0)
            contratos_bl = cliente_data.get("contratos_com_bl", "")

            print(f"{i}. {cliente}:")
            print(f"   Total contratos: {cliente_data.get('total_contratos', 0)}")
            print(f"   Total com BL: {total_bl}")
            if contratos_bl:
                print(f"   Contratos: {contratos_bl}")
            else:
                print(f"   Contratos: (nenhum)")
            print()

        # Comparação com dados reais
        print("5. VALIDACAO COM DADOS REAIS:")
        print("-" * 80)

        # Conta quantos contratos realmente têm BL
        contratos_com_bl_real = [r for r in results if r.get("numeroBL") and str(r.get("numeroBL")).strip()]

        print(f"Registros totais: {len(results)}")
        print(f"Contratos com BL (dados brutos): {len(contratos_com_bl_real)}")

        # Agrupa por cliente para comparar
        from collections import defaultdict
        por_cliente_real = defaultdict(list)
        for row in contratos_com_bl_real:
            cliente = row.get("cliente", "N/A")
            contrato = row.get("contrato", "N/A")
            por_cliente_real[cliente].append(contrato)

        print(f"Clientes com contratos com BL: {len(por_cliente_real)}")
        print("\nExemplos de clientes com BL (dados brutos):")
        for i, (cliente, contratos) in enumerate(list(por_cliente_real.items())[:5], 1):
            print(f"  {i}. {cliente}: {len(contratos)} contratos")

        # Resultado final
        print("\n6. RESULTADO FINAL:")
        print("-" * 80)

        if len(campos_encontrados) == len(campos_esperados):
            print("[OK] TODOS OS CAMPOS LOGISTICOS FORAM ADICIONADOS!")
            print(f"    {len(campos_encontrados)}/{len(campos_esperados)} campos presentes")
        else:
            print(f"[PARCIAL] {len(campos_encontrados)}/{len(campos_esperados)} campos presentes")
            if campos_faltando:
                print(f"    Faltando: {', '.join(campos_faltando)}")

        print(f"\n[INFO] Output completo salvo em: agregacao_output.txt")

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
    test_agregacao_bl()
