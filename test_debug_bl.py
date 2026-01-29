"""
Debug detalhado dos dados de BL em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_debug_bl():
    """Debug completo dos dados de BL"""
    print("=" * 80)
    print("DEBUG DETALHADO - CONTRATOS COM/SEM BL")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Cria objeto fake de user
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Executando query...")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quantos contratos de janeiro 2026 ainda não têm número de BL?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")

        # Salva resultado completo
        with open("debug_bl_result.txt", "w", encoding="utf-8") as f:
            f.write(result)
        print("Resultado salvo em: debug_bl_result.txt\n")

        # Extrai JSON
        if "[" in result:
            json_start = result.index("[")
            json_end = result.rindex("]") + 1
            json_str = result[json_start:json_end]
            data = json.loads(json_str)
        else:
            data = json.loads(result)

        print(f"3. Total de clientes: {len(data)}\n")

        # Debug detalhado cliente por cliente
        print("4. ANÁLISE DETALHADA POR CLIENTE:")
        print("-" * 80)

        total_contratos = 0
        total_com_bl = 0
        total_embarcados = 0

        clientes_detalhes = []

        for item in data:
            cliente = item.get("cliente", "N/A").strip()
            contratos = item.get("total_contratos", 0)
            com_bl = item.get("total_contratos_com_bl", 0)
            embarcados = item.get("total_contratos_embarcados", 0)

            sem_bl = contratos - com_bl

            total_contratos += contratos
            total_com_bl += com_bl
            total_embarcados += embarcados

            if contratos > 0:
                clientes_detalhes.append({
                    "cliente": cliente,
                    "total": contratos,
                    "com_bl": com_bl,
                    "sem_bl": sem_bl,
                    "embarcados": embarcados
                })

        # Ordena por total de contratos
        clientes_detalhes.sort(key=lambda x: x["total"], reverse=True)

        # Mostra top 10
        print("\nTop 10 clientes por número de contratos:\n")
        for i, c in enumerate(clientes_detalhes[:10], 1):
            print(f"{i}. {c['cliente']}")
            print(f"   Total: {c['total']} contratos")
            print(f"   COM BL: {c['com_bl']}")
            print(f"   SEM BL: {c['sem_bl']}")
            print(f"   Embarcados: {c['embarcados']}")
            print()

        total_sem_bl = total_contratos - total_com_bl

        print("\n5. TOTALIZADORES:")
        print("-" * 80)
        print(f"Total de contratos: {total_contratos}")
        print(f"Contratos COM BL: {total_com_bl}")
        print(f"Contratos SEM BL: {total_sem_bl}")
        print(f"Contratos embarcados: {total_embarcados}")

        print("\n6. ANÁLISE:")
        print("-" * 80)
        print(f"IA disse: 67 contratos sem BL")
        print(f"Correto é: {total_sem_bl} contratos sem BL")
        print(f"\nNúmero 67 coincide com: embarcados = {total_embarcados}")

        if total_embarcados == 67:
            print("\n⚠️ PROBLEMA IDENTIFICADO:")
            print("A IA está confundindo 'contratos embarcados' (67) com 'contratos sem BL'")
            print(f"O correto seria: {total_sem_bl} contratos sem BL")

        print("\n" + "=" * 80)
        print("DEBUG CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_debug_bl()
