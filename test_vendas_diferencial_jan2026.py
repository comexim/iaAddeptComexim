"""
Verifica diferenciais de vendas em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_diferencial_jan2026():
    """Verifica diferenciais médios por cliente em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - DIFERENCIAL POR CLIENTE JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026
        print("2. Consultando vendas de janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Agrupa por cliente e calcula diferencial médio
        clientes = defaultdict(lambda: {
            "diferenciais": [],
            "total_sacas": 0,
            "total_valor": 0,
            "contratos": []
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            diferencial = row.get("diferencial")

            if diferencial is not None:
                clientes[cliente]["diferenciais"].append(float(diferencial))

            clientes[cliente]["total_sacas"] += row.get("sacas", 0) or 0
            clientes[cliente]["total_valor"] += row.get("valorTotal", 0) or 0
            clientes[cliente]["contratos"].append(row.get("contrato", ""))

        # Calcula médias
        print("3. DIFERENCIAIS MÉDIOS POR CLIENTE:")
        print("-" * 80)

        clientes_com_diferencial = []
        for cliente, data in clientes.items():
            if data["diferenciais"]:
                diferencial_medio = sum(data["diferenciais"]) / len(data["diferenciais"])
                clientes_com_diferencial.append({
                    "cliente": cliente,
                    "diferencial_medio": round(diferencial_medio, 2),
                    "num_contratos": len(data["diferenciais"]),
                    "total_sacas": data["total_sacas"],
                    "total_valor": data["total_valor"]
                })

        # Ordena por valor total (maior primeiro)
        clientes_com_diferencial.sort(key=lambda x: x["total_valor"], reverse=True)

        # Mostra todos os clientes
        for i, c in enumerate(clientes_com_diferencial, 1):
            print(f"{i:2d}. {c['cliente'][:50]:50s}")
            print(f"    Diferencial Médio: {c['diferencial_medio']:>8.2f}")
            print(f"    Contratos: {c['num_contratos']}, Sacas: {c['total_sacas']:,.0f}, Valor: R$ {c['total_valor']:,.2f}")
            print()

        # Comparação com resposta da IA
        print("\n4. COMPARAÇÃO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = {
            "BERNHARD ROTHFOS GMB": -29.91,
            "THE FOLGER COFFEE": -25.0,
            "JDE": 12.28,
            "NESTRADE S.A.": 8.61,
            "NESTLE ARARAS": 13.0
        }

        for nome_cliente_ia, dif_ia in ia_disse.items():
            # Busca cliente no banco (parcial, case insensitive)
            encontrado = None
            for c in clientes_com_diferencial:
                cliente_banco = c["cliente"].upper()
                nome_busca = nome_cliente_ia.upper()

                # Remove asteriscos da busca
                nome_busca = nome_busca.replace("*", "")

                if nome_busca in cliente_banco or cliente_banco in nome_busca:
                    encontrado = c
                    break

            print(f"\n{nome_cliente_ia}:")
            print(f"  IA disse: {dif_ia:.2f}")

            if encontrado:
                print(f"  Banco:    {encontrado['diferencial_medio']:.2f}")
                diferenca = abs(encontrado['diferencial_medio'] - dif_ia)
                status = "[OK]" if diferenca < 0.1 else "[DIFERENTE]"
                print(f"  Diferenca: {diferenca:.2f} {status}")
            else:
                print(f"  Banco:    [CLIENTE NAO ENCONTRADO]")

        print("\n" + "=" * 80)
        print("[OK] VERIFICACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_diferencial_jan2026()
