"""
Verifica vendas de dezembro de 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_vendas_dez2025():
    """Analisa vendas de dezembro 2025"""
    print("=" * 80)
    print("VERIFICACAO - VENDAS DEZEMBRO 2025")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de dezembro 2025
        print("2. Consultando vendas de dezembro 2025...")
        filters = {"mesEmbarque": "2025/12"}
        results = sql_client.execute_function("IA_Vendas", filters)

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Agrupa por cliente
        clientes = defaultdict(lambda: {
            "contratos": 0,
            "diferenciais": [],
            "total_valor": 0,
            "total_sacas": 0
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE").strip()
            diferencial = row.get("diferencial")
            valor = row.get("valorTotal", 0) or 0
            sacas = row.get("sacas", 0) or 0

            clientes[cliente]["contratos"] += 1
            clientes[cliente]["total_valor"] += valor
            clientes[cliente]["total_sacas"] += sacas

            if diferencial is not None:
                clientes[cliente]["diferenciais"].append(float(diferencial))

        # Calcula médias e ordena por valor
        clientes_lista = []
        for cliente, data in clientes.items():
            dif_medio = None
            if data["diferenciais"]:
                dif_medio = sum(data["diferenciais"]) / len(data["diferenciais"])

            clientes_lista.append({
                "cliente": cliente,
                "contratos": data["contratos"],
                "total_valor": data["total_valor"],
                "total_sacas": data["total_sacas"],
                "diferencial_medio": round(dif_medio, 2) if dif_medio is not None else None
            })

        # Ordena por valor total
        clientes_lista.sort(key=lambda x: x["total_valor"], reverse=True)

        print("3. RESUMO GERAL:")
        print("-" * 80)
        print(f"Total de contratos: {len(results)}")
        print(f"Total de clientes: {len(clientes_lista)}")
        print(f"Valor total: R$ {sum(c['total_valor'] for c in clientes_lista):,.2f}")
        print(f"Total de sacas: {sum(c['total_sacas'] for c in clientes_lista):,.2f}")

        print("\n4. TOP 10 CLIENTES POR VALOR:")
        print("-" * 80)

        for i, c in enumerate(clientes_lista[:10], 1):
            print(f"\n{i:2d}. {c['cliente'][:50]}")
            print(f"    Contratos: {c['contratos']}")
            print(f"    Valor Total: R$ {c['total_valor']:,.2f}")
            print(f"    Sacas: {c['total_sacas']:,.2f}")
            print(f"    Diferencial Medio: {c['diferencial_medio']}" if c['diferencial_medio'] is not None else "    Diferencial Medio: N/A")

        # Comparação com resposta da IA
        print("\n5. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = {
            "total_contratos": 60,
            "total_clientes": 27,
            "destaques": [
                {"nome": "VOLCAFE", "contratos": 8, "valor": 4062797.41, "diferencial": -7.75},
                {"nome": "THE FOLGER COFFEE", "contratos": 2, "valor": 3734919.96, "diferencial": -25.0},
                {"nome": "ROTHFOS CORPORATON", "contratos": 2, "valor": 1676218.68, "diferencial": -32.0},
                {"nome": "AHOLD COFFEE", "contratos": 4, "valor": 1550346.68, "diferencial": -51.75}
            ]
        }

        print("\nIA disse:")
        print(f"  - {ia_disse['total_contratos']} contratos")
        print(f"  - {ia_disse['total_clientes']} clientes")

        print("\nBanco tem:")
        print(f"  - {len(results)} contratos")
        print(f"  - {len(clientes_lista)} clientes")

        # Validação de totais
        print("\n6. VALIDACAO DE TOTAIS:")
        print("-" * 80)

        validacoes = []

        if len(results) == ia_disse['total_contratos']:
            print(f"[OK] Total de contratos: {len(results)}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Contratos - IA disse: {ia_disse['total_contratos']}, Banco tem: {len(results)}")
            validacoes.append(False)

        if len(clientes_lista) == ia_disse['total_clientes']:
            print(f"[OK] Total de clientes: {len(clientes_lista)}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Clientes - IA disse: {ia_disse['total_clientes']}, Banco tem: {len(clientes_lista)}")
            validacoes.append(False)

        # Validação dos destaques
        print("\n7. VALIDACAO DOS CLIENTES DESTACADOS:")
        print("-" * 80)

        for destaque in ia_disse['destaques']:
            nome = destaque['nome']
            # Busca cliente no banco (case insensitive, parcial)
            encontrado = None
            for c in clientes_lista:
                if nome.upper() in c['cliente'].upper() or c['cliente'].upper() in nome.upper():
                    encontrado = c
                    break

            print(f"\n{nome}:")
            print(f"  IA disse:")
            print(f"    Contratos: {destaque['contratos']}")
            print(f"    Valor: R$ {destaque['valor']:,.2f}")
            print(f"    Diferencial: {destaque['diferencial']}")

            if encontrado:
                print(f"  Banco tem:")
                print(f"    Contratos: {encontrado['contratos']}")
                print(f"    Valor: R$ {encontrado['total_valor']:,.2f}")
                print(f"    Diferencial: {encontrado['diferencial_medio']}")

                # Valida cada campo
                val_contratos = encontrado['contratos'] == destaque['contratos']
                val_valor = abs(encontrado['total_valor'] - destaque['valor']) < 1
                val_dif = abs(encontrado['diferencial_medio'] - destaque['diferencial']) < 0.01 if encontrado['diferencial_medio'] is not None else False

                status_contratos = "[OK]" if val_contratos else "[ERRO]"
                status_valor = "[OK]" if val_valor else "[ERRO]"
                status_dif = "[OK]" if val_dif else "[ERRO]"

                print(f"  Status: Contratos {status_contratos}, Valor {status_valor}, Diferencial {status_dif}")

                validacoes.append(val_contratos and val_valor and val_dif)
            else:
                print(f"  Banco: [CLIENTE NAO ENCONTRADO]")
                validacoes.append(False)

        # Resultado final
        print("\n8. RESULTADO FINAL:")
        print("-" * 80)

        taxa_acerto = (sum(validacoes) / len(validacoes) * 100) if validacoes else 0
        print(f"Validacoes corretas: {sum(validacoes)}/{len(validacoes)}")
        print(f"Taxa de acerto: {taxa_acerto:.1f}%")

        if all(validacoes):
            print("\n[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif taxa_acerto >= 80:
            print(f"\n[PARCIAL] Resposta da IA esta {taxa_acerto:.1f}% correta")
        else:
            print(f"\n[ERRO] Resposta da IA tem problemas")

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
    test_vendas_dez2025()
