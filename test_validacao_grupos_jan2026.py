"""
Valida resposta da IA sobre vendas por grupo em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_validacao_grupos():
    """Valida valores reais por grupo em janeiro 2026"""
    print("=" * 80)
    print("VALIDACAO - VENDAS POR GRUPO EM JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Busca contratos de janeiro 2026 (por mesEmbarque)
        print("2. Buscando contratos de janeiro 2026...")
        results = sql_client.execute_function("IA_Vendas", {"mesEmbarque": "2026/01"})

        if not results:
            print("[ERRO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Agrupa por grupo de venda
        print("3. AGREGANDO POR GRUPO DE VENDA:")
        print("-" * 80)

        por_grupo = {}
        registros_sem_grupo = []

        for row in results:
            grupo = row.get("grupoVenda", "").strip()
            valor = row.get("valorTotal", 0) or 0
            sacas = row.get("sacas", 0) or 0

            if not grupo:
                grupo = "SEM GRUPO"
                registros_sem_grupo.append(row.get("contrato", "N/A"))

            if grupo not in por_grupo:
                por_grupo[grupo] = {"valor": 0, "sacas": 0, "contratos": 0}

            por_grupo[grupo]["valor"] += float(valor)
            por_grupo[grupo]["sacas"] += float(sacas)
            por_grupo[grupo]["contratos"] += 1

        print(f"\nTotal de grupos encontrados: {len(por_grupo)}\n")

        for i, (grupo, totais) in enumerate(sorted(por_grupo.items(), key=lambda x: x[1]["valor"], reverse=True), 1):
            print(f"{i}. {grupo}:")
            print(f"   Valor: R$ {totais['valor']:,.2f}")
            print(f"   Sacas: {totais['sacas']:,.2f}")
            print(f"   Contratos: {totais['contratos']}")

        # Compara com resposta da IA
        print("\n\n4. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        resposta_ia = {
            "CEU": 499792560.30,
            "MI": 313101174.50,
            "COBRA": 1500524545.10,
            "MINT": 13556111.09
        }

        print("\nResposta da IA:")
        for grupo, valor in resposta_ia.items():
            print(f"  {grupo}: R$ {valor:,.2f}")

        print("\nDados do banco:")
        for grupo, totais in sorted(por_grupo.items(), key=lambda x: x[1]["valor"], reverse=True):
            print(f"  {grupo}: R$ {totais['valor']:,.2f}")

        print("\n\n5. ANALISE:")
        print("-" * 80)

        for grupo_ia, valor_ia in resposta_ia.items():
            if grupo_ia in por_grupo:
                valor_banco = por_grupo[grupo_ia]["valor"]
                diferenca = valor_ia - valor_banco
                percentual = (diferenca / valor_banco * 100) if valor_banco > 0 else 0

                if abs(percentual) < 1:
                    print(f"\n[OK] {grupo_ia}: Correto")
                else:
                    print(f"\n[ERRO] {grupo_ia}:")
                    print(f"  IA: R$ {valor_ia:,.2f}")
                    print(f"  Banco: R$ {valor_banco:,.2f}")
                    print(f"  Diferenca: R$ {diferenca:,.2f} ({percentual:+.1f}%)")
            else:
                print(f"\n[ERRO] {grupo_ia}: Grupo NAO ENCONTRADO no banco")

        # Verifica se há grupos no banco que não estão na IA
        for grupo_banco in por_grupo.keys():
            if grupo_banco not in resposta_ia and grupo_banco != "SEM GRUPO":
                print(f"\n[AVISO] {grupo_banco}: Grupo existe no banco mas NAO foi mencionado pela IA")
                print(f"  Valor: R$ {por_grupo[grupo_banco]['valor']:,.2f}")

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
    test_validacao_grupos()
