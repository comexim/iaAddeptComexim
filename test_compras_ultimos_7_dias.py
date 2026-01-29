"""
Testa compras dos últimos 7 dias
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_compras_ultimos_7_dias():
    """Testa compras dos últimos 7 dias"""
    print("=" * 80)
    print("TESTE - Compras dos últimos 7 dias")
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

        print("2. Testando: 'Quais foram as compras dos últimos 7 dias?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais foram as compras dos últimos 7 dias?"

        result = sql_tools._pesquisa_compras(data_inicio="últimos 7 dias")

        print(f"[OK] Retornou resultado\n")

        # Salva resultado para análise
        with open("compras_ultimos_7_dias_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        print("Resultado salvo em: compras_ultimos_7_dias_result.txt\n")

        # Extrai JSON se possível
        if isinstance(result, str):
            if "[" in result:
                json_start = result.index("[")
                json_end = result.rindex("]") + 1
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
            else:
                print("Resultado não contém JSON")
                print(result[:1000])
                return
        else:
            data = result

        print("3. COMPARAÇÃO COM RESPOSTA DA IA:")
        print("-" * 80)
        print("Resposta da IA:")
        print("1. Pedido 969388 da AJ Coffee Comércio e Exportação de Café, R$ 2.527.000,00")
        print("2. Pedido 544314 da Cooxupé, R$ 1.940.000,00")
        print("3. Pedido 969389 da Coop. M. Carmelo, R$ 192.000,00")
        print("4. Pedido 969390 da Coop dos Cafeic de Campos Gerais e Campo, R$ 1.018.600,01")
        print("5. Pedido 969487 de Luiz Carlos Figueiredo, R$ 5.000.000,00")
        print()

        print("Dados do banco:")
        print("-" * 80)

        # Como os dados vêm agregados por cliente, precisamos procurar nos detalhes
        if isinstance(data, list) and len(data) > 0:
            # Verifica se tem campo com lista de contratos/pedidos
            primeiro = data[0]
            print(f"Total de clientes retornados: {len(data)}")
            print(f"\nCampos do primeiro registro:")
            for key in primeiro.keys():
                print(f"  - {key}")

            # Procura por pedidos específicos nos dados
            print("\n\nPROCURANDO PEDIDOS MENCIONADOS PELA IA:")
            print("-" * 80)

            pedidos_ia = {
                "969388": "AJ Coffee",
                "544314": "Cooxupé",
                "969389": "Coop. M. Carmelo",
                "969390": "Coop dos Cafeic",
                "969487": "Luiz Carlos Figueiredo"
            }

            # Verifica se tem campo "contratos" ou similar
            for cliente_data in data:
                contratos_field = cliente_data.get("contratos", cliente_data.get("numeros", ""))
                if contratos_field and isinstance(contratos_field, str):
                    for pedido, nome in pedidos_ia.items():
                        if pedido in contratos_field:
                            print(f"✓ Pedido {pedido} encontrado no cliente: {cliente_data.get('cliente', 'N/A')}")

        print("\n\n4. VERIFICAÇÃO DIRETA NO BANCO:")
        print("-" * 80)

        # Calcula data de 7 dias atrás
        from datetime import datetime, timedelta
        hoje = datetime.now()
        sete_dias_atras = hoje - timedelta(days=7)
        data_filtro = sete_dias_atras.strftime("%Y%m%d")

        print(f"Filtro: emissao >= {data_filtro}")

        result_direto = sql_client.execute_function("dbo.IA_Compras", filters={"emissao": data_filtro})

        if result_direto and len(result_direto) > 0:
            print(f"Total de registros: {len(result_direto)}\n")

            print("Procurando pedidos mencionados pela IA:")
            for pedido, nome in pedidos_ia.items():
                encontrado = [r for r in result_direto if r.get("numero") == pedido or str(r.get("numero")) == pedido]
                if encontrado:
                    reg = encontrado[0]
                    print(f"\n[OK] Pedido {pedido}:")
                    print(f"  Fornecedor: {reg.get('FORNEC', 'N/A')}")
                    print(f"  Valor Total: R$ {reg.get('valorTotal', 0):,.2f}")
                    print(f"  Emissao: {reg.get('emissao', 'N/A')}")
                    print(f"  Sacas: {reg.get('sacas', 0)}")
                else:
                    print(f"\n[X] Pedido {pedido} NAO encontrado")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_compras_ultimos_7_dias()
