"""
Verifica todos os certificados únicos em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_certificados_jan2026():
    """Lista todos os certificados únicos de janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - CERTIFICADOS JANEIRO 2026")
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

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Coleta todos os certificados únicos
        certificados_set = set()
        contratos_por_certificado = {}

        for row in results:
            cert = row.get("certificado")
            contrato = row.get("contrato", "N/A")

            if cert:
                cert_str = str(cert).strip()
                if cert_str:  # Se não for vazio
                    certificados_set.add(cert_str)

                    # Registra contratos por certificado
                    if cert_str not in contratos_por_certificado:
                        contratos_por_certificado[cert_str] = []
                    contratos_por_certificado[cert_str].append(contrato)

        # Ordena certificados
        certificados_list = sorted(list(certificados_set))

        print("3. CERTIFICADOS UNICOS ENCONTRADOS:")
        print("-" * 80)

        if certificados_list:
            for i, cert in enumerate(certificados_list, 1):
                num_contratos = len(contratos_por_certificado[cert])
                print(f"{i}. {cert} ({num_contratos} contratos)")
        else:
            print("  Nenhum certificado encontrado")

        print(f"\nTotal de certificados únicos: {len(certificados_list)}")

        # Mostra detalhes de cada certificado
        print("\n4. DETALHES POR CERTIFICADO:")
        print("-" * 80)
        for cert in certificados_list:
            contratos = contratos_por_certificado[cert]
            print(f"\n{cert}:")
            print(f"  Contratos: {', '.join(contratos[:10])}")
            if len(contratos) > 10:
                print(f"  ... e mais {len(contratos) - 10} contratos")

        # Comparação com resposta da IA
        print("\n5. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = ["4C", "RF", "FT", "GCP"]

        print("IA disse:")
        for cert in ia_disse:
            print(f"  - {cert}")

        print("\nBanco tem:")
        for cert in certificados_list:
            print(f"  - {cert}")

        # Verifica se estão corretos
        print("\n6. VALIDACAO:")
        print("-" * 80)

        ia_set = set(ia_disse)
        banco_set = set(certificados_list)

        corretos = ia_set & banco_set
        faltando = banco_set - ia_set
        extras = ia_set - banco_set

        print(f"Certificados corretos: {len(corretos)}/{len(ia_set)}")
        if corretos:
            print("  Corretos:", ", ".join(sorted(corretos)))

        if faltando:
            print(f"\nCertificados que a IA NAO mencionou: {len(faltando)}")
            print("  Faltando:", ", ".join(sorted(faltando)))

        if extras:
            print(f"\nCertificados que a IA mencionou mas NAO existem: {len(extras)}")
            print("  Extras:", ", ".join(sorted(extras)))

        if not faltando and not extras:
            print("\n✓ RESPOSTA DA IA ESTA 100% CORRETA!")
        elif not extras:
            print(f"\n⚠ RESPOSTA DA IA ESTA PARCIAL (faltou mencionar {len(faltando)} certificados)")
        else:
            print("\n✗ RESPOSTA DA IA TEM ERROS")

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
    test_certificados_jan2026()
