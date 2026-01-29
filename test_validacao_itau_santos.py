"""
Validação: Saldo no Itaú Santos
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_validacao():
    """Valida saldo do Itaú Santos"""
    print("=" * 80)
    print("VALIDACAO - Itaú Santos")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Conta em Reais: R$ -7.750.000,00 (saldo devedor)")
        print("Conta em Dólares: R$ 500.000,00 (saldo positivo)")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_SaldoBancario", filters=None)
        print(f"Total de contas: {len(result) if result else 0}")

        if result:
            # Filtra apenas bancos com "ITAU" e "STOS" no nome
            itau_santos = [r for r in result if "ITAU STOS" in str(r.get("banco", "")).upper()]
            
            print(f"\nContas 'ITAU STOS' encontradas: {len(itau_santos)}")
            
            if itau_santos:
                print("\nDetalhamento:")
                print("-" * 80)
                
                for conta in itau_santos:
                    banco = conta.get("banco", "").strip()
                    moeda = conta.get("moeda", "").strip()
                    agencia = conta.get("agencia", "").strip()
                    conta_num = conta.get("conta", "").strip()
                    saldo = conta.get("saldo", 0)
                    
                    if isinstance(saldo, Decimal):
                        saldo = float(saldo)
                    
                    print(f"\nBanco: {banco}")
                    print(f"Moeda: {moeda}")
                    print(f"Agência: {agencia}")
                    print(f"Conta: {conta_num}")
                    print(f"Saldo: R$ {saldo:,.2f}")
            
            # Verifica também outras contas Itaú
            print("\n" + "=" * 80)
            print("TODAS AS CONTAS ITAÚ (qualquer tipo):")
            print("=" * 80)
            
            todas_itau = [r for r in result if "ITAU" in str(r.get("banco", "")).upper()]
            print(f"\nTotal de contas Itaú: {len(todas_itau)}")
            
            for conta in todas_itau:
                banco = conta.get("banco", "").strip()
                moeda = conta.get("moeda", "").strip()
                saldo = conta.get("saldo", 0)
                
                if isinstance(saldo, Decimal):
                    saldo = float(saldo)
                
                print(f"{banco:25} | {moeda:10} | R$ {saldo:>15,.2f}")

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
