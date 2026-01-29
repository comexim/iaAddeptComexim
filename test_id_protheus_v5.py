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

        print("2. Buscando todos os contratos de janeiro 2026...")

        # Busca todos de janeiro 2026 para ver as colunas
        result = sql_client.execute_function(
            "dbo.IA_Vendas",
            filters={
                "mesEmbarque": "janeiro 2026"
            }
        )

        print(f"Total de registros encontrados: {len(result)}")

        if result and len(result) > 0:
            # Pega as colunas do primeiro resultado
            colunas = list(result[0].keys())
            print(f"\nTotal de colunas disponíveis: {len(colunas)}")

            # Procura colunas relacionadas a contrato
            contrato_cols = [c for c in colunas if 'contrat' in c.lower() or 'numero' in c.lower()]
            print(f"\nColunas relacionadas a contrato/numero:")
            for col in contrato_cols:
                print(f"  - {col}")

            # Procura colunas relacionadas a ID ou Protheus
            id_cols = [c for c in colunas if 'id' in c.lower() or 'protheus' in c.lower() or 'recno' in c.lower() or 'r_e_c' in c.lower()]

            if id_cols:
                print(f"\n✓ Colunas com ID/Protheus/RecNo encontradas:")
                for col in id_cols:
                    print(f"  - {col}")
            else:
                print(f"\n✗ Nenhuma coluna com ID/Protheus/RecNo encontrada")

            # Agora busca especificamente contratos 021/25
            print("\n\n3. BUSCANDO CONTRATO 021/25:")
            print("-" * 80)

            # Tenta encontrar a coluna correta de contrato
            contrato_col_name = None
            for col in contrato_cols:
                if 'numero' in col.lower():
                    contrato_col_name = col
                    break

            if not contrato_col_name and contrato_cols:
                contrato_col_name = contrato_cols[0]

            if contrato_col_name:
                print(f"Usando coluna: {contrato_col_name}")

                # Filtra contratos que contenham 021/25
                contratos_021_25 = [r for r in result if '021/25' in str(r.get(contrato_col_name, ''))]

                if contratos_021_25:
                    print(f"\nContratos encontrados: {len(contratos_021_25)}\n")

                    for i, row in enumerate(contratos_021_25, 1):
                        print(f"--- Registro {i} ---")
                        print(f"Contrato: {row.get(contrato_col_name)}")
                        if 'cliente' in row:
                            print(f"Cliente: {row.get('cliente')}")
                        if 'valor' in row:
                            print(f"Valor: {row.get('valor')}")
                        if 'sacas' in row:
                            print(f"Sacas: {row.get('sacas')}")

                        # Mostra campos relacionados a ID
                        if id_cols:
                            print("\nCampos de ID/Protheus:")
                            for col in id_cols:
                                print(f"  {col}: {row.get(col)}")
                        else:
                            print("\n⚠️ Nenhum campo de ID/Protheus encontrado!")

                        print()

                    print("\n4. ANÁLISE:")
                    print("-" * 80)
                    if id_cols:
                        print("✓ Existem campos de ID disponíveis no banco")
                        print("→ O agente deveria conseguir retornar essa informação")
                        print(f"→ Campos disponíveis: {', '.join(id_cols)}")
                    else:
                        print("✗ NÃO existem campos de ID/Protheus no banco")
                        print("→ A resposta da IA está correta: não há ID Protheus disponível")

                else:
                    print(f"\n✗ Contrato 021/25 não encontrado!")
                    print("→ A resposta da IA está correta: o contrato não existe")

                    print(f"\nPrimeiros 10 contratos (para referência):")
                    for r in result[:10]:
                        print(f"  - {r.get(contrato_col_name)}")
            else:
                print("Não foi possível identificar coluna de número do contrato")
                print(f"\nTodas as colunas disponíveis ({len(colunas)}):")
                for col in colunas:
                    print(f"  - {col}")

        else:
            print("\nNenhum contrato encontrado em janeiro 2026")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_id_protheus()
