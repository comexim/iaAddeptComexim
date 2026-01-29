"""
Verifica contratos do cliente JDE/IJDE em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_jde_jan2026():
    """Analisa contratos do JDE em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - JDE/IJDE JANEIRO 2026")
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

        # Filtra apenas JDE (pode ser que o banco tenha só "JDE" sem o "I")
        jde_contratos = [r for r in results if "JDE" in r.get("cliente", "").upper()]

        if not jde_contratos:
            print("[AVISO] Nenhum contrato JDE encontrado")
            return

        print(f"[OK] {len(jde_contratos)} contratos JDE\n")

        # Mostra todos os contratos
        print("3. LISTA DE CONTRATOS:")
        print("-" * 80)

        paises = set()
        qualidades = set()
        valores = []

        for i, contrato in enumerate(jde_contratos, 1):
            num_contrato = contrato.get("contrato", "N/A")
            cliente = contrato.get("cliente", "N/A")
            pais = contrato.get("pais", "N/A")
            qualidade = contrato.get("descricaoQualidade", "N/A")
            valor_total = contrato.get("valorTotal", 0) or 0
            sacas = contrato.get("sacas", 0) or 0
            diferencial = contrato.get("diferencial")

            print(f"\nContrato {i}: {num_contrato}")
            print(f"  Cliente: {cliente}")
            print(f"  Pais: {pais}")
            print(f"  Qualidade: {qualidade}")
            print(f"  Sacas: {sacas:,.2f}")
            print(f"  Valor Total: R$ {valor_total:,.2f}")
            print(f"  Diferencial: {diferencial}")

            paises.add(pais)
            qualidades.add(qualidade)
            valores.append(valor_total)

        # Resumo
        print("\n" + "-" * 80)
        print("4. RESUMO:")
        print("-" * 80)
        print(f"Cliente encontrado no banco: {jde_contratos[0].get('cliente', 'N/A')}")
        print(f"Total de contratos: {len(jde_contratos)}")
        print(f"Total de sacas: {sum(c.get('sacas', 0) or 0 for c in jde_contratos):,.2f}")
        print(f"Valor total: R$ {sum(valores):,.2f}")
        print(f"Maior contrato: R$ {max(valores):,.2f}")
        print(f"Menor contrato: R$ {min(valores):,.2f}")

        print(f"\nPaises de destino:")
        for pais in sorted(paises):
            print(f"  - {pais}")

        print(f"\nQualidades de cafe:")
        for i, qual in enumerate(sorted(qualidades), 1):
            print(f"  {i}. {qual}")

        # Comparação com resposta da IA
        print("\n5. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        print("IA disse:")
        print("  - Cliente: IJDE")
        print("  - 4 contratos")
        print("  - Destino: Paises Baixos (Holanda)")
        print("  - Qualidades mencionadas: 'TOP GERMAN MIXED CROP', 'PRIMEIRO MTGB'")
        print("  - Maior valor: ate R$ 1.179.853,18")

        print("\nBanco tem:")
        print(f"  - Cliente: {jde_contratos[0].get('cliente', 'N/A').strip()}")
        print(f"  - {len(jde_contratos)} contratos")
        print(f"  - Paises: {', '.join(sorted(paises))}")

        # Verifica se as qualidades mencionadas existem
        qualidades_ia = ["TOP GERMAN MIXED CROP", "PRIMEIRO MTGB"]
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

        # Nome do cliente
        cliente_banco = jde_contratos[0].get('cliente', '').strip().upper()
        if "JDE" in cliente_banco:
            print(f"[OK] Cliente: Banco tem '{cliente_banco}' (usuario perguntou sobre 'IJDE')")
            print("     Nota: Usuario pode ter escrito 'IJDE' mas o correto e 'JDE'")
            validacoes.append(True)
        else:
            print(f"[ERRO] Cliente esperado: JDE/IJDE, encontrado: {cliente_banco}")
            validacoes.append(False)

        # Quantidade de contratos
        if len(jde_contratos) == 4:
            print("[OK] Quantidade de contratos: 4 (correto)")
            validacoes.append(True)
        else:
            print(f"[ERRO] Quantidade: IA disse 4, banco tem {len(jde_contratos)}")
            validacoes.append(False)

        # Destino
        # Normaliza paises
        paises_normalizados = {p.strip().upper() for p in paises}
        if any("HOLANDA" in p or "PAISES BAIXOS" in p for p in paises_normalizados):
            print("[OK] Destino: Paises Baixos/Holanda (correto)")
            validacoes.append(True)
        else:
            print(f"[ERRO] Destino: IA disse Holanda, banco tem {paises}")
            validacoes.append(False)

        # Maior valor
        maior_valor_banco = max(valores)
        if abs(maior_valor_banco - 1179853.18) < 1:
            print(f"[OK] Maior valor: R$ {maior_valor_banco:,.2f} (correto)")
            validacoes.append(True)
        else:
            print(f"[AVISO] Maior valor: IA disse R$ 1.179.853,18, banco tem R$ {maior_valor_banco:,.2f}")
            print(f"        Diferenca: R$ {abs(maior_valor_banco - 1179853.18):,.2f}")
            validacoes.append(abs(maior_valor_banco - 1179853.18) < 100)  # Tolerância de R$ 100

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
    test_jde_jan2026()
