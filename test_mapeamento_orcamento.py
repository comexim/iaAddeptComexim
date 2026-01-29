"""
Mapeamento completo: IA_Orcamento()
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
import json

def test_mapeamento():
    """Mapeia todas as colunas de IA_Orcamento"""
    print("=" * 80)
    print("MAPEAMENTO COMPLETO - IA_Orcamento()")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Executando: SELECT * FROM IA_Orcamento() WHERE ano >= '2025' AND mes = '12'")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Orcamento", filters={"ano": "2025", "mes": "12"})

        if not result:
            print("[AVISO] Nenhum resultado para dez/2025, tentando ano completo...")
            result = sql_client.execute_function("dbo.IA_Orcamento", filters={"ano": "2025"})

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        print(f"Total de registros: {len(result)}")

        print("\n3. TODAS AS COLUNAS DISPONÍVEIS:")
        print("=" * 80)

        # Pega o primeiro registro para ver as colunas
        primeiro = result[0]
        colunas = list(primeiro.keys())

        print(f"Total de colunas: {len(colunas)}")
        print("\nLista de colunas:")
        for i, col in enumerate(colunas, 1):
            valor = primeiro.get(col)
            tipo = type(valor).__name__

            # Converte Decimal para ver o valor
            if isinstance(valor, Decimal):
                valor = float(valor)

            # Trunca strings longas
            valor_str = str(valor)[:50] if valor is not None else "NULL"

            print(f"{i:3}. {col:30} | Tipo: {tipo:10} | Exemplo: {valor_str}")

        print("\n4. PRIMEIROS 3 REGISTROS COMPLETOS:")
        print("=" * 80)

        for i, registro in enumerate(result[:3], 1):
            print(f"\n--- Registro {i} ---")
            for col, valor in registro.items():
                if isinstance(valor, Decimal):
                    valor = float(valor)
                valor_str = str(valor)[:80] if valor is not None else "NULL"
                print(f"  {col}: {valor_str}")

        print("\n5. ANÁLISE DE CAMPOS IMPORTANTES:")
        print("=" * 80)

        # Campos únicos
        categorias = set()
        contas = set()
        anos = set()
        meses = set()
        total_orcado = 0
        total_realizado = 0

        for r in result:
            if r.get("categoria"):
                categorias.add(str(r["categoria"]).strip())
            if r.get("conta"):
                contas.add(str(r["conta"]).strip())
            if r.get("ano"):
                anos.add(str(r["ano"]))
            if r.get("mes"):
                meses.add(str(r["mes"]))

            orcado = r.get("orcado", 0)
            if orcado and isinstance(orcado, Decimal):
                orcado = float(orcado)
            total_orcado += orcado or 0

            realizado = r.get("realizado", 0)
            if realizado and isinstance(realizado, Decimal):
                realizado = float(realizado)
            total_realizado += realizado or 0

        print(f"\nCategorias únicas: {len(categorias)}")
        for cat in sorted(categorias):
            print(f"  - {cat}")

        print(f"\nContas únicas: {len(contas)}")
        print(f"Primeiras 20 contas:")
        for conta in sorted(contas)[:20]:
            print(f"  - {conta}")

        print(f"\nAnos: {sorted(anos)}")
        print(f"Meses: {sorted(meses)}")

        print(f"\nTotal orçado: R$ {total_orcado:,.2f}")
        print(f"Total realizado: R$ {total_realizado:,.2f}")
        print(f"Percentual realizado: {(total_realizado/total_orcado*100) if total_orcado > 0 else 0:.2f}%")

        print("\n6. ESTRUTURA DE AGREGAÇÃO ATUAL:")
        print("=" * 80)

        from collections import defaultdict

        por_categoria = defaultdict(lambda: {"contas": set(), "orcado": 0, "realizado": 0, "registros": 0})

        for r in result:
            categoria = str(r.get("categoria", "SEM CATEGORIA")).strip()
            conta = str(r.get("conta", "")).strip()

            orcado = r.get("orcado", 0)
            if orcado and isinstance(orcado, Decimal):
                orcado = float(orcado)

            realizado = r.get("realizado", 0)
            if realizado and isinstance(realizado, Decimal):
                realizado = float(realizado)

            por_categoria[categoria]["contas"].add(conta)
            por_categoria[categoria]["orcado"] += orcado or 0
            por_categoria[categoria]["realizado"] += realizado or 0
            por_categoria[categoria]["registros"] += 1

        print("\nAgregação por categoria:")
        for categoria in sorted(por_categoria.keys()):
            dados = por_categoria[categoria]
            print(f"\n{categoria}:")
            print(f"  Contas: {len(dados['contas'])}")
            print(f"  Registros: {dados['registros']}")
            print(f"  Orçado: R$ {dados['orcado']:,.2f}")
            print(f"  Realizado: R$ {dados['realizado']:,.2f}")
            print(f"  Percentual: {(dados['realizado']/dados['orcado']*100) if dados['orcado'] > 0 else 0:.2f}%")

        print("\n7. VERIFICAÇÃO DE CAMPOS NULL/VAZIOS:")
        print("=" * 80)

        campos_com_null = defaultdict(int)
        for r in result:
            for col, valor in r.items():
                if valor is None or (isinstance(valor, str) and valor.strip() == ""):
                    campos_com_null[col] += 1

        if campos_com_null:
            print("\nCampos com valores NULL ou vazios:")
            for campo, qtd in sorted(campos_com_null.items(), key=lambda x: x[1], reverse=True):
                percentual = (qtd / len(result) * 100)
                print(f"  {campo:30} | {qtd:4} registros ({percentual:.1f}%)")
        else:
            print("\nTodos os campos têm valores preenchidos!")

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
