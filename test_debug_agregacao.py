"""
Debug: verifica se campos específicos estão na agregação
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_debug_agregacao():
    """Testa se campos jan2026 estão no output"""
    print("=" * 80)
    print("DEBUG - VERIFICANDO CAMPOS NA AGREGACAO")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Simula query SEM filtro (como IA faz para "baixados EM janeiro 2026")
        print("2. Executando pesquisa_vendas(periodo=None)...")

        # Cria objeto fake de user
        class FakeUser:
            phone_number = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        result = sql_tools._pesquisa_vendas(periodo=None)

        print(f"[OK] Retornou {len(result) if isinstance(result, list) else 'N/A'} items\n")
        print(f"DEBUG - Tipo: {type(result)}")
        print(f"DEBUG - Primeiros 200 chars: {str(result)[:200]}\n")

        # Verifica se é lista ou string JSON
        if isinstance(result, str):
            print("3. Resultado é STRING (JSON). Convertendo...")
            if not result or result.strip() == "":
                print("[ERRO] Resultado vazio!")
                return
            data = json.loads(result)
        else:
            print("3. Resultado é LISTA. Usando diretamente...")
            data = result

        # Procura por campos específicos no primeiro cliente
        print("\n4. VERIFICANDO CAMPOS NO PRIMEIRO CLIENTE:")
        print("-" * 80)

        if data and len(data) > 0:
            primeiro = data[0]
            print(f"\nCliente: {primeiro.get('cliente', 'N/A')}")
            print(f"\nCampos disponíveis:")
            for key in sorted(primeiro.keys()):
                value = primeiro[key]
                if isinstance(value, str) and len(value) > 100:
                    print(f"  - {key}: {value[:100]}... (truncado)")
                else:
                    print(f"  - {key}: {value}")

            # Verifica especificamente os campos jan2026
            print("\n5. VERIFICANDO CAMPOS JAN2026:")
            print("-" * 80)

            if "contratos_baixados_jan2026" in primeiro:
                print(f"✓ contratos_baixados_jan2026 EXISTE")
                print(f"  Valor: {primeiro['contratos_baixados_jan2026'][:200]}")
            else:
                print("✗ contratos_baixados_jan2026 NÃO EXISTE")

            if "total_baixados_jan2026" in primeiro:
                print(f"✓ total_baixados_jan2026 EXISTE")
                print(f"  Valor: {primeiro['total_baixados_jan2026']}")
            else:
                print("✗ total_baixados_jan2026 NÃO EXISTE")

            # Procura clientes com jan2026 > 0
            print("\n6. PROCURANDO CLIENTES COM BAIXADOS EM JAN/2026:")
            print("-" * 80)

            clientes_com_jan = []
            for item in data[:50]:  # Primeiros 50
                total_jan = item.get("total_baixados_jan2026", 0)
                if total_jan > 0:
                    clientes_com_jan.append({
                        "cliente": item.get("cliente"),
                        "total": total_jan,
                        "contratos": item.get("contratos_baixados_jan2026", "")[:100]
                    })

            if clientes_com_jan:
                print(f"\n[OK] Encontrados {len(clientes_com_jan)} clientes\n")
                for i, item in enumerate(clientes_com_jan[:10], 1):
                    print(f"{i}. {item['cliente']}: {item['total']} contratos")
                    print(f"   {item['contratos']}")
            else:
                print("\n[ERRO] Nenhum cliente com total_baixados_jan2026 > 0")
                print("POSSÍVEL CAUSA: Campos não estão sendo preenchidos corretamente")

        else:
            print("[ERRO] Nenhum dado retornado")

        print("\n" + "=" * 80)
        print("[OK] DEBUG CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_debug_agregacao()
