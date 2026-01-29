"""
Calcula exatamente o total correto de janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_calculo():
    """Calcula totais corretos"""
    print("=" * 80)
    print("CALCULO CORRETO - Janeiro 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        # Busca janeiro 2026
        result = sql_client.execute_function("dbo.IA_ContasAReceber", filters={"vencimentoReal": "20260101"})

        if result:
            result_filtrado = [r for r in result if r.get("vencimentoReal", "") <= "20260131"]
            print(f"\nTotal de registros janeiro 2026: {len(result_filtrado)}")

            # Separa por tipo
            por_tipo = defaultdict(list)
            for r in result_filtrado:
                tipo = r.get("tipo", "")
                por_tipo[tipo].append(r)

            print("\nREGISTROS POR TIPO:")
            print("-" * 80)
            for tipo, registros in sorted(por_tipo.items()):
                print(f"{tipo}: {len(registros)} registros")

            # Calcula totais incluindo TODOS os tipos
            print("\n" + "=" * 80)
            print("CALCULO 1: INCLUINDO TODOS OS TIPOS")
            print("=" * 80)

            por_cliente_todos = defaultdict(lambda: {"valor": 0, "registros": []})
            total_todos = 0

            for r in result_filtrado:
                cliente = r.get("cliente", "").strip()
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

                por_cliente_todos[cliente]["valor"] += valor
                por_cliente_todos[cliente]["registros"].append({
                    "tipo": r.get("tipo"),
                    "numero": r.get("numero", "").strip(),
                    "contrato": r.get("contrato", "").strip(),
                    "valor": valor
                })
                total_todos += valor

            print(f"\nTOTAL (todos os tipos): R$ {total_todos:,.2f}")

            print("\nTop 5 clientes:")
            clientes_ordenados = sorted(por_cliente_todos.items(),
                                       key=lambda x: abs(x[1]["valor"]),
                                       reverse=True)

            for i, (cliente, dados) in enumerate(clientes_ordenados[:5], 1):
                print(f"\n{i}. {cliente}: R$ {dados['valor']:,.2f}")
                for reg in dados['registros']:
                    print(f"   - {reg['tipo']:10} {reg['numero']:10} {reg['contrato']:30} R$ {reg['valor']:>12,.2f}")

            # Calcula totais apenas com tipo=Receber
            print("\n" + "=" * 80)
            print("CALCULO 2: APENAS tipo='Receber'")
            print("=" * 80)

            receber_only = [r for r in result_filtrado if r.get("tipo") == "Receber"]
            print(f"\nTotal de registros tipo='Receber': {len(receber_only)}")

            por_cliente_receber = defaultdict(lambda: {"valor": 0, "registros": []})
            total_receber = 0

            for r in receber_only:
                cliente = r.get("cliente", "").strip()
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

                por_cliente_receber[cliente]["valor"] += valor
                por_cliente_receber[cliente]["registros"].append({
                    "numero": r.get("numero", "").strip(),
                    "contrato": r.get("contrato", "").strip(),
                    "valor": valor
                })
                total_receber += valor

            print(f"\nTOTAL (apenas Receber): R$ {total_receber:,.2f}")

            print("\nTop 5 clientes:")
            clientes_ordenados_receber = sorted(por_cliente_receber.items(),
                                               key=lambda x: abs(x[1]["valor"]),
                                               reverse=True)

            for i, (cliente, dados) in enumerate(clientes_ordenados_receber[:5], 1):
                print(f"\n{i}. {cliente}: R$ {dados['valor']:,.2f}")

            # Compara com resposta da IA
            print("\n" + "=" * 80)
            print("COMPARACAO COM IA")
            print("=" * 80)
            print(f"\nIA disse:        R$ 13.219.599,31")
            print(f"Todos os tipos:  R$ {total_todos:,.2f}")
            print(f"Apenas Receber:  R$ {total_receber:,.2f}")

            dif_todos = abs(total_todos - 13219599.31)
            dif_receber = abs(total_receber - 13219599.31)

            print(f"\nDiferença (todos):   R$ {dif_todos:,.2f}")
            print(f"Diferença (receber): R$ {dif_receber:,.2f}")

            if dif_todos < 1:
                print("\n[OK] IA está correta (usando todos os tipos)")
            elif dif_receber < 1:
                print("\n[OK] IA está correta (usando apenas tipo='Receber')")
            elif dif_receber < dif_todos:
                print("\n[INFO] IA parece estar usando apenas tipo='Receber' mas há pequena diferença")
            else:
                print("\n[X] Há discrepância nos valores - IA pode ter erro de cálculo")

            # Verifica NESTLE ARARAS especificamente
            print("\n" + "=" * 80)
            print("NESTLE ARARAS (detalhado)")
            print("=" * 80)

            nestle_registros = [r for r in result_filtrado if "NESTLE ARARAS" in r.get("cliente", "")]
            total_nestle = sum(
                float(r.get("valor", 0)) if isinstance(r.get("valor"), Decimal)
                else r.get("valor", 0) or 0
                for r in nestle_registros
            )

            print(f"\nNESLE ARARAS - Total de registros: {len(nestle_registros)}")
            print(f"NESTLE ARARAS - Valor total: R$ {total_nestle:,.2f}")
            print(f"IA disse: R$ 1.544.734,89")
            print(f"Diferença: R$ {abs(total_nestle - 1544734.89):,.2f}")

            for reg in nestle_registros:
                tipo = reg.get("tipo")
                numero = reg.get("numero", "").strip()
                contrato = reg.get("contrato", "").strip()
                valor = reg.get("valor", 0)
                if isinstance(valor, Decimal):
                    valor = float(valor)
                print(f"  - {tipo:10} {numero:10} {contrato:30} R$ {valor:>12,.2f}")

        print("\n" + "=" * 80)
        print("[OK] CALCULO CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_calculo()
