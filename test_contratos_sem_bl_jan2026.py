"""
Testa query sobre contratos sem BL em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_contratos_sem_bl_jan2026():
    """Testa query sobre contratos sem BL"""
    print("=" * 80)
    print("TESTE - CONTRATOS SEM BL EM JANEIRO 2026")
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

        print("2. Query: 'Quantos contratos de janeiro 2026 ainda não têm número de BL?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quantos contratos de janeiro 2026 ainda não têm número de BL?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")
        print(f"DEBUG - Tamanho: {len(result) if isinstance(result, list) else len(str(result))}")

        # Verifica se é lista ou string JSON
        if isinstance(result, str):
            # Salva em arquivo
            with open("test_sem_bl_result.txt", "w", encoding="utf-8") as f:
                f.write(result)
            print("Resultado salvo em: test_sem_bl_result.txt\n")

            if not result or result.strip() == "":
                print("[ERRO] Resultado vazio!")
                return
            if result.startswith("PRECISA_"):
                print(f"[ERRO] {result}")
                return

            # Extrai JSON da resposta formatada
            if "[" in result:
                json_start = result.index("[")
                json_end = result.rindex("]") + 1
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
            else:
                data = json.loads(result)
        else:
            data = result

        print(f"3. Total de clientes retornados: {len(data)}\n")

        # Verifica primeiro cliente
        print("4. VERIFICANDO CAMPOS NO PRIMEIRO CLIENTE:")
        print("-" * 80)

        if data:
            primeiro = data[0]
            print(f"\nCliente: {primeiro.get('cliente', 'N/A')}")
            print(f"\nCampos relacionados a BL:")
            if "contratos_com_bl" in primeiro:
                print(f"  - contratos_com_bl: {primeiro['contratos_com_bl'][:100] if primeiro['contratos_com_bl'] else 'vazio'}")
            if "total_contratos_com_bl" in primeiro:
                print(f"  - total_contratos_com_bl: {primeiro['total_contratos_com_bl']}")
            if "total_contratos" in primeiro:
                print(f"  - total_contratos: {primeiro['total_contratos']}")

        # Calcula total de contratos COM BL e SEM BL
        print("\n\n5. CALCULANDO CONTRATOS COM/SEM BL:")
        print("-" * 80)

        total_contratos = 0
        total_com_bl = 0

        for item in data:
            contratos = item.get("total_contratos", 0)
            com_bl = item.get("total_contratos_com_bl", 0)

            total_contratos += contratos
            total_com_bl += com_bl

        total_sem_bl = total_contratos - total_com_bl

        print(f"\nTotal de contratos: {total_contratos}")
        print(f"Contratos COM BL: {total_com_bl}")
        print(f"Contratos SEM BL: {total_sem_bl}")

        # Verifica resposta da IA
        print("\n\n6. VALIDANDO RESPOSTA DA IA:")
        print("-" * 80)
        print("IA disse: '107 contratos, 67 ainda não têm número de BL'")
        print(f"\nDados reais:")
        print(f"  Total de contratos: {total_contratos} (IA disse: 107)")
        print(f"  Sem BL: {total_sem_bl} (IA disse: 67)")

        if total_contratos == 107 and total_sem_bl == 67:
            print("\n✓ RESPOSTA DA IA ESTÁ CORRETA!")
        else:
            print("\n✗ RESPOSTA DA IA ESTÁ ERRADA!")
            print(f"  Correto seria: {total_contratos} contratos, {total_sem_bl} sem BL")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_contratos_sem_bl_jan2026()
