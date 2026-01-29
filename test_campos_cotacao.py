"""
Mapeia todos os campos da função IA_Cotacao()
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def mapear_cotacao():
    """Mapeia estrutura da IA_Cotacao"""
    print("=" * 80)
    print("MAPEAMENTO - IA_Cotacao()")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Executando: SELECT * FROM IA_Cotacao()")
        result = sql_client.execute_function("dbo.IA_Cotacao", filters=None)

        print(f"[OK] Retornou {len(result)} registros\n")

        if result and len(result) > 0:
            # Lista todas as colunas
            colunas = list(result[0].keys())
            print(f"3. COLUNAS DISPONÍVEIS ({len(colunas)} campos):")
            print("-" * 80)
            for i, col in enumerate(colunas, 1):
                print(f"{i:3d}. {col}")

            # Mostra primeiros 3 registros como exemplo
            print(f"\n\n4. EXEMPLOS DE DADOS (primeiros 3 registros):")
            print("-" * 80)

            for idx, registro in enumerate(result[:3], 1):
                print(f"\n--- REGISTRO {idx} ---")
                for col in colunas:
                    valor = registro.get(col)
                    # Trunca valores muito longos
                    if isinstance(valor, str) and len(valor) > 100:
                        valor = valor[:100] + "..."
                    print(f"{col}: {valor}")

            # Analisa tipos de dados
            print(f"\n\n5. ANÁLISE DE TIPOS:")
            print("-" * 80)
            
            primeiro = result[0]
            tipos_numericos = []
            tipos_texto = []
            tipos_data = []
            tipos_lista = []
            
            for col in colunas:
                val = primeiro.get(col)
                tipo = type(val).__name__
                
                if tipo in ['int', 'float', 'Decimal']:
                    tipos_numericos.append(col)
                elif tipo == 'str':
                    tipos_texto.append(col)
                elif tipo in ['date', 'datetime']:
                    tipos_data.append(col)
                elif tipo == 'list':
                    tipos_lista.append(col)

            print(f"\nCampos NUMÉRICOS ({len(tipos_numericos)}):")
            for col in tipos_numericos:
                print(f"  - {col}")

            print(f"\nCampos de TEXTO ({len(tipos_texto)}):")
            for col in tipos_texto:
                print(f"  - {col}")

            print(f"\nCampos de DATA ({len(tipos_data)}):")
            for col in tipos_data:
                print(f"  - {col}")

            print(f"\nCampos de LISTA ({len(tipos_lista)}):")
            for col in tipos_lista:
                print(f"  - {col}")

            # Estatísticas gerais
            print(f"\n\n6. ESTATÍSTICAS GERAIS:")
            print("-" * 80)
            print(f"Total de registros: {len(result)}")
            print(f"Total de colunas: {len(colunas)}")
            
            # Salva resultado completo
            with open("cotacao_mapeamento.txt", "w", encoding="utf-8") as f:
                f.write("MAPEAMENTO COMPLETO - IA_Cotacao()\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Total de registros: {len(result)}\n")
                f.write(f"Total de colunas: {len(colunas)}\n\n")
                f.write("COLUNAS:\n")
                for i, col in enumerate(colunas, 1):
                    f.write(f"{i:3d}. {col}\n")
                f.write("\n\nPRIMEIROS 5 REGISTROS:\n")
                f.write("=" * 80 + "\n")
                for idx, registro in enumerate(result[:5], 1):
                    f.write(f"\nREGISTRO {idx}:\n")
                    for col in colunas:
                        f.write(f"{col}: {registro.get(col)}\n")
            
            print("\nMapeamento completo salvo em: cotacao_mapeamento.txt")

        else:
            print("\n[AVISO] Nenhum registro retornado pela função")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    mapear_cotacao()
