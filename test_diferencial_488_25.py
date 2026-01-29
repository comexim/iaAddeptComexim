"""
Valida: Diferencial do contrato 488/25 (sem valor fixado)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal

def test_diferencial():
    """Valida diferencial do contrato 488/25"""
    print("=" * 80)
    print("VALIDACAO - Diferencial do contrato 488/25")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("User: quantos contratos de exportação em 12/2025 não tem valor fixado?")
        print("IA: 1 contrato (CORRETO)")
        print("")
        print("User: e qual é o diferencial desse contrato?")
        print("IA: 0,00 (ERRADO)")
        print("Cliente diz: -53,75 (print mostra diferencial -53.75)")

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

        print("\n4. Filtrando contratos SEM valor fixado (valorFixado IS NULL ou = 0)")
        print("-" * 80)

        sem_fixacao = []
        for r in result:
            valor_fixado = r.get("valorFixado")

            # Considera NULL ou 0 como "sem fixação"
            if valor_fixado is None or valor_fixado == 0 or valor_fixado == 0.0:
                sem_fixacao.append(r)

        print(f"Contratos sem fixação: {len(sem_fixacao)}")

        print("\n5. TODOS OS CONTRATOS SEM FIXAÇÃO:")
        print("=" * 80)

        for i, r in enumerate(sem_fixacao, 1):
            contrato = r.get("contrato", "").strip()
            cliente = r.get("cliente", "").strip()
            diferencial = r.get("diferencial")
            valor_fixado = r.get("valorFixado")

            # Converte diferencial
            if diferencial is None:
                diferencial = 0.0
            elif isinstance(diferencial, Decimal):
                diferencial = float(diferencial)

            # Converte valor fixado
            if valor_fixado is None:
                valor_fixado_str = "NULL"
            elif isinstance(valor_fixado, Decimal):
                valor_fixado_str = f"{float(valor_fixado):,.2f}"
            else:
                valor_fixado_str = f"{valor_fixado:,.2f}"

            print(f"{i}. Contrato: {contrato:10} Cliente: {cliente:35} Diferencial: {diferencial:>8.2f}  ValorFixado: {valor_fixado_str}")

        print("\n6. FOCO NO CONTRATO 488/25:")
        print("=" * 80)

        contrato_488 = None
        for r in sem_fixacao:
            if "488/25" in r.get("contrato", ""):
                contrato_488 = r
                break

        if not contrato_488:
            print("[X] Contrato 488/25 NÃO encontrado nos contratos sem fixação!")
            print("    Verificando se ele existe na lista completa...")

            for r in result:
                if "488/25" in r.get("contrato", ""):
                    print(f"\n[!] Contrato 488/25 EXISTE mas tem valor fixado!")
                    valor_fixado = r.get("valorFixado")
                    if isinstance(valor_fixado, Decimal):
                        valor_fixado = float(valor_fixado)
                    print(f"    ValorFixado: {valor_fixado}")
                    break
        else:
            print("[OK] Contrato 488/25 encontrado!")
            print(f"\nCliente: {contrato_488.get('cliente', '')}")

            diferencial = contrato_488.get("diferencial")
            valor_fixado = contrato_488.get("valorFixado")

            if diferencial is None:
                diferencial_float = 0.0
            elif isinstance(diferencial, Decimal):
                diferencial_float = float(diferencial)
            else:
                diferencial_float = float(diferencial)

            print(f"Diferencial no banco: {diferencial_float}")
            print(f"ValorFixado no banco: {valor_fixado}")

            print("\n7. COMPARAÇÃO:")
            print("-" * 80)
            print(f"IA disse:      0,00")
            print(f"Cliente disse: -53,75")
            print(f"Banco tem:     {diferencial_float}")

            if abs(diferencial_float - (-53.75)) < 0.01:
                print("\n[OK] Cliente está CORRETO! Diferencial é -53,75")
                print("[X] IA está COMPLETAMENTE ERRADA!")
            elif abs(diferencial_float) < 0.01:
                print("\n[X] Banco realmente tem diferencial 0,00")
                print("    Cliente pode estar vendo dados diferentes")
            else:
                print(f"\n[?] Banco tem valor diferente: {diferencial_float}")

        print("\n8. Testando a tool diretamente:")
        print("=" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        # Primeira pergunta
        print("\n[Pergunta 1]")
        print("User: quantos contratos de exportação em 12/2025 não tem valor fixado?")
        sql_tools.user_query = "quantos contratos de exportação em 12/2025 não tem valor fixado?"
        result1 = sql_tools._pesquisa_vendas(periodo="12/2025")

        # Busca informação sobre 488/25
        print("\nProcurando 488/25 na resposta da tool...")
        linhas = result1.split('\n')

        # Procura nas linhas agregadas por cliente
        encontrou_488 = False
        for i, linha in enumerate(linhas):
            if "488/25" in linha or "COMEXIM EUROPE" in linha:
                print(f"\nLinha {i}: {linha[:150]}")
                # Mostra algumas linhas ao redor
                for j in range(max(0, i-3), min(len(linhas), i+10)):
                    if "diferencial" in linhas[j].lower():
                        print(f"  Linha {j}: {linhas[j][:150]}")
                encontrou_488 = True
                break

        if not encontrou_488:
            print("[X] 488/25 não encontrado na resposta da tool")

        # Segunda pergunta (simulando contexto)
        print("\n\n[Pergunta 2]")
        print("User: e qual é o diferencial desse contrato?")
        sql_tools.user_query = "e qual é o diferencial desse contrato?"
        result2 = sql_tools._pesquisa_vendas(periodo="12/2025")

        print("\nProcurando diferencial do 488/25 na segunda resposta...")
        for i, linha in enumerate(result2.split('\n')):
            if "488/25" in linha or "COMEXIM EUROPE" in linha:
                print(f"\nLinha {i}: {linha[:150]}")
                # Mostra linhas ao redor
                for j in range(max(0, i-3), min(len(linhas), i+10)):
                    if "diferencial" in result2.split('\n')[j].lower():
                        print(f"  Linha {j}: {result2.split('\n')[j][:150]}")
                break

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
    test_diferencial()
