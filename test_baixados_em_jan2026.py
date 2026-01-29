"""
Testa query de contratos baixados EM janeiro 2026 (por data de baixa)
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_baixados_em_jan2026():
    """Testa se query de baixados em janeiro 2026 é problemática"""
    print("=" * 80)
    print("TESTE - CONTRATOS BAIXADOS EM JANEIRO 2026 (POR DATA DE BAIXA)")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Testa query SEM filtro (busca tudo e filtra em Python)
        print("2. Buscando TODOS os contratos (sem filtro)...")
        start_time = time.time()

        results_all = sql_client.execute_function("IA_Vendas", {})

        elapsed = time.time() - start_time
        print(f"[OK] Tempo: {elapsed:.2f}s")
        print(f"Total de registros: {len(results_all) if results_all else 0}\n")

        if not results_all:
            print("[AVISO] Nenhum registro encontrado")
            return

        # Filtra em Python por data de baixa em janeiro 2026
        print("3. Filtrando por baixaReceber em janeiro 2026...")
        start_time = time.time()

        baixados_jan2026 = []
        for row in results_all:
            baixa = row.get("baixaReceber")
            if baixa and str(baixa).strip().startswith("202601"):
                baixados_jan2026.append(row)

        elapsed = time.time() - start_time
        print(f"[OK] Tempo de filtro: {elapsed:.2f}s")
        print(f"Contratos baixados em jan/2026: {len(baixados_jan2026)}\n")

        # Mostra alguns exemplos
        if baixados_jan2026:
            print("4. EXEMPLOS DE CONTRATOS BAIXADOS EM JANEIRO 2026:")
            print("-" * 80)

            from collections import defaultdict
            por_cliente = defaultdict(list)

            for row in baixados_jan2026:
                cliente = row.get("cliente", "N/A")
                contrato = row.get("contrato", "N/A")
                baixa = row.get("baixaReceber", "N/A")
                embarque = row.get("mesEmbarque", "N/A")
                por_cliente[cliente].append((contrato, baixa, embarque))

            print(f"\nTotal: {len(baixados_jan2026)} contratos de {len(por_cliente)} clientes\n")

            for i, (cliente, contratos) in enumerate(sorted(por_cliente.items())[:10], 1):
                print(f"{i}. {cliente}: {len(contratos)} contrato(s)")
                for contrato, baixa, embarque in contratos[:3]:
                    print(f"   - {contrato} (Baixa: {baixa}, Embarque: {embarque})")
                if len(contratos) > 3:
                    print(f"   ... e mais {len(contratos) - 3} contratos")
                print()

        # Análise do problema
        print("\n5. ANALISE DO PROBLEMA:")
        print("=" * 80)

        print(f"\nTotal de registros no banco: {len(results_all)}")
        print(f"Contratos baixados em jan/2026: {len(baixados_jan2026)}")
        print(f"Percentual: {len(baixados_jan2026)/len(results_all)*100:.2f}%")

        print("\nPROBLEMA POTENCIAL:")
        print("- Query sem filtro retorna TODOS os contratos (pode ser milhares)")
        print("- IA precisa processar e agregar todos esses dados")
        print("- Isso pode causar TIMEOUT ou DEMORA EXCESSIVA")

        print("\nSOLUCAO:")
        print("- Perguntar 'contratos COM EMBARQUE em janeiro 2026 já baixados'")
        print("  (usa filtro mesEmbarque='2026/01', muito mais eficiente)")

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
    test_baixados_em_jan2026()
