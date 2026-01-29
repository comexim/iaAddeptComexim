"""
Valida: Contratos para Argentina em dezembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal

def test_argentina():
    """Valida contratos Argentina"""
    print("=" * 80)
    print("VALIDACAO - Argentina em dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Sacas: 1.320")
        print("Contratos: 558/25, 559/25")
        print("FALTOU: 513/25")

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

        print("\n4. Filtrando por país = ARGENTINA")
        print("-" * 80)

        argentina = []
        for r in result:
            pais = r.get("pais", "").strip().upper()
            if "ARGENT" in pais:
                argentina.append(r)

        print(f"Contratos para Argentina: {len(argentina)}")

        if not argentina:
            print("\n[X] NENHUM contrato para Argentina encontrado!")

            # Lista todos os países
            print("\nPaíses encontrados (únicos):")
            paises = set()
            for r in result:
                pais = r.get("pais", "").strip()
                if pais:
                    paises.add(pais)
            for pais in sorted(paises):
                print(f"  - {pais}")
            return

        print("\n5. TODOS OS CONTRATOS PARA ARGENTINA:")
        print("=" * 80)

        total_sacas = 0
        for i, r in enumerate(argentina, 1):
            contrato = r.get("contrato", "").strip()
            cliente = r.get("cliente", "").strip()
            peso = r.get("peso", 0)

            if peso is None:
                peso = 0
            elif isinstance(peso, Decimal):
                peso = float(peso)

            sacas = peso / 60
            total_sacas += sacas

            pais = r.get("pais", "").strip()

            print(f"{i:2}. Contrato: {contrato:10} Cliente: {cliente:30} Sacas: {sacas:>8,.2f}  País: {pais}")

        print(f"\nTotal de sacas: {total_sacas:,.2f}")

        print("\n6. VERIFICANDO OS 3 CONTRATOS:")
        print("=" * 80)

        contratos_esperados = ["513/25", "558/25", "559/25"]
        contratos_encontrados = [r.get("contrato", "").strip() for r in argentina]

        for contrato in contratos_esperados:
            if any(contrato in c for c in contratos_encontrados):
                print(f"✓ {contrato}: ENCONTRADO")
            else:
                print(f"✗ {contrato}: NÃO ENCONTRADO")

        print("\n7. Testando agregação por cliente:")
        print("-" * 80)

        from collections import defaultdict
        por_cliente = defaultdict(lambda: {"contratos": [], "sacas": 0})

        for r in argentina:
            cliente = r.get("cliente", "").strip() or "SEM CLIENTE"
            contrato = r.get("contrato", "").strip()
            peso = r.get("peso", 0)

            if peso is None:
                peso = 0
            elif isinstance(peso, Decimal):
                peso = float(peso)

            sacas = peso / 60

            por_cliente[cliente]["contratos"].append(contrato)
            por_cliente[cliente]["sacas"] += sacas

        print("\nPor cliente:")
        for cliente, dados in por_cliente.items():
            contratos_str = ", ".join(dados["contratos"])
            print(f"{cliente:40} {dados['sacas']:>8,.2f} sacas")
            print(f"  Contratos: {contratos_str}")

        print("\n8. PROBLEMA IDENTIFICADO:")
        print("=" * 80)

        # Verifica se há múltiplos clientes
        if len(por_cliente) > 1:
            print(f"\n[!] Há {len(por_cliente)} clientes diferentes para Argentina!")
            print("    A agregação por cliente separa os contratos por cliente.")
            print("    O campo 'contratos' em cada cliente mostra apenas os primeiros 10 contratos DAQUELE cliente.")
            print("    Se a IA olhar apenas 1 cliente, vai perder os contratos dos outros clientes!")
        else:
            print("\n[OK] Todos os contratos são do mesmo cliente")
            cliente_unico = list(por_cliente.keys())[0]
            qtd_contratos = len(por_cliente[cliente_unico]["contratos"])
            print(f"    Cliente: {cliente_unico}")
            print(f"    Quantidade de contratos: {qtd_contratos}")
            if qtd_contratos > 10:
                print(f"    [!] PROBLEMA: São {qtd_contratos} contratos, mas o campo 'contratos' só mostra os 10 primeiros!")

        print("\n9. Testando a tool diretamente:")
        print("=" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        # Simula a conversa
        print("\n[Conversa simulada]")
        print("User: quantas sacas de cafe foram exportadas em 12/2025?")
        sql_tools.user_query = "quantas sacas de cafe foram exportadas em 12/2025?"
        result1 = sql_tools._pesquisa_vendas(periodo="12/2025")
        print(f"Tool: {result1[:500]}")

        print("\n\nUser: quantas dessas sacas foram para a Argentina?")
        sql_tools.user_query = "quantas dessas sacas foram para a Argentina?"
        result2 = sql_tools._pesquisa_vendas(periodo="12/2025")

        # Verifica se a agregação inclui filtro por país
        if "ARGENT" in result2.upper():
            print("\n[OK] Tool retornou dados com Argentina")

            # Busca a linha com contratos
            linhas = result2.split('\n')
            for i, linha in enumerate(linhas):
                if '"contratos":' in linha or 'Contratos:' in linha:
                    print(f"\nLinha de contratos encontrada:")
                    print(linha[:200])
                    # Mostra algumas linhas ao redor
                    for j in range(max(0, i-2), min(len(linhas), i+3)):
                        if 'cliente' in linhas[j].lower() or 'argent' in linhas[j].lower():
                            print(linhas[j][:100])
        else:
            print("\n[X] Tool NÃO retornou dados específicos de Argentina")
            print("    A IA precisa filtrar manualmente pelos dados retornados")

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
    test_argentina()
