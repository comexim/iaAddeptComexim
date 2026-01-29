"""
Investiga em detalhe o cliente NESTLE ARARAS em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_nestle_araras():
    """Analisa NESTLE ARARAS em janeiro 2026"""
    print("=" * 80)
    print("INVESTIGACAO - NESTLE ARARAS JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026
        print("2. Consultando NESTLE ARARAS em janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        # Filtra apenas NESTLE ARARAS
        nestle_contratos = [r for r in results if "NESTLE ARARAS" in r.get("cliente", "").upper()]

        if not nestle_contratos:
            print("[AVISO] Nenhum contrato NESTLE ARARAS encontrado")
            return

        print(f"[OK] {len(nestle_contratos)} contratos NESTLE ARARAS\n")

        # Mostra todos os contratos
        print("3. CONTRATOS NESTLE ARARAS:")
        print("-" * 80)

        diferenciais = []
        total_sacas = 0
        total_valor = 0

        for i, contrato in enumerate(nestle_contratos, 1):
            dif = contrato.get("diferencial")
            sacas = contrato.get("sacas", 0) or 0
            valor = contrato.get("valorTotal", 0) or 0

            print(f"\nContrato {i}: {contrato.get('contrato', 'N/A')}")
            print(f"  Cliente: {contrato.get('cliente', 'N/A')}")
            print(f"  Diferencial: {dif}")
            print(f"  Sacas: {sacas:,.2f}")
            print(f"  Valor Total: R$ {valor:,.2f}")
            print(f"  Emissao: {contrato.get('emissao', 'N/A')}")
            print(f"  Mes Embarque: {contrato.get('mesEmbarque', 'N/A')}")

            if dif is not None:
                diferenciais.append(float(dif))

            total_sacas += sacas
            total_valor += valor

        # Calcula média
        print("\n" + "-" * 80)
        print("4. RESUMO:")
        print("-" * 80)
        print(f"Total de contratos: {len(nestle_contratos)}")
        print(f"Total de sacas: {total_sacas:,.2f}")
        print(f"Total de valor: R$ {total_valor:,.2f}")

        if diferenciais:
            media = sum(diferenciais) / len(diferenciais)
            print(f"\nDiferenciais encontrados: {diferenciais}")
            print(f"Soma dos diferenciais: {sum(diferenciais):.2f}")
            print(f"Quantidade de diferenciais: {len(diferenciais)}")
            print(f"MEDIA CALCULADA: {media:.2f}")
        else:
            print("\nNenhum diferencial encontrado!")

        print("\n5. COMPARACAO:")
        print("-" * 80)
        print(f"IA disse: 13.00")
        print(f"Banco tem: {media:.2f}")
        print(f"Diferenca: {abs(13.00 - media):.2f}")

        print("\n" + "=" * 80)
        print("[OK] INVESTIGACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_nestle_araras()
