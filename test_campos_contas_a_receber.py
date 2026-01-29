"""
Mapeia todos os campos da função IA_ContasAReceber()
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_mapeamento():
    """Mapeia campos da função IA_ContasAReceber"""
    print("=" * 80)
    print("MAPEAMENTO - IA_ContasAReceber()")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Executando: SELECT * FROM IA_ContasAReceber() WHERE vencimentoReal >= '20250112'")
        print("-" * 80)

        # Executa com filtro
        result = sql_client.execute_function("dbo.IA_ContasAReceber", filters={"vencimentoReal": "20250112"})

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        print(f"[OK] Retornou {len(result)} registros\n")

        # Analisa primeiro registro
        print("3. CAMPOS DISPONÍVEIS (primeiro registro):")
        print("=" * 80)

        primeiro = result[0]
        campos = list(primeiro.keys())

        print(f"Total de campos: {len(campos)}\n")

        for i, campo in enumerate(campos, 1):
            valor = primeiro.get(campo)
            tipo = type(valor).__name__
            valor_str = str(valor)[:50] if valor is not None else "None"
            print(f"{i:2}. {campo:25} ({tipo:10}) = {valor_str}")

        # Estatísticas
        print("\n" + "=" * 80)
        print("4. ESTATÍSTICAS:")
        print("=" * 80)

        print(f"Total de registros: {len(result)}")

        # Clientes únicos
        clientes = set(r.get("cliente", "") for r in result if r.get("cliente"))
        print(f"Clientes únicos: {len(clientes)}")

        # Naturezas únicas
        naturezas = set(r.get("natureza", "") for r in result if r.get("natureza"))
        print(f"Naturezas únicas: {len(naturezas)}")
        if naturezas:
            print(f"  Exemplos: {sorted(list(naturezas))[:5]}")

        # Range de datas
        vencimentos = [r.get("vencimentoReal", "") for r in result if r.get("vencimentoReal")]
        if vencimentos:
            print(f"Vencimentos: {min(vencimentos)} até {max(vencimentos)}")

        # Valores
        from decimal import Decimal
        valores = []
        for r in result:
            valor = r.get("valor", 0)
            if valor is not None:
                if isinstance(valor, Decimal):
                    valores.append(float(valor))
                elif isinstance(valor, (int, float)):
                    valores.append(valor)

        if valores:
            print(f"Valor total: R$ {sum(valores):,.2f}")
            print(f"Valor médio: R$ {sum(valores)/len(valores):,.2f}")
            print(f"Maior valor: R$ {max(valores):,.2f}")

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
    test_mapeamento()
