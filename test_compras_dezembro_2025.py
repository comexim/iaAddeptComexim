"""
Testa compras de dezembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_compras_dezembro():
    """Testa compras de dezembro 2025"""
    print("=" * 80)
    print("TESTE - Compras de dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Testando tool: 'Compras de dezembro 2025'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Compras de dezembro 2025"

        result = sql_tools._pesquisa_compras(data_inicio="dezembro 2025")

        print(f"[OK] Retornou resultado\n")

        print("3. COMPARAÇÃO COM RESPOSTA DA IA:")
        print("-" * 80)
        print("Resposta da IA:")
        print("- Valor total: R$ 216.259.606,70")
        print("- Total de sacas: 108.561,36")
        print("- Clientes: Não houve clientes específicos")
        print()

        # Extrai dados do resultado
        if isinstance(result, str):
            if "[" in result:
                json_start = result.index("[")
                json_end = result.rindex("]") + 1
                json_str = result[json_start:json_end]
                data = json.loads(json_str)

                print("Dados do banco (agregados):")
                print("-" * 80)
                if data and len(data) > 0:
                    total_valor = sum(c.get("total_valor", 0) for c in data)
                    total_sacas = sum(c.get("total_sacas", 0) for c in data)

                    print(f"Total de clientes: {len(data)}")
                    print(f"Valor total: R$ {total_valor:,.2f}")
                    print(f"Total de sacas: {total_sacas:,.2f}")

                    # Mostra os clientes
                    print("\nClientes encontrados:")
                    for i, cliente_data in enumerate(data[:10], 1):
                        cliente = cliente_data.get("cliente", "N/A")
                        valor = cliente_data.get("total_valor", 0)
                        sacas = cliente_data.get("total_sacas", 0)
                        print(f"{i}. {cliente}: R$ {valor:,.2f} / {sacas:.2f} sacas")

        print("\n\n4. VERIFICAÇÃO DIRETA NO BANCO:")
        print("-" * 80)

        # Consulta direta dezembro 2025
        result_direto = sql_client.execute_function("dbo.IA_Compras", filters={"emissao": "20251201"})

        if result_direto and len(result_direto) > 0:
            print(f"Total de registros: {len(result_direto)}\n")

            # Calcula totais
            total_valor_direto = sum(float(r.get("valorTotal", 0) or 0) for r in result_direto)
            total_sacas_direto = sum(float(r.get("sacas", 0) or 0) for r in result_direto)

            print("Totais calculados diretamente:")
            print(f"Valor total: R$ {total_valor_direto:,.2f}")
            print(f"Total de sacas: {total_sacas_direto:,.2f}")

            # Verifica se valores batem
            print("\n\n5. VALIDAÇÃO:")
            print("-" * 80)

            valor_ia = 216259606.70
            sacas_ia = 108561.36

            if abs(total_valor_direto - valor_ia) < 1:
                print("[OK] Valor total CORRETO")
            else:
                print(f"[X] Valor total DIVERGE:")
                print(f"    IA: R$ {valor_ia:,.2f}")
                print(f"    Banco: R$ {total_valor_direto:,.2f}")

            if abs(total_sacas_direto - sacas_ia) < 1:
                print("[OK] Total de sacas CORRETO")
            else:
                print(f"[X] Total de sacas DIVERGE:")
                print(f"    IA: {sacas_ia:,.2f}")
                print(f"    Banco: {total_sacas_direto:,.2f}")

            # Verifica fornecedores
            fornecedores_unicos = set(r.get("FORNEC", "").strip() for r in result_direto if r.get("FORNEC"))
            print(f"\n\nFornecedores únicos no banco: {len(fornecedores_unicos)}")
            if fornecedores_unicos:
                print("Primeiros 10 fornecedores:")
                for i, forn in enumerate(list(fornecedores_unicos)[:10], 1):
                    print(f"  {i}. {forn}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_compras_dezembro()
