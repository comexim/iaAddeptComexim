"""
Simula exatamente o que acontece quando usuário pergunta sobre contratos baixados
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.utils.date_parser import DateParser

def test_query_baixados():
    """Testa diferentes formas de consultar contratos baixados"""
    print("=" * 80)
    print("TESTE - SIMULACAO DE QUERY SOBRE CONTRATOS BAIXADOS")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Testa filtro mesEmbarque = janeiro 2026
        print("\nTESTE: Filtro mesEmbarque = '2026/01'")
        print("-" * 80)

        results = sql_client.execute_function("IA_Vendas", {"mesEmbarque": "2026/01"})

        if results:
            baixados = [r for r in results if r.get("baixaReceber") and str(r.get("baixaReceber")).strip()]
            print(f"Total registros: {len(results)}")
            print(f"Contratos baixados: {len(baixados)}")

            if baixados:
                print("\nExemplos:")
                for k, row in enumerate(baixados[:5], 1):
                    print(f"  {k}. {row.get('cliente')} - {row.get('contrato')} (Baixa: {row.get('baixaReceber')})")
        else:
            print("Nenhum registro encontrado")

        # Teste específico: qual é o filtro correto?
        print("\n\n2. ANALISE: QUAL FILTRO USAR PARA 'JANEIRO 2026'?")
        print("=" * 80)

        print("\nCampos disponíveis para filtrar data:")
        print("- mesEmbarque: mês de embarque (YYYY/MM)")
        print("- emissao: data de emissão do contrato (YYYYMMDD)")
        print("- baixaReceber: data de baixa no contas a receber (YYYYMMDD)")

        print("\nPergunta: 'Contratos de janeiro 2026 já baixados'")
        print("Interpretação correta:")
        print("  - 'de janeiro 2026' pode significar:")
        print("    a) Contratos com mesEmbarque = 2026/01 (embarcados em jan/2026)")
        print("    b) Contratos com emissao em jan/2026 (emitidos em jan/2026)")
        print("    c) Contratos com baixaReceber em jan/2026 (baixados em jan/2026)")

        # Testa cada interpretação
        print("\n3. TESTANDO CADA INTERPRETACAO:")
        print("=" * 80)

        # a) Embarque em jan/2026
        print("\na) Contratos EMBARCADOS em jan/2026 que foram BAIXADOS:")
        results_embarque = sql_client.execute_function("IA_Vendas", {"mesEmbarque": "2026/01"})
        baixados_embarque = [r for r in results_embarque if r.get("baixaReceber") and str(r.get("baixaReceber")).strip()]
        print(f"   Total: {len(baixados_embarque)} contratos")

        # b) Emissão em jan/2026
        print("\nb) Contratos EMITIDOS em jan/2026 que foram BAIXADOS:")
        # Precisa consultar todos e filtrar por emissao
        results_all = sql_client.execute_function("IA_Vendas", {})
        if results_all:
            emitidos_jan2026 = [r for r in results_all
                               if r.get("emissao") and str(r.get("emissao")).startswith("202601")]
            baixados_emissao = [r for r in emitidos_jan2026
                               if r.get("baixaReceber") and str(r.get("baixaReceber")).strip()]
            print(f"   Total contratos emitidos jan/2026: {len(emitidos_jan2026)}")
            print(f"   Total baixados: {len(baixados_emissao)}")

        # c) Baixados em jan/2026
        print("\nc) Contratos BAIXADOS em jan/2026:")
        if results_all:
            baixados_jan2026 = [r for r in results_all
                               if r.get("baixaReceber") and str(r.get("baixaReceber")).startswith("202601")]
            print(f"   Total: {len(baixados_jan2026)} contratos")
            if baixados_jan2026:
                print("\n   Exemplos:")
                for k, row in enumerate(baixados_jan2026[:5], 1):
                    print(f"   {k}. {row.get('cliente')} - {row.get('contrato')}")
                    print(f"      Emissão: {row.get('emissao')}, Embarque: {row.get('mesEmbarque')}, Baixa: {row.get('baixaReceber')}")

        # Verificação: qual a IA está usando?
        print("\n\n4. PROVAVEL CAUSA DO PROBLEMA:")
        print("=" * 80)

        print("\nA pergunta 'Contratos de janeiro 2026 já baixados' é AMBIGUA.")
        print("\nSE a IA está usando filtro mesEmbarque='2026/01':")
        print(f"  → Encontra {len(baixados_embarque)} contratos baixados ✓")

        print("\nSE a IA está usando filtro baixaReceber em jan/2026:")
        print(f"  → Encontra {len(baixados_jan2026) if results_all else 0} contratos baixados")

        print("\nSE a IA não está aplicando NENHUM filtro de data e está olhando dados errados:")
        print("  → Pode não encontrar nenhum contrato ✗")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_query_baixados()
