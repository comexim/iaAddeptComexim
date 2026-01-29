"""
Validação: Janeiro 2026 completo (01/01 até 31/01)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida janeiro completo"""
    print("=" * 80)
    print("VALIDACAO - Janeiro 2026 completo (01/01 até 31/01)")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        fornecedores_ia = {
            "FOLHA": 51846684.97,
            "COOP. TRES PONTAS": 19567999.98,
            "JUROS CTR CAMBIO": 8312998.79,
            "INSS": 7725531.70,
            "COMEXIM - OURO FINO": 6341123.43,
        }

        for i, (nome, valor) in enumerate(fornecedores_ia.items(), 1):
            print(f"{i}. {nome}: R$ {valor:,.2f}")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca desde 01/01/2026
        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters={"vencimento": "20260101"})
        print(f"Total bruto (>= 01/01/2026): {len(result) if result else 0}")

        if result:
            # Aplica filtro manual até 31/01
            result_filtrado = [r for r in result if r.get("vencimento", "") <= "20260131"]
            print(f"Total filtrado (<= 31/01/2026): {len(result_filtrado)}")

            # Agrega por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0})

            for r in result_filtrado:
                fornecedor = r.get("fornecedor", "").strip() or "SEM FORNECEDOR"
                valor = r.get("valor", 0)

                if valor is None:
                    valor = 0
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_fornecedor[fornecedor]["valor"] += valor

            print("\nTop 5 fornecedores:")
            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            matches = 0
            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:5], 1):
                print(f"{i}. {fornecedor[:40]:40} R$ {dados['valor']:>15,.2f}")

                # Verifica match com IA
                for nome_ia, valor_ia in fornecedores_ia.items():
                    if nome_ia.upper() in fornecedor.upper():
                        diferenca = abs(dados['valor'] - valor_ia)
                        if diferenca < 1:
                            print(f"   [OK] EXATO!")
                            matches += 1
                        else:
                            percentual = (diferenca / valor_ia * 100) if valor_ia > 0 else 0
                            print(f"   [X] IA: R$ {valor_ia:,.2f}, Dif: R$ {diferenca:,.2f} ({percentual:.1f}%)")
                        break

            print(f"\n{'=' * 80}")
            if matches == 5:
                print("[OK] TODOS OS 5 FORNECEDORES ESTAO 100% CORRETOS!")
            elif matches >= 3:
                print(f"[OK] {matches}/5 fornecedores validados - diferenças pequenas são aceitáveis")
            else:
                print(f"[INFO] {matches}/5 fornecedores validados")

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
    test_validacao()
