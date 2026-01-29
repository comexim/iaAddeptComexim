"""
Verifica preços médios por cliente em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_preco_medio_jan2026():
    """Calcula preços médios por cliente em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - PRECO MEDIO POR CLIENTE JANEIRO 2026")
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

        # Agrupa por cliente e calcula preço médio
        clientes = defaultdict(lambda: {
            "valores_unitarios": [],
            "total_sacas": 0,
            "total_valor": 0,
            "contratos": 0
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            valor_unitario = row.get("valorUnitario")
            sacas = row.get("sacas", 0) or 0

            if valor_unitario is not None:
                clientes[cliente]["valores_unitarios"].append(float(valor_unitario))

            clientes[cliente]["total_sacas"] += sacas
            clientes[cliente]["total_valor"] += row.get("valorTotal", 0) or 0
            clientes[cliente]["contratos"] += 1

        # Calcula médias e ordena por valor total
        clientes_com_preco = []
        for cliente, data in clientes.items():
            if data["valores_unitarios"]:
                preco_medio = sum(data["valores_unitarios"]) / len(data["valores_unitarios"])
                clientes_com_preco.append({
                    "cliente": cliente,
                    "preco_medio": round(preco_medio, 2),
                    "num_contratos": data["contratos"],
                    "total_sacas": data["total_sacas"],
                    "total_valor": data["total_valor"]
                })

        # Ordena por valor total (maior primeiro)
        clientes_com_preco.sort(key=lambda x: x["total_valor"], reverse=True)

        print("3. PRECO MEDIO (VALOR UNITARIO) POR CLIENTE:")
        print("-" * 80)

        # Mostra TOP 10
        for i, c in enumerate(clientes_com_preco[:10], 1):
            print(f"{i:2d}. {c['cliente'][:40]:40s}")
            print(f"    Preco Medio: R$ {c['preco_medio']:>8.2f}/saca")
            print(f"    Contratos: {c['num_contratos']}, Sacas: {c['total_sacas']:,.0f}, Valor: R$ {c['total_valor']:,.2f}")
            print()

        # Comparação com resposta da IA
        print("\n4. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = {
            "BERNHARD ROTHFOS GMB": 333.21,
            "THE FOLGER COFFEE": 326.80,
            "JDE": 343.56,
            "NESTRADE S.A.": 380.84,
            "NESTLE ARARAS": 377.58
        }

        total_corretos = 0
        total_verificados = 0

        for nome_cliente_ia, preco_ia in ia_disse.items():
            # Busca cliente no banco (parcial, case insensitive)
            encontrado = None
            for c in clientes_com_preco:
                cliente_banco = c["cliente"].upper().strip()
                nome_busca = nome_cliente_ia.upper().strip()

                if nome_busca in cliente_banco or cliente_banco in nome_busca:
                    encontrado = c
                    break

            print(f"\n{nome_cliente_ia}:")
            print(f"  IA disse: R$ {preco_ia:.2f}/saca")

            if encontrado:
                print(f"  Banco:    R$ {encontrado['preco_medio']:.2f}/saca")
                diferenca = abs(encontrado['preco_medio'] - preco_ia)

                if diferenca < 0.01:
                    status = "[OK]"
                    total_corretos += 1
                else:
                    status = "[DIFERENTE]"

                print(f"  Diferenca: R$ {diferenca:.2f} {status}")
                total_verificados += 1
            else:
                print(f"  Banco:    [CLIENTE NAO ENCONTRADO]")

        print("\n" + "=" * 80)
        print("5. RESUMO DA VALIDACAO:")
        print("-" * 80)
        print(f"Total de clientes verificados: {total_verificados}")
        print(f"Clientes com valores corretos: {total_corretos}")
        print(f"Taxa de acerto: {(total_corretos/total_verificados*100):.1f}%")

        if total_corretos == total_verificados:
            print("\n[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        else:
            print(f"\n[AVISO] {total_verificados - total_corretos} cliente(s) com valores diferentes")

        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_preco_medio_jan2026()
