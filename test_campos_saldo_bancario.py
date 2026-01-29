"""
Mapeia campos de IA_SaldoBancario
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
import json
from decimal import Decimal

def test_campos():
    """Mapeia todos os campos"""
    print("=" * 80)
    print("MAPEAMENTO - IA_SaldoBancario")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Executando: IA_SaldoBancario()")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_SaldoBancario", filters=None)

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        print(f"Total de registros: {len(result)}")

        print("\n3. CAMPOS MAPEADOS:")
        print("-" * 80)

        # Pega primeiro registro para ver estrutura
        if result:
            primeiro = result[0]
            print(f"\nTotal de campos: {len(primeiro.keys())}")
            print("\nNomes dos campos:")
            for i, campo in enumerate(sorted(primeiro.keys()), 1):
                tipo = type(primeiro[campo]).__name__
                valor = primeiro[campo]
                if isinstance(valor, Decimal):
                    valor = float(valor)
                print(f"{i:2}. {campo:30} ({tipo:10}) = {valor}")

        print("\n4. PRIMEIROS 5 REGISTROS (amostra):")
        print("-" * 80)

        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        for i, registro in enumerate(result[:5], 1):
            print(f"\nRegistro {i}:")
            print(json.dumps(registro, ensure_ascii=False, indent=2, default=convert_decimals))

        # Estatísticas
        print("\n" + "=" * 80)
        print("ESTATÍSTICAS:")
        print("=" * 80)

        # Conta bancos únicos
        bancos = set()
        total_saldo = 0

        for r in result:
            banco = r.get("banco", "").strip()
            if banco:
                bancos.add(banco)

            saldo = r.get("saldo", 0)
            if isinstance(saldo, Decimal):
                saldo = float(saldo)
            elif saldo is None:
                saldo = 0
            total_saldo += saldo

        print(f"\nTotal de registros: {len(result)}")
        print(f"Bancos únicos: {len(bancos)}")
        print(f"Saldo total: R$ {total_saldo:,.2f}")

        if bancos:
            print(f"\nBancos encontrados:")
            for banco in sorted(bancos):
                print(f"  - {banco}")

        print("\n" + "=" * 80)
        print("[OK] MAPEAMENTO CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_campos()
