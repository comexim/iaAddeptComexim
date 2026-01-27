"""
Mapeia TODOS os campos da função IA_ContasPagas() - FINANCEIRO
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_campos_contas_pagas():
    """Mapeia campos de IA_ContasPagas()"""
    print("=" * 80)
    print("MAPEAMENTO COMPLETO - IA_ContasPagas() - FINANCEIRO")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Executando: SELECT * FROM IA_ContasPagas() WHERE emissao >= '20251205'")
        result = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251205"})

        if not result:
            print("[AVISO] Nenhum resultado retornado")
            print("\nTentando sem filtro...")
            result = sql_client.execute_function("dbo.IA_ContasPagas", filters=None)

        if not result:
            print("[ERRO] Ainda sem resultados")
            return

        print(f"[OK] {len(result)} registros retornados\n")

        # Pega o primeiro registro para mapear colunas
        primeiro = result[0]
        colunas = list(primeiro.keys())

        print("=" * 80)
        print(f"TOTAL DE COLUNAS: {len(colunas)}")
        print("=" * 80)

        print("\nLISTA COMPLETA DE COLUNAS:")
        print("-" * 80)
        for i, col in enumerate(colunas, 1):
            valor = primeiro[col]
            tipo = type(valor).__name__

            # Mostra valor de exemplo (limitado)
            if isinstance(valor, str):
                valor_exemplo = valor[:50] if len(str(valor)) > 50 else valor
            elif isinstance(valor, Decimal):
                valor_exemplo = f"{float(valor):,.2f}"
            else:
                valor_exemplo = valor

            print(f"{i:3}. {col:35} ({tipo:10}) = {valor_exemplo}")

        print("\n" + "=" * 80)
        print("EXEMPLOS DE REGISTROS:")
        print("=" * 80)
        for i, reg in enumerate(result[:5], 1):
            print(f"\nRegistro {i}:")
            # Tenta mostrar campos principais
            for key in ['emissao', 'vencimento', 'fornecedor', 'descricao', 'valor', 'valorPago', 'dataPagamento']:
                if key in reg:
                    valor = reg[key]
                    if isinstance(valor, Decimal):
                        print(f"  {key}: {float(valor):,.2f}")
                    else:
                        print(f"  {key}: {valor}")

        print("\n" + "=" * 80)
        print("ANÁLISE DE TIPOS DE DADOS:")
        print("=" * 80)

        # Agrupa colunas por tipo
        tipos = {}
        for col in colunas:
            tipo = type(primeiro[col]).__name__
            if tipo not in tipos:
                tipos[tipo] = []
            tipos[tipo].append(col)

        for tipo, cols in sorted(tipos.items()):
            print(f"\n{tipo} ({len(cols)} colunas):")
            for col in cols:
                print(f"  - {col}")

        print("\n" + "=" * 80)
        print("VALIDAÇÃO DE DADOS:")
        print("=" * 80)

        # Verifica dados nulos/vazios
        print("\nColunas com valores nulos/vazios no primeiro registro:")
        for col in colunas:
            valor = primeiro[col]
            if valor is None or (isinstance(valor, str) and valor.strip() == ""):
                print(f"  - {col}: {valor}")

        # Estatísticas gerais
        print(f"\n\nTotal de registros analisados: {len(result)}")
        print(f"Total de colunas mapeadas: {len(colunas)}")

        print("\n" + "=" * 80)
        print("[OK] MAPEAMENTO COMPLETO CONCLUÍDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_campos_contas_pagas()
