"""
Mapeamento completo da função IA_Estoque()
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SQLServerClient
from dotenv import load_dotenv
from decimal import Decimal
from datetime import datetime, date

load_dotenv()

print("=" * 80)
print("MAPEAMENTO COMPLETO: IA_Estoque()")
print("=" * 80)
print()

# Conectar ao banco
client = SQLServerClient()
conn = client._get_connection()
cursor = conn.cursor()

# Query para pegar todos os registros
query = "SELECT TOP 100 * FROM IA_Estoque()"

print("Executando query no SQL Server...")
cursor.execute(query)

# Pegar descrição das colunas
columns = [column[0] for column in cursor.description]
print(f"\n[OK] Total de colunas: {len(columns)}")
print("\nCOLUNAS DISPONÍVEIS:")
for i, col in enumerate(columns, 1):
    print(f"  {i:2d}. {col}")

# Pegar alguns registros de exemplo
rows = cursor.fetchall()
print(f"\n[OK] Total de registros retornados: {len(rows)}")

if rows:
    print("\n" + "=" * 80)
    print("ANÁLISE DOS TIPOS DE DADOS")
    print("=" * 80)

    # Analisar tipos de dados do primeiro registro
    first_row = rows[0]

    tipos = {}
    for col_name, value in zip(columns, first_row):
        tipo = type(value).__name__
        valor_exemplo = value

        # Formatação especial para tipos específicos
        if isinstance(value, Decimal):
            valor_exemplo = float(value)
        elif isinstance(value, (datetime, date)):
            valor_exemplo = value.strftime('%Y-%m-%d') if isinstance(value, date) else value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, str):
            valor_exemplo = value.strip() if value else ""

        tipos[col_name] = {
            'tipo': tipo,
            'exemplo': valor_exemplo
        }

    # Agrupar por tipo
    print("\nPor tipo de dado:")
    for tipo_nome in ['str', 'Decimal', 'float', 'int', 'datetime', 'date', 'bool']:
        campos_tipo = [col for col, info in tipos.items() if info['tipo'] == tipo_nome]
        if campos_tipo:
            print(f"\n{tipo_nome.upper()} ({len(campos_tipo)} campos):")
            for campo in campos_tipo[:10]:  # Mostrar primeiros 10
                exemplo = tipos[campo]['exemplo']
                if isinstance(exemplo, str) and len(exemplo) > 50:
                    exemplo = exemplo[:50] + "..."
                print(f"  - {campo}: {exemplo}")
            if len(campos_tipo) > 10:
                print(f"  ... e mais {len(campos_tipo) - 10} campos")

    # Salvar mapeamento detalhado
    print("\n" + "=" * 80)
    print("SALVANDO MAPEAMENTO DETALHADO...")
    print("=" * 80)

    with open("mapeamento_estoque.txt", "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("MAPEAMENTO COMPLETO: IA_Estoque()\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total de colunas: {len(columns)}\n")
        f.write(f"Total de registros analisados: {len(rows)}\n\n")

        f.write("COLUNAS E TIPOS:\n")
        f.write("-" * 80 + "\n\n")

        for col in columns:
            info = tipos[col]
            f.write(f"{col}\n")
            f.write(f"  Tipo: {info['tipo']}\n")
            f.write(f"  Exemplo: {info['exemplo']}\n\n")

        # Análise de valores únicos para campos importantes
        f.write("\n" + "=" * 80 + "\n")
        f.write("ANÁLISE DE VALORES ÚNICOS\n")
        f.write("=" * 80 + "\n\n")

        # Campos categóricos para analisar
        campos_categoricos = ['filial', 'linha', 'certificado', 'bebida', 'tipo', 'preparo', 'safra']

        for campo in campos_categoricos:
            if campo in columns:
                idx = columns.index(campo)
                valores = [row[idx] for row in rows if row[idx]]
                valores_unicos = list(set(str(v).strip() if v else '' for v in valores if v))
                valores_unicos = [v for v in valores_unicos if v]  # Remove vazios

                if valores_unicos:
                    f.write(f"\n{campo.upper()} ({len(valores_unicos)} valores únicos):\n")
                    for v in sorted(valores_unicos)[:20]:
                        count = sum(1 for row in rows if str(row[idx]).strip() == v)
                        f.write(f"  - {v}: {count} registros\n")
                    if len(valores_unicos) > 20:
                        f.write(f"  ... e mais {len(valores_unicos) - 20} valores\n")

        # Estatísticas numéricas
        f.write("\n" + "=" * 80 + "\n")
        f.write("ESTATÍSTICAS NUMÉRICAS\n")
        f.write("=" * 80 + "\n\n")

        campos_numericos = [col for col, info in tipos.items() if info['tipo'] in ['Decimal', 'float', 'int']]

        for campo in campos_numericos[:15]:  # Primeiros 15
            idx = columns.index(campo)
            valores = [float(row[idx]) if row[idx] is not None else 0 for row in rows]
            valores_nao_zero = [v for v in valores if v != 0]

            if valores_nao_zero:
                f.write(f"\n{campo}:\n")
                f.write(f"  Mínimo: {min(valores_nao_zero):,.2f}\n")
                f.write(f"  Máximo: {max(valores_nao_zero):,.2f}\n")
                f.write(f"  Média: {sum(valores_nao_zero)/len(valores_nao_zero):,.2f}\n")
                f.write(f"  Registros não-zero: {len(valores_nao_zero)}/{len(valores)}\n")

        # Exemplos de registros completos
        f.write("\n" + "=" * 80 + "\n")
        f.write("EXEMPLOS DE REGISTROS COMPLETOS\n")
        f.write("=" * 80 + "\n\n")

        for i, row in enumerate(rows[:3], 1):
            f.write(f"\nREGISTRO {i}:\n")
            f.write("-" * 80 + "\n")
            for col, val in zip(columns, row):
                if isinstance(val, Decimal):
                    val = float(val)
                elif isinstance(val, (datetime, date)):
                    val = val.strftime('%Y-%m-%d') if isinstance(val, date) else val.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(val, str):
                    val = val.strip()
                f.write(f"{col}: {val}\n")

    print(f"\n[OK] Mapeamento salvo em: mapeamento_estoque.txt")

    # Criar resumo visual
    print("\n" + "=" * 80)
    print("RESUMO VISUAL")
    print("=" * 80)

    print(f"\n[INFO] Total de colunas: {len(columns)}")
    print(f"[INFO] Total de registros: {len(rows)}")

    # Identificar campos chave
    campos_chave = []
    if 'idProtheus' in columns:
        campos_chave.append('idProtheus (ID único)')
    if 'produto' in columns or 'descricao' in columns:
        campos_chave.append('produto/descricao (Descrição)')
    if 'quantidade' in columns or 'saldo' in columns:
        campos_chave.append('quantidade/saldo (Quantidade em estoque)')
    if 'filial' in columns:
        campos_chave.append('filial (Localização)')

    if campos_chave:
        print("\n[KEY] Campos chave identificados:")
        for campo in campos_chave:
            print(f"  - {campo}")

else:
    print("\n[WARNING] Nenhum registro encontrado")

# Fechar conexão
cursor.close()
conn.close()

print("\n" + "=" * 80)
print("[OK] MAPEAMENTO CONCLUIDO!")
print("=" * 80)
