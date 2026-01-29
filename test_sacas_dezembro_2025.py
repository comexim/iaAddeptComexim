"""
Valida: Total de sacas exportadas em dezembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal

def test_sacas_dez2025():
    """Valida sacas dezembro 2025"""
    print("=" * 80)
    print("VALIDACAO - Sacas exportadas em dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("IA disse: 650,84 sacas (para FREY A/S)")
        print("Cliente diz que o correto é: 52.013 sacas (TOTAL)")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Executando: SELECT * FROM IA_Vendas() WHERE mesEmbarque = '2025/12'")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas", filters={"mesEmbarque": "2025/12"})

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        print(f"Total de registros: {len(result)}")

        # Calcula total de sacas
        total_sacas = 0
        for r in result:
            peso = r.get("peso", 0)
            if peso is None:
                peso = 0
            elif isinstance(peso, Decimal):
                peso = float(peso)
            elif isinstance(peso, str):
                try:
                    peso = float(peso)
                except:
                    peso = 0

            # Converte peso (kg) para sacas (60kg por saca)
            sacas = peso / 60
            total_sacas += sacas

        print(f"\n4. TOTAL DE SACAS (calculado do banco):")
        print("=" * 80)
        print(f"Total: {total_sacas:,.2f} sacas")

        print("\n5. COMPARAÇÃO:")
        print("=" * 80)
        print(f"IA disse:      650,84 sacas")
        print(f"Cliente disse: 52.013 sacas")
        print(f"Banco tem:     {total_sacas:,.2f} sacas")

        if abs(total_sacas - 52013) < 1:
            print("\n[OK] Cliente está CORRETO! Banco tem 52.013 sacas")
            print("[X] IA está COMPLETAMENTE ERRADA!")
        elif abs(total_sacas - 650.84) < 1:
            print("\n[X] IA está correta, mas cliente está errado")
        else:
            print(f"\n[?] Valor no banco ({total_sacas:,.2f}) não bate nem com IA nem com cliente")

        print("\n6. Por cliente (primeiros 10):")
        print("-" * 80)

        from collections import defaultdict
        por_cliente = defaultdict(float)

        for r in result:
            cliente = r.get("cliente", "").strip() or "SEM CLIENTE"
            peso = r.get("peso", 0)

            if peso is None:
                peso = 0
            elif isinstance(peso, Decimal):
                peso = float(peso)
            elif isinstance(peso, str):
                try:
                    peso = float(peso)
                except:
                    peso = 0

            sacas = peso / 60
            por_cliente[cliente] += sacas

        clientes_ordenados = sorted(por_cliente.items(), key=lambda x: x[1], reverse=True)

        for i, (cliente, sacas) in enumerate(clientes_ordenados[:10], 1):
            print(f"{i:2}. {cliente:40} {sacas:>12,.2f} sacas")

        # Verifica FREY A/S especificamente
        print("\n7. Verificando FREY A/S:")
        print("-" * 80)

        frey_sacas = 0
        for cliente, sacas in clientes_ordenados:
            if "FREY" in cliente.upper():
                frey_sacas = sacas
                print(f"FREY A/S: {sacas:,.2f} sacas")
                break

        if frey_sacas > 0:
            if abs(frey_sacas - 650.84) < 1:
                print("\n[!] IA FILTROU POR FREY A/S quando não deveria!")
                print("    Pergunta era sobre TODAS as sacas, não só FREY A/S")
            else:
                print(f"\n[?] FREY A/S tem {frey_sacas:,.2f} sacas, IA disse 650,84")

        print("\n8. Testando a tool diretamente:")
        print("=" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "quantas sacas de cafe foram exportadas em 12/2025?"

        result_tool = sql_tools._pesquisa_vendas(periodo="12/2025")

        print("\nResposta da tool (primeiros 2000 chars):")
        print(result_tool[:2000])

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
    test_sacas_dez2025()
