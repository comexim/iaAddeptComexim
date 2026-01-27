"""
Valida a resposta da IA sobre contas pagas de janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao_resposta_ia():
    """Valida resposta da IA"""
    print("=" * 80)
    print("VALIDACAO - Resposta da IA sobre contas pagas")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total de contas: 493")
        print("Valor total: R$ 20.534.685,84")
        print("\nFornecedores listados pela IA:")
        print("1. RUNDFUNK ARD, ZDF, DRADI: R$ 18,36")
        print("2. TRIBUNAL DE JUSTICA: R$ 34,35")
        print("3. PEDAGIO SEM PARAR: R$ 50,53")
        print("4. ACIAOF: R$ 56,00")
        print("5. CLARO: R$ 61,66")
        print()

        print("3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20260101"})

        if not result:
            print("[ERRO] Nenhum resultado")
            return

        # Calcula total
        total_valor = 0
        for r in result:
            valor = r.get("valor", 0)
            if isinstance(valor, Decimal):
                valor = float(valor)
            elif isinstance(valor, str):
                try:
                    valor = float(valor)
                except:
                    valor = 0
            total_valor += valor

        print(f"Total de registros: {len(result)}")
        print(f"Valor total: R$ {abs(total_valor):,.2f}")

        # Agrupa por fornecedor
        por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

        for r in result:
            fornecedor = r.get("fornecedor", "SEM FORNECEDOR").strip() or "SEM FORNECEDOR"
            valor = r.get("valor", 0)

            if isinstance(valor, Decimal):
                valor = float(valor)
            elif isinstance(valor, str):
                try:
                    valor = float(valor)
                except:
                    valor = 0

            por_fornecedor[fornecedor]["valor"] += valor
            por_fornecedor[fornecedor]["quantidade"] += 1

        # Ordena por MAIOR valor absoluto (mais importantes)
        fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

        print("\n" + "=" * 80)
        print("TOP 10 MAIORES FORNECEDORES (por valor):")
        print("=" * 80)
        for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
            nome_curto = fornecedor[:50] if len(fornecedor) > 50 else fornecedor
            print(f"{i:2}. {nome_curto:50} R$ {abs(dados['valor']):>15,.2f}  ({dados['quantidade']:>4} pagamentos)")

        print("\n" + "=" * 80)
        print("TOP 10 MENORES FORNECEDORES (por valor):")
        print("=" * 80)
        # Pega os ultimos (menores valores)
        fornecedores_menores = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]))[:10]
        for i, (fornecedor, dados) in enumerate(fornecedores_menores, 1):
            nome_curto = fornecedor[:50] if len(fornecedor) > 50 else fornecedor
            print(f"{i:2}. {nome_curto:50} R$ {abs(dados['valor']):>15,.2f}  ({dados['quantidade']:>4} pagamentos)")

        print("\n" + "=" * 80)
        print("VALIDACAO DOS FORNECEDORES MENCIONADOS PELA IA:")
        print("=" * 80)

        fornecedores_ia = {
            "RUNDFUNK ARD, ZDF, DRADI": 18.36,
            "TRIBUNAL DE JUSTICA": 34.35,
            "PEDAGIO SEM PARAR": 50.53,
            "ACIAOF": 56.00,
            "CLARO": 61.66
        }

        for nome, valor_ia in fornecedores_ia.items():
            if nome in por_fornecedor:
                valor_banco = abs(por_fornecedor[nome]["valor"])
                diferenca = abs(valor_banco - valor_ia)
                if diferenca < 0.01:
                    print(f"[OK] {nome}: R$ {valor_banco:,.2f} (correto)")
                else:
                    print(f"[X] {nome}: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {valor_banco:,.2f}")
            else:
                print(f"[X] {nome}: NAO ENCONTRADO no banco")

        print("\n" + "=" * 80)
        print("ANALISE:")
        print("=" * 80)
        print("A IA listou os MENORES fornecedores (valores pequenos).")
        print("Mas o ideal seria listar os MAIORES (mais relevantes):")
        print("")
        print("Os maiores fornecedores sao:")
        for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:5], 1):
            print(f"  {i}. {fornecedor[:50]}: R$ {abs(dados['valor']):,.2f}")

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
    test_validacao_resposta_ia()
