"""
Valida: Resposta da IA sobre contrato 488/25
Pergunta: Qual o diferencial e o preço fixado do contrato 488/25? E para qual país foi exportado?
Resposta IA: O contrato 488/25, exportado para a Alemanha, possui um diferencial de -53,75 e não tem preço fixado (valor fixado é 0,00).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_488_25():
    """Valida contrato 488/25"""
    print("=" * 80)
    print("VALIDACAO - Contrato 488/25")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Pergunta: Qual o diferencial e o preço fixado do contrato 488/25?")
        print("          E para qual país foi exportado?")
        print("")
        print("Resposta IA:")
        print("  - País: ALEMANHA")
        print("  - Diferencial: -53,75")
        print("  - Preço fixado: 0,00 (não tem preço fixado)")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Buscando contrato 488/25 no banco de dados")
        print("-" * 80)

        # Busca o contrato específico
        result = sql_client.execute_function("dbo.IA_Vendas")

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        # Filtra o contrato 488/25
        contrato_488 = None
        for r in result:
            contrato = r.get("contrato", "").strip()
            if contrato == "488/25":
                contrato_488 = r
                break

        if not contrato_488:
            print("[X] ERRO: Contrato 488/25 NÃO encontrado no banco!")
            return

        print("[OK] Contrato 488/25 encontrado")

        print("\n4. DADOS DO BANCO:")
        print("=" * 80)

        pais = contrato_488.get("pais", "").strip()
        diferencial = contrato_488.get("diferencial", None)
        valor_fixado = contrato_488.get("valorFixado", None)
        cliente = contrato_488.get("cliente", "").strip()
        sacas = contrato_488.get("sacas", 0)
        numero_bl = contrato_488.get("numeroBL", "").strip()
        saida_navio = contrato_488.get("saidaNavio", "")

        print(f"Contrato: 488/25")
        print(f"Cliente: {cliente}")
        print(f"País: {pais}")
        print(f"Diferencial: {diferencial}")
        print(f"Valor Fixado: {valor_fixado}")
        print(f"Sacas: {sacas}")
        print(f"BL: {numero_bl if numero_bl else 'SEM BL'}")
        print(f"Saída Navio: {saida_navio if saida_navio else 'SEM SAIDA'}")

        print("\n5. COMPARAÇÃO:")
        print("=" * 80)

        # Validação 1: País
        print("\n5.1. PAÍS:")
        print(f"  IA disse: ALEMANHA")
        print(f"  Banco tem: {pais}")
        if "ALEMAN" in pais.upper():
            print("  [OK] CORRETO")
            pais_correto = True
        else:
            print("  [X] INCORRETO")
            pais_correto = False

        # Validação 2: Diferencial
        print("\n5.2. DIFERENCIAL:")
        print(f"  IA disse: -53,75")
        print(f"  Banco tem: {diferencial}")

        # Converte para float para comparação
        diferencial_float = None
        if diferencial is not None:
            if isinstance(diferencial, (int, float, Decimal)):
                diferencial_float = float(diferencial)

        if diferencial_float is not None and abs(diferencial_float - (-53.75)) < 0.01:
            print("  [OK] CORRETO")
            diferencial_correto = True
        else:
            print("  [X] INCORRETO")
            diferencial_correto = False

        # Validação 3: Preço Fixado
        print("\n5.3. PREÇO FIXADO:")
        print(f"  IA disse: 0,00 (não tem preço fixado)")
        print(f"  Banco tem: {valor_fixado}")

        # Converte para float para comparação
        valor_fixado_float = None
        if valor_fixado is not None:
            if isinstance(valor_fixado, (int, float, Decimal)):
                valor_fixado_float = float(valor_fixado)

        # Considera correto se for None, 0, ou 0.0
        if valor_fixado_float is None or abs(valor_fixado_float) < 0.01:
            print("  [OK] CORRETO (valor e zero ou nulo)")
            valor_fixado_correto = True
        else:
            print("  [X] INCORRETO (valor nao e zero)")
            valor_fixado_correto = False

        print("\n6. RESULTADO FINAL:")
        print("=" * 80)

        if pais_correto and diferencial_correto and valor_fixado_correto:
            print("\n" + "=" * 80)
            print("[OK][OK][OK] RESPOSTA DA IA ESTA 100% CORRETA! [OK][OK][OK]")
            print("=" * 80)
            print("\nTodos os campos conferem:")
            print(f"  [OK] Pais: ALEMANHA")
            print(f"  [OK] Diferencial: -53,75")
            print(f"  [OK] Preco fixado: 0,00")
        else:
            print("\n" + "=" * 80)
            print("[X][X][X] RESPOSTA DA IA ESTA INCORRETA! [X][X][X]")
            print("=" * 80)
            print("\nErros encontrados:")
            if not pais_correto:
                print(f"  [X] Pais: IA disse ALEMANHA, banco tem {pais}")
            if not diferencial_correto:
                print(f"  [X] Diferencial: IA disse -53,75, banco tem {diferencial}")
            if not valor_fixado_correto:
                print(f"  [X] Valor fixado: IA disse 0,00, banco tem {valor_fixado}")

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
    test_488_25()
