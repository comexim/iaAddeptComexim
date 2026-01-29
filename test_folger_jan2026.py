"""
Verifica diferencial médio do cliente The Folger Coffee em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_folger_jan2026():
    """Analisa diferencial do The Folger Coffee em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - THE FOLGER COFFEE JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026
        print("2. Consultando vendas de janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        # Filtra apenas THE FOLGER COFFEE
        folger_contratos = [r for r in results if "FOLGER" in r.get("cliente", "").upper()]

        if not folger_contratos:
            print("[AVISO] Nenhum contrato THE FOLGER COFFEE encontrado")
            return

        print(f"[OK] {len(folger_contratos)} contratos THE FOLGER COFFEE\n")

        # Mostra todos os contratos
        print("3. LISTA DE CONTRATOS:")
        print("-" * 80)

        diferenciais = []
        total_sacas = 0
        total_valor = 0

        for i, contrato in enumerate(folger_contratos, 1):
            num_contrato = contrato.get("contrato", "N/A")
            cliente = contrato.get("cliente", "N/A")
            diferencial = contrato.get("diferencial")
            sacas = contrato.get("sacas", 0) or 0
            valor_total = contrato.get("valorTotal", 0) or 0
            pais = contrato.get("pais", "N/A")
            qualidade = contrato.get("descricaoQualidade", "N/A")

            print(f"\nContrato {i}: {num_contrato}")
            print(f"  Cliente: {cliente}")
            print(f"  Diferencial: {diferencial}")
            print(f"  Sacas: {sacas:,.2f}")
            print(f"  Valor Total: R$ {valor_total:,.2f}")
            print(f"  Pais: {pais}")
            print(f"  Qualidade: {qualidade[:50]}")

            if diferencial is not None:
                diferenciais.append(float(diferencial))

            total_sacas += sacas
            total_valor += valor_total

        # Calcula diferencial médio
        print("\n" + "-" * 80)
        print("4. CALCULO DO DIFERENCIAL MEDIO:")
        print("-" * 80)

        if diferenciais:
            print(f"Diferenciais encontrados: {diferenciais}")
            print(f"Soma dos diferenciais: {sum(diferenciais):.2f}")
            print(f"Quantidade de contratos: {len(diferenciais)}")
            diferencial_medio = sum(diferenciais) / len(diferenciais)
            print(f"DIFERENCIAL MEDIO CALCULADO: {diferencial_medio:.2f}")
        else:
            print("Nenhum diferencial encontrado!")
            diferencial_medio = None

        # Resumo geral
        print("\n5. RESUMO:")
        print("-" * 80)
        print(f"Cliente: THE FOLGER COFFEE")
        print(f"Total de contratos: {len(folger_contratos)}")
        print(f"Total de sacas: {total_sacas:,.2f}")
        print(f"Valor total: R$ {total_valor:,.2f}")
        print(f"Diferencial medio: {diferencial_medio:.2f}" if diferencial_medio is not None else "Diferencial medio: N/A")

        # Comparação com resposta da IA
        print("\n6. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = -25.0

        print(f"IA disse: {ia_disse:.2f}")
        print(f"Banco tem: {diferencial_medio:.2f}" if diferencial_medio is not None else "Banco tem: N/A")

        if diferencial_medio is not None:
            diferenca = abs(diferencial_medio - ia_disse)
            print(f"Diferenca: {diferenca:.2f}")

            if diferenca < 0.01:
                print("\n[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
            else:
                print(f"\n[ERRO] Diferenca de {diferenca:.2f} encontrada")
        else:
            print("\n[ERRO] Nao foi possivel calcular diferencial medio")

        print("\n" + "=" * 80)
        print("[OK] VERIFICACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_folger_jan2026()
