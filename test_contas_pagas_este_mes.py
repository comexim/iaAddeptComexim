"""
Testa contas pagas deste mes (janeiro 2026)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal
from datetime import datetime

def test_contas_pagas_este_mes():
    """Testa contas pagas deste mes"""
    print("=" * 80)
    print("TESTE - Contas pagas deste mes (janeiro 2026)")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        # Primeiro, testa a tool
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Testando tool: 'este mes'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais contas foram pagas este mes?"

        result_tool = sql_tools._pesquisa_contas_pagas(data_inicio="este mes")

        if result_tool:
            print(f"[OK] Tool retornou resultado")
            print(f"Tamanho da resposta: {len(result_tool)} caracteres")

            # Procura por "SEM CLIENTE" na resposta
            if "SEM CLIENTE" in result_tool:
                print("\n[AVISO] Resposta menciona 'SEM CLIENTE' - INCORRETO para contas pagas!")
                print("Contas pagas sao sobre FORNECEDORES, nao clientes.\n")

            # Mostra primeiros 1000 caracteres
            print("Primeiros 1000 chars da resposta:")
            print("-" * 80)
            print(result_tool[:1000])
            print("-" * 80)
        else:
            print("[ERRO] Tool nao retornou resultado\n")

        # Verifica diretamente no banco
        print("\n\n3. VERIFICACAO DIRETA NO BANCO:")
        print("-" * 80)

        # Janeiro 2026 = 20260101
        print("Consultando: IA_ContasPagas WHERE emissao >= '20260101'")
        result_direto = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20260101"})

        if result_direto and len(result_direto) > 0:
            print(f"\nTotal de registros: {len(result_direto)}")

            # Calcula total
            total_valor = 0
            for r in result_direto:
                valor = r.get("valor", None)
                if valor:
                    if isinstance(valor, Decimal):
                        total_valor += float(valor)
                    elif isinstance(valor, (int, float)):
                        total_valor += valor
                    elif isinstance(valor, str):
                        try:
                            total_valor += float(valor)
                        except:
                            try:
                                valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                                total_valor += float(valor_limpo)
                            except:
                                pass

            print(f"Valor total pago: R$ {total_valor:,.2f}")

            # Conta fornecedores unicos
            fornecedores_unicos = set()
            for r in result_direto:
                fornecedor = r.get("fornecedor", "").strip()
                if fornecedor:
                    fornecedores_unicos.add(fornecedor)

            print(f"Total de fornecedores diferentes: {len(fornecedores_unicos)}")

            # Mostra top 10 fornecedores
            from collections import defaultdict
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            for r in result_direto:
                fornecedor = r.get("fornecedor", "SEM FORNECEDOR").strip() or "SEM FORNECEDOR"
                valor = r.get("valor", 0)

                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        try:
                            valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                            valor = float(valor_limpo)
                        except:
                            valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_fornecedor[fornecedor]["valor"] += valor
                por_fornecedor[fornecedor]["quantidade"] += 1

            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: x[1]["valor"])

            print(f"\n\nTop 10 fornecedores (maiores pagamentos):")
            print("-" * 80)
            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
                nome_curto = fornecedor[:50] if len(fornecedor) > 50 else fornecedor
                print(f"{i:2}. {nome_curto:50} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:>4} pagamentos)")

            # Mostra alguns exemplos
            print(f"\n\nExemplos de pagamentos (primeiros 5):")
            print("-" * 80)
            for i, r in enumerate(result_direto[:5], 1):
                fornecedor = r.get("fornecedor", "N/A")[:50]
                valor = r.get("valor", 0)
                try:
                    valor = float(valor)
                except:
                    valor = 0
                natureza = r.get("natureza", "N/A").strip()
                emissao = r.get("emissao", "N/A")

                print(f"\n{i}. Fornecedor: {fornecedor}")
                print(f"   Valor: R$ {valor:,.2f}")
                print(f"   Natureza: {natureza}")
                print(f"   Emissao: {emissao}")

        else:
            print("\n[AVISO] Nenhum registro encontrado para janeiro 2026")
            print("Isso pode significar que ainda nao ha contas pagas em janeiro 2026.")

            # Tenta dezembro 2025 como comparacao
            print("\n\nTentando dezembro 2025 para comparacao:")
            result_dez = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251201"})
            if result_dez:
                print(f"[OK] Dezembro 2025 tem {len(result_dez)} registros")
            else:
                print("[AVISO] Dezembro 2025 tambem nao tem registros")

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
    test_contas_pagas_este_mes()
