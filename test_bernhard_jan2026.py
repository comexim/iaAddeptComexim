"""
Verifica contratos do cliente Bernhard Rothfos em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_bernhard_jan2026():
    """Analisa contratos do Bernhard Rothfos em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - BERNHARD ROTHFOS JANEIRO 2026")
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

        # Filtra apenas BERNHARD ROTHFOS
        bernhard_contratos = [r for r in results if "BERNHARD ROTHFOS" in r.get("cliente", "").upper()]

        if not bernhard_contratos:
            print("[AVISO] Nenhum contrato BERNHARD ROTHFOS encontrado")
            return

        print(f"[OK] {len(bernhard_contratos)} contratos BERNHARD ROTHFOS\n")

        # Mostra todos os contratos
        print("3. LISTA DE CONTRATOS:")
        print("-" * 80)

        paises = set()
        qualidades = set()
        valores = []

        for i, contrato in enumerate(bernhard_contratos, 1):
            num_contrato = contrato.get("contrato", "N/A")
            pais = contrato.get("pais", "N/A")
            qualidade = contrato.get("descricaoQualidade", "N/A")
            valor_total = contrato.get("valorTotal", 0) or 0
            sacas = contrato.get("sacas", 0) or 0

            print(f"\nContrato {i}: {num_contrato}")
            print(f"  Pais: {pais}")
            print(f"  Qualidade: {qualidade[:60]}...")
            print(f"  Sacas: {sacas:,.2f}")
            print(f"  Valor Total: R$ {valor_total:,.2f}")

            paises.add(pais)
            qualidades.add(qualidade)
            valores.append(valor_total)

        # Resumo
        print("\n" + "-" * 80)
        print("4. RESUMO:")
        print("-" * 80)
        print(f"Total de contratos: {len(bernhard_contratos)}")
        print(f"Total de sacas: {sum(c.get('sacas', 0) or 0 for c in bernhard_contratos):,.2f}")
        print(f"Valor total: R$ {sum(valores):,.2f}")
        print(f"Maior contrato: R$ {max(valores):,.2f}")
        print(f"Menor contrato: R$ {min(valores):,.2f}")

        print(f"\nPaises de destino:")
        for pais in sorted(paises):
            print(f"  - {pais}")

        print(f"\nQualidades de cafe (amostra):")
        for i, qual in enumerate(sorted(qualidades)[:5], 1):
            print(f"  {i}. {qual[:70]}")
        if len(qualidades) > 5:
            print(f"  ... e mais {len(qualidades) - 5} qualidades")

        # Comparação com resposta da IA
        print("\n5. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        print("IA disse:")
        print("  - 11 contratos")
        print("  - Destino: Alemanha")
        print("  - Qualidades mencionadas: 'TOP GERMAN MTGB EUDR', 'GRINDERS GOOD CUP 13 UP RFA EUDR'")
        print("  - Maior valor: ate R$ 1.506.025,32")

        print("\nBanco tem:")
        print(f"  - {len(bernhard_contratos)} contratos")
        print(f"  - Paises: {', '.join(sorted(paises))}")

        # Verifica se as qualidades mencionadas existem
        qualidades_ia = ["TOP GERMAN MTGB EUDR", "GRINDERS GOOD CUP 13 UP RFA EUDR"]
        print(f"  - Qualidades verificadas:")
        for qual_ia in qualidades_ia:
            encontrada = any(qual_ia.upper() in q.upper() for q in qualidades)
            status = "[OK]" if encontrada else "[NAO ENCONTRADA]"
            print(f"    {status} '{qual_ia}'")

        print(f"  - Maior valor: R$ {max(valores):,.2f}")

        # Validação
        print("\n6. VALIDACAO:")
        print("-" * 80)

        validacoes = []

        # Quantidade de contratos
        if len(bernhard_contratos) == 11:
            print("[OK] Quantidade de contratos: 11 (correto)")
            validacoes.append(True)
        else:
            print(f"[ERRO] Quantidade: IA disse 11, banco tem {len(bernhard_contratos)}")
            validacoes.append(False)

        # Destino
        if paises == {"ALEMANHA"}:
            print("[OK] Destino: Alemanha (correto)")
            validacoes.append(True)
        else:
            print(f"[ERRO] Destino: IA disse Alemanha, banco tem {paises}")
            validacoes.append(False)

        # Maior valor
        maior_valor_banco = max(valores)
        if abs(maior_valor_banco - 1506025.32) < 1:
            print(f"[OK] Maior valor: R$ {maior_valor_banco:,.2f} (correto)")
            validacoes.append(True)
        else:
            print(f"[AVISO] Maior valor: IA disse R$ 1.506.025,32, banco tem R$ {maior_valor_banco:,.2f}")
            validacoes.append(abs(maior_valor_banco - 1506025.32) < 100)  # Tolerância de R$ 100

        # Qualidades
        qualidades_corretas = sum(
            any(qual_ia.upper() in q.upper() for q in qualidades)
            for qual_ia in qualidades_ia
        )
        if qualidades_corretas == len(qualidades_ia):
            print(f"[OK] Qualidades mencionadas: {qualidades_corretas}/{len(qualidades_ia)} encontradas")
            validacoes.append(True)
        else:
            print(f"[AVISO] Qualidades: {qualidades_corretas}/{len(qualidades_ia)} encontradas")
            validacoes.append(qualidades_corretas > 0)

        # Resultado final
        print("\n7. RESULTADO FINAL:")
        print("-" * 80)

        if all(validacoes):
            print("[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif sum(validacoes) / len(validacoes) >= 0.75:
            print(f"[PARCIAL] Resposta da IA esta {sum(validacoes)}/{len(validacoes)} correta")
        else:
            print(f"[ERRO] Resposta da IA tem problemas: {sum(validacoes)}/{len(validacoes)} correto")

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
    test_bernhard_jan2026()
