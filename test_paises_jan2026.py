"""
Verifica todos os países únicos em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_paises_jan2026():
    """Lista todos os países únicos de janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - PAISES JANEIRO 2026")
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

        # Coleta todos os países únicos
        paises_set = set()
        contratos_por_pais = {}
        sacas_por_pais = {}

        for row in results:
            pais = row.get("pais")
            contrato = row.get("contrato", "N/A")
            sacas = row.get("sacas", 0) or 0

            if pais:
                pais_str = str(pais).strip()
                if pais_str:  # Se não for vazio
                    paises_set.add(pais_str)

                    # Registra contratos por país
                    if pais_str not in contratos_por_pais:
                        contratos_por_pais[pais_str] = []
                        sacas_por_pais[pais_str] = 0

                    contratos_por_pais[pais_str].append(contrato)
                    sacas_por_pais[pais_str] += sacas

        # Ordena países alfabeticamente
        paises_list = sorted(list(paises_set))

        print("3. PAISES UNICOS ENCONTRADOS NO BANCO:")
        print("-" * 80)

        if paises_list:
            for i, pais in enumerate(paises_list, 1):
                num_contratos = len(contratos_por_pais[pais])
                total_sacas = sacas_por_pais[pais]
                print(f"{i:2d}. {pais:40s} ({num_contratos} contratos, {total_sacas:,.0f} sacas)")
        else:
            print("  Nenhum país encontrado")

        print(f"\nTotal de países únicos: {len(paises_list)}")

        # Comparação com resposta da IA
        print("\n4. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = [
            "Alemanha",
            "Estados Unidos",
            "Países Baixos (Holanda)",
            "Suíça",
            "Brasil",
            "Reino Unido",
            "Finlândia",
            "Argentina",
            "Bélgica",
            "Coreia, República da",
            "Grécia",
            "Polônia, República da",
            "Rússia, Federação da",
            "Japão",
            "Singapura",
            "Austrália"
        ]

        print("IA disse:")
        for i, pais in enumerate(ia_disse, 1):
            print(f"  {i:2d}. {pais}")

        print(f"\nTotal mencionado pela IA: {len(ia_disse)}")

        print("\n5. VALIDACAO (NORMALIZADA):")
        print("-" * 80)

        # Normaliza nomes para comparação
        def normalizar(texto):
            """Normaliza nome do país para comparação"""
            texto = texto.upper().strip()
            # Remove acentos e caracteres especiais
            import unicodedata
            texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                          if unicodedata.category(c) != 'Mn')
            # Substitui variações comuns
            texto = texto.replace("PAISES BAIXOS", "HOLANDA")
            texto = texto.replace("(HOLANDA)", "")
            texto = texto.replace("COREIA, REPUBLICA DA", "COREIA DO SUL")
            texto = texto.replace("POLONIA, REPUBLICA DA", "POLONIA")
            texto = texto.replace("RUSSIA, FEDERACAO DA", "RUSSIA")
            texto = texto.replace(",", "")
            texto = texto.strip()
            return texto

        # Cria sets normalizados
        banco_normalizado = {normalizar(p): p for p in paises_list}
        ia_normalizado = {normalizar(p): p for p in ia_disse}

        # Encontra correspondências
        corretos = []
        for norm_ia, original_ia in ia_normalizado.items():
            if norm_ia in banco_normalizado:
                corretos.append({
                    "ia": original_ia,
                    "banco": banco_normalizado[norm_ia]
                })

        faltando_banco = set(banco_normalizado.keys()) - set(ia_normalizado.keys())
        extras_ia = set(ia_normalizado.keys()) - set(banco_normalizado.keys())

        print(f"Países corretos: {len(corretos)}/{len(ia_disse)}")

        if corretos:
            print("\nCorretos (IA → Banco):")
            for match in corretos:
                print(f"  ✓ '{match['ia']}' → '{match['banco']}'")

        if faltando_banco:
            print(f"\nPaíses que a IA NAO mencionou: {len(faltando_banco)}")
            for norm in sorted(faltando_banco):
                original = banco_normalizado[norm]
                num_contratos = len(contratos_por_pais[original])
                total_sacas = sacas_por_pais[original]
                print(f"  - {original} ({num_contratos} contratos, {total_sacas:,.0f} sacas)")

        if extras_ia:
            print(f"\nPaíses que a IA mencionou mas NAO existem: {len(extras_ia)}")
            for norm in sorted(extras_ia):
                original = ia_normalizado[norm]
                print(f"  - {original}")

        # Resultado final
        print("\n6. RESULTADO FINAL:")
        print("-" * 80)

        if not faltando_banco and not extras_ia:
            print("[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif not extras_ia:
            print(f"[PARCIAL] IA mencionou {len(corretos)} países corretamente, mas faltou {len(faltando_banco)}")
        else:
            print(f"[ERRO] IA tem {len(extras_ia)} país(es) incorreto(s)")

        taxa_acerto = (len(corretos) / len(ia_disse) * 100) if ia_disse else 0
        print(f"Taxa de acerto: {taxa_acerto:.1f}%")

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
    test_paises_jan2026()
