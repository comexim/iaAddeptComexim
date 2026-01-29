"""
Testa query sobre ID Protheus de contrato
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_id_protheus():
    """Testa query sobre ID Protheus"""
    print("=" * 80)
    print("TESTE - ID PROTHEUS DO CONTRATO 021/25")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Buscando contrato 021/25 usando IA_Vendas...")

        # Busca usando filtro de numeroContrato
        result = sql_client.execute_function(
            "dbo.IA_Vendas",
            filters={
                "numeroContrato": "021/25"
            }
        )

        print(f"Total de registros encontrados: {len(result)}")

        if result and len(result) > 0:
            # Pega as colunas do primeiro resultado
            colunas = list(result[0].keys())
            print(f"\nTotal de colunas disponíveis: {len(colunas)}")

            # Procura colunas relacionadas a ID ou Protheus
            id_cols = [c for c in colunas if 'id' in c.lower() or 'protheus' in c.lower() or 'recno' in c.lower() or 'r_e_c' in c.lower()]

            if id_cols:
                print(f"\n✓ Colunas com ID/Protheus/RecNo encontradas:")
                for col in id_cols:
                    print(f"  - {col}")
            else:
                print(f"\n✗ Nenhuma coluna com ID/Protheus/RecNo encontrada!")

            print("\n\n3. DADOS DO CONTRATO 021/25:")
            print("-" * 80)

            for i, row in enumerate(result, 1):
                print(f"\n--- Registro {i} ---")
                print(f"Contrato: {row.get('numeroContrato')}")
                print(f"Cliente: {row.get('cliente')}")
                print(f"Valor: {row.get('valor')}")
                print(f"Sacas: {row.get('sacas')}")

                # Mostra campos relacionados a ID
                if id_cols:
                    print("\nCampos de ID/Protheus:")
                    for col in id_cols:
                        print(f"  {col}: {row.get(col)}")
                else:
                    print("\n⚠️ Nenhum campo de ID/Protheus encontrado!")
                    print("\nMostrando todos os campos disponíveis:")
                    print(f"Total: {len(colunas)} campos\n")
                    for col in colunas:
                        val = row.get(col)
                        if isinstance(val, str) and len(val) > 100:
                            val = val[:100] + "..."
                        print(f"  {col}: {val}")

            print("\n\n4. ANÁLISE:")
            print("-" * 80)
            if id_cols:
                print("✓ Existem campos de ID disponíveis no banco")
                print("→ O agente deveria conseguir retornar essa informação")
                print(f"→ Campos disponíveis: {', '.join(id_cols)}")
            else:
                print("✗ NÃO existem campos de ID/Protheus no banco")
                print("→ A resposta da IA está correta: não há ID Protheus disponível")

        else:
            print("\n[AVISO] Contrato 021/25 não encontrado!")
            print("\n→ A resposta da IA está correta: o contrato não existe")

            # Tenta buscar contratos de janeiro 2026
            print("\nBuscando contratos de janeiro 2026...")
            result_jan = sql_client.execute_function(
                "dbo.IA_Vendas",
                filters={
                    "mesEmbarque": "janeiro 2026"
                }
            )

            if result_jan and len(result_jan) > 0:
                print(f"Total de registros em janeiro 2026: {len(result_jan)}")
                # Mostra alguns contratos
                print("\nPrimeiros 10 contratos:")
                for r in result_jan[:10]:
                    print(f"  - {r.get('numeroContrato')} ({r.get('cliente')})")
            else:
                print("Nenhum contrato encontrado em janeiro 2026")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_id_protheus()
