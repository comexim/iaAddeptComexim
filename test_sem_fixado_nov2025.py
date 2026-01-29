"""
Valida: Contratos sem valor fixado em novembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_nov2025():
    """Valida contratos sem fixação em nov/2025"""
    print("=" * 80)
    print("VALIDACAO - Contratos sem valor fixado em novembro 2025")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("IA disse: 'não houve contratos sem valor fixado'")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Executando: SELECT * FROM IA_Vendas() WHERE mesEmbarque = '2025/11'")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas", filters={"mesEmbarque": "2025/11"})

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        print(f"Total de registros em novembro/2025: {len(result)}")

        print("\n4. Filtrando contratos SEM valor fixado")
        print("-" * 80)

        sem_fixacao = []
        for r in result:
            valor_fixado = r.get("valorFixado")

            # Considera NULL ou 0 como "sem fixação"
            if valor_fixado is None or valor_fixado == 0 or valor_fixado == 0.0:
                sem_fixacao.append(r)

        print(f"Contratos sem fixação em novembro: {len(sem_fixacao)}")

        if len(sem_fixacao) == 0:
            print("\n[OK] IA está CORRETA - Não há contratos sem fixação em novembro/2025")
        else:
            print(f"\n[X] IA está INCORRETA - Há {len(sem_fixacao)} contrato(s) sem fixação!")
            print("\nContratos sem fixação:")
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

        print("\n5. Estatísticas gerais de novembro:")
        print("-" * 80)
        total_contratos = len(result)
        contratos_fixados = total_contratos - len(sem_fixacao)
        percentual_fixado = (contratos_fixados / total_contratos * 100) if total_contratos > 0 else 0

        print(f"Total de contratos: {total_contratos}")
        print(f"Contratos com valor fixado: {contratos_fixados}")
        print(f"Contratos SEM valor fixado: {len(sem_fixacao)}")
        print(f"Percentual fixado: {percentual_fixado:.1f}%")

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
    test_nov2025()
