"""
Verifica o formato exato do campo valor
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_field_format():
    """Verifica formato do campo valor"""
    print("=" * 80)
    print("TESTE - Formato do campo valor")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Consultando contas pagas...")
        result = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251201"})

        if not result:
            print("[ERRO] Nenhum resultado")
            return

        print(f"[OK] {len(result)} registros retornados\n")

        # Pega primeiro registro
        primeiro = result[0]

        print("=" * 80)
        print("PRIMEIRO REGISTRO - TODOS OS CAMPOS:")
        print("=" * 80)

        for campo, valor in primeiro.items():
            tipo = type(valor).__name__
            print(f"{campo:20} = {valor!r:50} (tipo: {tipo})")

        print("\n" + "=" * 80)
        print("ANALISE DO CAMPO 'valor':")
        print("=" * 80)

        valor_campo = primeiro.get("valor")
        print(f"Valor bruto: {valor_campo!r}")
        print(f"Tipo: {type(valor_campo).__name__}")
        print(f"Comprimento: {len(str(valor_campo))}")

        # Tenta diferentes conversoes
        print("\nTentativas de conversao:")
        print("-" * 40)

        try:
            valor_float = float(valor_campo)
            print(f"float(valor_campo) = {valor_float:,.2f}")
        except Exception as e:
            print(f"float(valor_campo) FALHOU: {e}")

        try:
            valor_limpo = str(valor_campo).replace("R$", "").replace(".", "").replace(",", ".").strip()
            print(f"Apos limpeza: '{valor_limpo}'")
            valor_float = float(valor_limpo)
            print(f"float(valor_limpo) = {valor_float:,.2f}")
        except Exception as e:
            print(f"float(valor_limpo) FALHOU: {e}")

        # Verifica valorStr tambem
        print("\n" + "=" * 80)
        print("ANALISE DO CAMPO 'valorStr':")
        print("=" * 80)

        valorStr = primeiro.get("valorStr")
        print(f"valorStr bruto: {valorStr!r}")
        print(f"Tipo: {type(valorStr).__name__}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_field_format()
