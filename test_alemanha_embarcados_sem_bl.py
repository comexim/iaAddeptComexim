"""
Valida: Contratos Alemanha embarcados sem BL em dezembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_alemanha():
    """Valida contratos Alemanha embarcados sem BL"""
    print("=" * 80)
    print("VALIDACAO - Alemanha: embarcados sem BL em dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("IA disse: 3 contratos embarcados mas ainda não têm BL")

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

        print("\n4. Filtrando por país = ALEMANHA")
        print("-" * 80)

        alemanha = []
        for r in result:
            pais = r.get("pais", "").strip().upper()
            if "ALEMAN" in pais:
                alemanha.append(r)

        print(f"Contratos para Alemanha: {len(alemanha)}")

        if not alemanha:
            print("\n[X] NENHUM contrato para Alemanha encontrado!")
            return

        print("\n5. Todos os contratos da Alemanha:")
        print("=" * 80)

        for i, r in enumerate(alemanha, 1):
            contrato = r.get("contrato", "").strip()
            cliente = r.get("cliente", "").strip()
            saida_navio = r.get("saidaNavio", "")
            numero_bl = r.get("numeroBL", "")

            # Verifica se tem saída de navio
            tem_saida = bool(saida_navio and str(saida_navio).strip())

            # Verifica se tem BL
            tem_bl = bool(numero_bl and str(numero_bl).strip())

            saida_str = str(saida_navio).strip() if tem_saida else "SEM SAIDA"
            bl_str = str(numero_bl).strip() if tem_bl else "SEM BL"

            print(f"{i}. Contrato: {contrato:10} Cliente: {cliente:30}")
            print(f"   Saida Navio: {saida_str:15} BL: {bl_str:20}")

        print("\n6. Filtrando: EMBARCADOS (com saidaNavio) mas SEM BL")
        print("=" * 80)

        embarcados_sem_bl = []
        for r in alemanha:
            saida_navio = r.get("saidaNavio", "")
            numero_bl = r.get("numeroBL", "")

            # Tem saída de navio
            tem_saida = bool(saida_navio and str(saida_navio).strip())

            # NÃO tem BL
            tem_bl = bool(numero_bl and str(numero_bl).strip())

            if tem_saida and not tem_bl:
                embarcados_sem_bl.append(r)

        print(f"Contratos embarcados SEM BL: {len(embarcados_sem_bl)}")

        if embarcados_sem_bl:
            print("\nLista de contratos:")
            for i, r in enumerate(embarcados_sem_bl, 1):
                contrato = r.get("contrato", "").strip()
                cliente = r.get("cliente", "").strip()
                saida_navio = r.get("saidaNavio", "").strip()

                print(f"{i}. Contrato: {contrato:10} Cliente: {cliente:30} Saida: {saida_navio}")
        else:
            print("\n[!] Nenhum contrato embarcado sem BL encontrado")

        print("\n7. COMPARAÇÃO:")
        print("=" * 80)
        print(f"IA disse:     3 contratos")
        print(f"Banco tem:    {len(embarcados_sem_bl)} contratos")

        if len(embarcados_sem_bl) == 3:
            print("\n[OK] IA está CORRETA! ✓")
        else:
            print(f"\n[X] IA está INCORRETA!")
            print(f"    Diferença: {abs(len(embarcados_sem_bl) - 3)} contratos")

        print("\n8. Estatísticas gerais da Alemanha:")
        print("-" * 80)

        total_alemanha = len(alemanha)
        com_bl = sum(1 for r in alemanha if r.get("numeroBL") and str(r.get("numeroBL")).strip())
        sem_bl = total_alemanha - com_bl
        embarcados = sum(1 for r in alemanha if r.get("saidaNavio") and str(r.get("saidaNavio")).strip())
        nao_embarcados = total_alemanha - embarcados

        print(f"Total de contratos Alemanha: {total_alemanha}")
        print(f"  Com BL: {com_bl}")
        print(f"  Sem BL: {sem_bl}")
        print(f"  Embarcados: {embarcados}")
        print(f"  Não embarcados: {nao_embarcados}")
        print(f"  Embarcados SEM BL: {len(embarcados_sem_bl)}")

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
    test_alemanha()
