"""
Validação: Saldo bancário atual
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida saldo bancário"""
    print("=" * 80)
    print("VALIDACAO - Saldo Bancário")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        valores_ia = {
            "Reais": -10621464.26,
            "Dólares": 625953.80,
            "Euros": 11046.33,
            "Libras": 0.00,
        }
        
        print("Saldo por moeda:")
        for moeda, valor in valores_ia.items():
            print(f"  {moeda}: R$ {valor:,.2f}")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_SaldoBancario", filters=None)
        print(f"Total de contas: {len(result) if result else 0}")

        if result:
            # Agrega por moeda
            total_por_moeda = defaultdict(float)

            for r in result:
                moeda = r.get("moeda", "").strip() or "Reais"
                saldo = r.get("saldo", 0)

                if saldo is None:
                    saldo = 0
                elif isinstance(saldo, Decimal):
                    saldo = float(saldo)
                elif isinstance(saldo, str):
                    try:
                        saldo = float(saldo)
                    except:
                        saldo = 0

                total_por_moeda[moeda] += saldo

            print("\nSaldo BANCO por moeda:")
            for moeda in ["Reais", "Dolares", "Euros", "Libras"]:
                if moeda in total_por_moeda:
                    print(f"  {moeda}: R$ {total_por_moeda[moeda]:,.2f}")

            print("\n" + "=" * 80)
            print("COMPARAÇÃO:")
            print("=" * 80)

            matches = 0
            for moeda_ia, valor_ia in valores_ia.items():
                # Converte nome da moeda
                moeda_banco = moeda_ia
                if moeda_ia == "Dólares":
                    moeda_banco = "Dolares"
                
                valor_banco = total_por_moeda.get(moeda_banco, 0)
                diferenca = abs(valor_banco - valor_ia)
                
                print(f"\n{moeda_ia}:")
                print(f"  IA:    R$ {valor_ia:,.2f}")
                print(f"  Banco: R$ {valor_banco:,.2f}")
                print(f"  Dif:   R$ {diferenca:,.2f}")
                
                if diferenca < 1:
                    print(f"  [OK] EXATO!")
                    matches += 1
                else:
                    percentual = (diferenca / abs(valor_ia) * 100) if valor_ia != 0 else 0
                    print(f"  [X] Diferença de {percentual:.2f}%")

            print("\n" + "=" * 80)
            if matches == len(valores_ia):
                print(f"[OK] VALIDACAO 100% CORRETA - {matches}/{len(valores_ia)} moedas validadas!")
            else:
                print(f"[INFO] {matches}/{len(valores_ia)} moedas validadas")

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
    test_validacao()
