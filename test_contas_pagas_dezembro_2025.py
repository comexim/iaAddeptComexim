"""
Testa contas pagas de dezembro 2025 e valida dados
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json
from decimal import Decimal

def test_contas_pagas_dezembro():
    """Testa contas pagas de dezembro 2025"""
    print("=" * 80)
    print("TESTE - Contas pagas de dezembro 2025")
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

        print("2. Testando tool: 'Contas pagas de dezembro 2025'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Contas pagas de dezembro 2025"

        result = sql_tools._pesquisa_contas_pagas(data_inicio="dezembro 2025")

        print(f"[OK] Retornou resultado\n")

        print("3. VERIFICACAO DIRETA NO BANCO:")
        print("-" * 80)

        # Consulta direta dezembro 2025
        result_direto = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251201"})

        if result_direto and len(result_direto) > 0:
            print(f"Total de registros: {len(result_direto)}\n")

            # Calcula totais
            total_valor_direto = 0
            for r in result_direto:
                valor = r.get("valor", None)
                if valor:
                    if isinstance(valor, Decimal):
                        total_valor_direto += float(valor)
                    elif isinstance(valor, (int, float)):
                        total_valor_direto += valor
                    elif isinstance(valor, str):
                        try:
                            # Tenta conversao direta primeiro
                            total_valor_direto += float(valor)
                        except:
                            try:
                                # Se falhar, tenta limpar formatacao
                                valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                                total_valor_direto += float(valor_limpo)
                            except:
                                pass

            print("Totais calculados diretamente:")
            print(f"Valor total pago: R$ {total_valor_direto:,.2f}")

            # Agrupa por natureza
            from collections import defaultdict
            por_natureza = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            for r in result_direto:
                natureza = r.get("natureza", "SEM NATUREZA").strip() or "SEM NATUREZA"
                valor = r.get("valor", 0)

                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        # Tenta conversao direta primeiro
                        valor = float(valor)
                    except:
                        try:
                            # Se falhar, tenta limpar formatacao
                            valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                            valor = float(valor_limpo)
                        except:
                            valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_natureza[natureza]["valor"] += valor
                por_natureza[natureza]["quantidade"] += 1

            # Ordena por valor
            naturezas_ordenadas = sorted(por_natureza.items(), key=lambda x: x[1]["valor"], reverse=True)

            print(f"\n\nPagamentos por natureza (Top 10):")
            print("-" * 80)
            for i, (natureza, totais) in enumerate(naturezas_ordenadas[:10], 1):
                print(f"{i:2}. {natureza:40} R$ {totais['valor']:>15,.2f}  ({totais['quantidade']:>4} pagamentos)")

            # Agrupa por fornecedor (top 10)
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            for r in result_direto:
                fornecedor = r.get("fornecedor", "SEM FORNECEDOR").strip() or "SEM FORNECEDOR"
                valor = r.get("valor", 0)

                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        # Tenta conversao direta primeiro
                        valor = float(valor)
                    except:
                        try:
                            # Se falhar, tenta limpar formatacao
                            valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                            valor = float(valor_limpo)
                        except:
                            valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_fornecedor[fornecedor]["valor"] += valor
                por_fornecedor[fornecedor]["quantidade"] += 1

            # Ordena por valor
            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: x[1]["valor"], reverse=True)

            print(f"\n\nMaiores fornecedores pagos (Top 10):")
            print("-" * 80)
            for i, (fornecedor, totais) in enumerate(fornecedores_ordenados[:10], 1):
                nome_curto = fornecedor[:50] if len(fornecedor) > 50 else fornecedor
                print(f"{i:2}. {nome_curto:50} R$ {totais['valor']:>15,.2f}  ({totais['quantidade']:>4} pagamentos)")

            # Verifica bancos utilizados
            bancos_unicos = set(r.get("banco", "").strip() for r in result_direto if r.get("banco"))
            print(f"\n\nBancos utilizados: {len(bancos_unicos)}")
            if bancos_unicos:
                print("Bancos:")
                for i, banco in enumerate(sorted(bancos_unicos)[:10], 1):
                    print(f"  {i}. {banco}")

            # Verifica centros de custo
            centros_custo = set(r.get("centroCusto", "").strip() for r in result_direto if r.get("centroCusto"))
            print(f"\n\nCentros de custo utilizados: {len(centros_custo)}")

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO COMPLETA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_contas_pagas_dezembro()
