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

        # Busca todos os contratos de janeiro 2026
        result = sql_client.execute_function(
            "dbo.IA_Vendas",
            params={
                "dataEmbarqueInicio": "2026-01-01",
                "dataEmbarqueFim": "2026-01-31"
            }
        )

        print(f"Total de registros em janeiro 2026: {len(result)}")

        # Filtra pelo contrato 021/25
        contratos_021_25 = [r for r in result if '021/25' in str(r.get('numeroContrato', ''))]

        if contratos_021_25:
            print(f"\nContratos encontrados com 021/25: {len(contratos_021_25)}")

            # Pega as colunas do primeiro resultado
            colunas = list(contratos_021_25[0].keys())
            print(f"\nTotal de colunas disponíveis: {len(colunas)}")

            # Procura colunas relacionadas a ID ou Protheus
            id_cols = [c for c in colunas if 'id' in c.lower() or 'protheus' in c.lower() or 'recno' in c.lower() or 'r_e_c' in c.lower()]

            if id_cols:
                print(f"\n✓ Colunas com ID/Protheus/RecNo encontradas: {id_cols}")
            else:
                print(f"\n✗ Nenhuma coluna com ID/Protheus/RecNo encontrada!")

            print("\n\n3. DADOS DO CONTRATO 021/25:")
            print("-" * 80)

            for i, row in enumerate(contratos_021_25, 1):
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
                    print("\nPrimeiros 30 campos disponíveis:")
                    for col in list(colunas)[:30]:
                        val = row.get(col)
                        if isinstance(val, str) and len(val) > 100:
                            val = val[:100] + "..."
                        print(f"  {col}: {val}")

            print("\n\n4. ANÁLISE:")
            print("-" * 80)
            if id_cols:
                print("✓ Existem campos de ID disponíveis no banco")
                print("→ O agente deveria conseguir retornar essa informação")
            else:
                print("✗ NÃO existem campos de ID/Protheus no banco")
                print("→ A resposta da IA está correta: não há ID Protheus disponível")

        else:
            print("\n[AVISO] Contrato 021/25 não encontrado!")

            # Mostra contratos que começam com 021
            contratos_021 = [r for r in result if str(r.get('numeroContrato', '')).startswith('021')]
            if contratos_021:
                print(f"\nContratos que começam com 021: {len(contratos_021)}")
                for c in contratos_021[:5]:
                    print(f"  - {c.get('numeroContrato')} ({c.get('cliente')})")
            else:
                print("\nNenhum contrato encontrado que comece com 021")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_id_protheus()
