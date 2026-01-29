"""
Valida: Comparacao Argentina vs Alemanha em dezembro 2025
Pergunta: Comparando dezembro de 2025, exportamos mais sacas para Argentina ou para Alemanha?
          Quantas sacas foram para cada um e quais os numeros dos contratos?
Resposta IA:
  - Alemanha: 1.377,96 sacas, contratos 488/25, 453/25A, 453/25B
  - Argentina: 1.320,00 sacas, contratos 513/25, 558/25, 559/25
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_argentina_alemanha():
    """Valida comparacao Argentina vs Alemanha"""
    print("=" * 80)
    print("VALIDACAO - Argentina vs Alemanha - Dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Pergunta: Comparando dezembro de 2025, exportamos mais sacas para")
        print("          Argentina ou para Alemanha? Quantas sacas e quais contratos?")
        print("")
        print("Resposta IA:")
        print("  Alemanha: 1.377,96 sacas")
        print("  Contratos Alemanha: 488/25, 453/25A, 453/25B")
        print("")
        print("  Argentina: 1.320,00 sacas")
        print("  Contratos Argentina: 513/25, 558/25, 559/25")
        print("")
        print("  Conclusao IA: Alemanha exportou MAIS sacas (1.377,96 > 1.320,00)")

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

        print(f"Total de registros em dezembro: {len(result)}")

        print("\n4. Filtrando por ALEMANHA")
        print("-" * 80)

        alemanha_contratos = []
        alemanha_total_sacas = 0

        for r in result:
            pais = r.get("pais", "").strip().upper()
            if "ALEMAN" in pais:
                contrato = r.get("contrato", "").strip()
                sacas = r.get("sacas", 0) or 0

                if isinstance(sacas, (int, float, Decimal)):
                    sacas_float = float(sacas)
                else:
                    sacas_float = 0

                alemanha_contratos.append({
                    "contrato": contrato,
                    "sacas": sacas_float,
                    "cliente": r.get("cliente", "").strip()
                })
                alemanha_total_sacas += sacas_float

        print(f"Contratos para Alemanha: {len(alemanha_contratos)}")
        print(f"Total de sacas Alemanha: {alemanha_total_sacas:.2f}")

        if alemanha_contratos:
            print("\nDetalhes dos contratos:")
            for c in alemanha_contratos:
                print(f"  - {c['contrato']:10} | {c['sacas']:10.2f} sacas | {c['cliente'][:30]}")

        print("\n5. Filtrando por ARGENTINA")
        print("-" * 80)

        argentina_contratos = []
        argentina_total_sacas = 0

        for r in result:
            pais = r.get("pais", "").strip().upper()
            if "ARGENTIN" in pais:
                contrato = r.get("contrato", "").strip()
                sacas = r.get("sacas", 0) or 0

                if isinstance(sacas, (int, float, Decimal)):
                    sacas_float = float(sacas)
                else:
                    sacas_float = 0

                argentina_contratos.append({
                    "contrato": contrato,
                    "sacas": sacas_float,
                    "cliente": r.get("cliente", "").strip()
                })
                argentina_total_sacas += sacas_float

        print(f"Contratos para Argentina: {len(argentina_contratos)}")
        print(f"Total de sacas Argentina: {argentina_total_sacas:.2f}")

        if argentina_contratos:
            print("\nDetalhes dos contratos:")
            for c in argentina_contratos:
                print(f"  - {c['contrato']:10} | {c['sacas']:10.2f} sacas | {c['cliente'][:30]}")

        print("\n6. COMPARACAO:")
        print("=" * 80)

        # Validacao 1: Total de sacas Alemanha
        print("\n6.1. TOTAL DE SACAS ALEMANHA:")
        print(f"  IA disse: 1.377,96 sacas")
        print(f"  Banco tem: {alemanha_total_sacas:.2f} sacas")

        if abs(alemanha_total_sacas - 1377.96) < 0.1:
            print("  [OK] CORRETO")
            alemanha_sacas_correto = True
        else:
            print("  [X] INCORRETO")
            alemanha_sacas_correto = False

        # Validacao 2: Contratos Alemanha
        print("\n6.2. CONTRATOS ALEMANHA:")
        print(f"  IA disse: 488/25, 453/25A, 453/25B")
        contratos_alemanha_banco = sorted([c['contrato'] for c in alemanha_contratos])
        print(f"  Banco tem: {', '.join(contratos_alemanha_banco)}")

        contratos_ia_alemanha = sorted(['488/25', '453/25A', '453/25B'])
        if contratos_alemanha_banco == contratos_ia_alemanha:
            print("  [OK] CORRETO")
            alemanha_contratos_correto = True
        else:
            print("  [X] INCORRETO")
            alemanha_contratos_correto = False

        # Validacao 3: Total de sacas Argentina
        print("\n6.3. TOTAL DE SACAS ARGENTINA:")
        print(f"  IA disse: 1.320,00 sacas")
        print(f"  Banco tem: {argentina_total_sacas:.2f} sacas")

        if abs(argentina_total_sacas - 1320.00) < 0.1:
            print("  [OK] CORRETO")
            argentina_sacas_correto = True
        else:
            print("  [X] INCORRETO")
            argentina_sacas_correto = False

        # Validacao 4: Contratos Argentina
        print("\n6.4. CONTRATOS ARGENTINA:")
        print(f"  IA disse: 513/25, 558/25, 559/25")
        contratos_argentina_banco = sorted([c['contrato'] for c in argentina_contratos])
        print(f"  Banco tem: {', '.join(contratos_argentina_banco)}")

        contratos_ia_argentina = sorted(['513/25', '558/25', '559/25'])
        if contratos_argentina_banco == contratos_ia_argentina:
            print("  [OK] CORRETO")
            argentina_contratos_correto = True
        else:
            print("  [X] INCORRETO")
            argentina_contratos_correto = False

        # Validacao 5: Qual exportou mais?
        print("\n6.5. QUAL PAIS EXPORTOU MAIS?")
        print(f"  IA disse: Alemanha exportou mais (1.377,96 > 1.320,00)")
        print(f"  Banco tem: Alemanha {alemanha_total_sacas:.2f} | Argentina {argentina_total_sacas:.2f}")

        if alemanha_total_sacas > argentina_total_sacas:
            print("  [OK] CORRETO - Alemanha exportou mais")
            comparacao_correta = True
        else:
            print("  [X] INCORRETO")
            comparacao_correta = False

        print("\n7. RESULTADO FINAL:")
        print("=" * 80)

        tudo_correto = (alemanha_sacas_correto and alemanha_contratos_correto and
                       argentina_sacas_correto and argentina_contratos_correto and
                       comparacao_correta)

        if tudo_correto:
            print("\n" + "=" * 80)
            print("[OK][OK][OK] RESPOSTA DA IA ESTA 100% CORRETA! [OK][OK][OK]")
            print("=" * 80)
            print("\nTodos os campos conferem:")
            print(f"  [OK] Alemanha: {alemanha_total_sacas:.2f} sacas")
            print(f"  [OK] Contratos Alemanha: {', '.join(contratos_alemanha_banco)}")
            print(f"  [OK] Argentina: {argentina_total_sacas:.2f} sacas")
            print(f"  [OK] Contratos Argentina: {', '.join(contratos_argentina_banco)}")
            print(f"  [OK] Alemanha exportou mais sacas")
        else:
            print("\n" + "=" * 80)
            print("[X][X][X] RESPOSTA DA IA ESTA INCORRETA! [X][X][X]")
            print("=" * 80)
            print("\nErros encontrados:")
            if not alemanha_sacas_correto:
                print(f"  [X] Sacas Alemanha: IA disse 1.377,96, banco tem {alemanha_total_sacas:.2f}")
            if not alemanha_contratos_correto:
                print(f"  [X] Contratos Alemanha: IA disse 488/25, 453/25A, 453/25B, banco tem {', '.join(contratos_alemanha_banco)}")
            if not argentina_sacas_correto:
                print(f"  [X] Sacas Argentina: IA disse 1.320,00, banco tem {argentina_total_sacas:.2f}")
            if not argentina_contratos_correto:
                print(f"  [X] Contratos Argentina: IA disse 513/25, 558/25, 559/25, banco tem {', '.join(contratos_argentina_banco)}")
            if not comparacao_correta:
                print(f"  [X] Comparacao errada")

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
    test_argentina_alemanha()
