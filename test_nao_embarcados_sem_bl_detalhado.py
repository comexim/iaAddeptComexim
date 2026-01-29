"""
Validação detalhada: Contratos NÃO embarcados e SEM BL em janeiro de 2026
Busca dados brutos direto do SQL sem otimizações
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SQLServerClient
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("VALIDAÇÃO DETALHADA: Contratos NÃO embarcados e SEM BL em janeiro de 2026")
print("=" * 80)
print()

# Conectar ao banco
client = SQLServerClient()
conn = client._get_connection()
cursor = conn.cursor()

# Query direta para janeiro 2026
query = """
SELECT
    contrato,
    cliente,
    saidaNavio,
    numeroBL,
    sacas
FROM IA_Vendas()
WHERE mesEmbarque = '2026/01'
ORDER BY contrato
"""

print("Executando query no SQL Server...")
cursor.execute(query)
rows = cursor.fetchall()

print(f"Total de contratos em janeiro 2026: {len(rows)}")
print()

# Classificar contratos
nao_embarcados_sem_bl = []
nao_embarcados_com_bl = []
embarcados_sem_bl = []
embarcados_com_bl = []

for row in rows:
    contrato = row[0]
    cliente = row[1]
    saida_navio = row[2]
    numero_bl = row[3]
    sacas = row[4]

    tem_saida = saida_navio and str(saida_navio).strip() != ""
    tem_bl = numero_bl and str(numero_bl).strip() != ""

    item = {
        'contrato': contrato,
        'cliente': cliente,
        'saidaNavio': saida_navio,
        'numeroBL': numero_bl,
        'sacas': float(sacas) if sacas else 0
    }

    if not tem_saida and not tem_bl:
        nao_embarcados_sem_bl.append(item)
    elif not tem_saida and tem_bl:
        nao_embarcados_com_bl.append(item)
    elif tem_saida and not tem_bl:
        embarcados_sem_bl.append(item)
    else:
        embarcados_com_bl.append(item)

# Fechar conexão
cursor.close()
conn.close()

print("=" * 80)
print("CLASSIFICAÇÃO DOS CONTRATOS:")
print("=" * 80)
print()

print(f"1. NÃO embarcados e SEM BL: {len(nao_embarcados_sem_bl)} contratos")
if nao_embarcados_sem_bl:
    total_sacas = sum(c['sacas'] for c in nao_embarcados_sem_bl)
    print(f"   Total de sacas: {total_sacas:,.2f}")
    print()
    print("   Primeiros 10:")
    for i, c in enumerate(nao_embarcados_sem_bl[:10], 1):
        print(f"      {i}. {c['contrato']} - {c['cliente'][:30]} - {c['sacas']:,.2f} sacas")
print()

print(f"2. NÃO embarcados mas COM BL: {len(nao_embarcados_com_bl)} contratos")
if nao_embarcados_com_bl:
    print("   Primeiros 5:")
    for i, c in enumerate(nao_embarcados_com_bl[:5], 1):
        print(f"      {i}. {c['contrato']} - {c['cliente'][:30]} - BL: {c['numeroBL']}")
print()

print(f"3. EMBARCADOS mas SEM BL: {len(embarcados_sem_bl)} contratos")
if embarcados_sem_bl:
    total_sacas = sum(c['sacas'] for c in embarcados_sem_bl)
    print(f"   Total de sacas: {total_sacas:,.2f}")
    print()
    print("   Primeiros 10:")
    for i, c in enumerate(embarcados_sem_bl[:10], 1):
        saida_val = c['saidaNavio']
        if saida_val and hasattr(saida_val, 'strftime'):
            saida = saida_val.strftime('%d/%m/%Y')
        elif saida_val:
            saida = str(saida_val)
        else:
            saida = 'N/A'
        print(f"      {i}. {c['contrato']} - {c['cliente'][:30]} - Saída: {saida}")
print()

print(f"4. EMBARCADOS e COM BL: {len(embarcados_com_bl)} contratos")
print()

print("=" * 80)
print("COMPARAÇÃO COM RESPOSTA DA IA:")
print("=" * 80)
print()

print("PERGUNTA DO USUÁRIO:")
print("  'Quantos contratos não foram embarcados e não têm BL?'")
print()
print("RESPOSTA DA IA:")
print("  'Em janeiro de 2026, há 7 contratos que foram embarcados,")
print("   mas não possuem BL'")
print()

print("ANÁLISE:")
print()

# Verificar se a IA respondeu sobre embarcados sem BL
if len(embarcados_sem_bl) == 7:
    print("[ERRO CRÍTICO] A IA inverteu a lógica da pergunta!")
    print()
    print("  Perguntado: NÃO foram embarcados e não têm BL")
    print("  Respondeu:  FORAM embarcados mas não têm BL")
    print()
    print(f"  Valor que a IA respondeu: 7 contratos (EMBARCADOS sem BL)")
    print(f"  Valor CORRETO: {len(nao_embarcados_sem_bl)} contratos (NÃO EMBARCADOS sem BL)")
    print()
    print("  Diferença: A IA contou a categoria OPOSTA!")
    print()

    if len(nao_embarcados_sem_bl) > 0:
        print("RESPOSTA CORRETA deveria ser:")
        print(f"  '{len(nao_embarcados_sem_bl)} contratos NÃO foram embarcados e não têm BL'")
        print()
        print("  Primeiros 5 contratos CORRETOS:")
        for i, c in enumerate(nao_embarcados_sem_bl[:5], 1):
            print(f"    {i}. {c['contrato']} ({c['cliente']})")
    else:
        print("  (Mas coincidentemente não há contratos NÃO embarcados sem BL)")

elif len(nao_embarcados_sem_bl) == 7:
    print("[OK] A IA respondeu corretamente!")
    print()
    print(f"  Valor correto: {len(nao_embarcados_sem_bl)} contratos")
else:
    print("[ERRO] A IA respondeu 7 contratos, mas os valores reais são:")
    print(f"  - NÃO embarcados sem BL: {len(nao_embarcados_sem_bl)} contratos")
    print(f"  - EMBARCADOS sem BL: {len(embarcados_sem_bl)} contratos")
    print()
    print("  A resposta da IA não corresponde a nenhuma das categorias!")

print()
print("=" * 80)
print("RESUMO:")
print("=" * 80)
print(f"Total de contratos em janeiro 2026: {len(rows)}")
print(f"  - {len(nao_embarcados_sem_bl)} NÃO embarcados sem BL (RESPOSTA CORRETA)")
print(f"  - {len(nao_embarcados_com_bl)} NÃO embarcados com BL")
print(f"  - {len(embarcados_sem_bl)} EMBARCADOS sem BL")
print(f"  - {len(embarcados_com_bl)} EMBARCADOS com BL")
print()

# Salvar resultado detalhado
with open("resultado_detalhado_nao_embarcados_bl.txt", "w", encoding="utf-8") as f:
    f.write("CONTRATOS NÃO EMBARCADOS SEM BL (janeiro 2026):\n")
    f.write("=" * 80 + "\n\n")
    for i, c in enumerate(nao_embarcados_sem_bl, 1):
        f.write(f"{i}. {c['contrato']} - {c['cliente']} - {c['sacas']:,.2f} sacas\n")

    f.write("\n\n")
    f.write("CONTRATOS EMBARCADOS SEM BL (janeiro 2026):\n")
    f.write("=" * 80 + "\n\n")
    for i, c in enumerate(embarcados_sem_bl, 1):
        saida_val = c['saidaNavio']
        if saida_val and hasattr(saida_val, 'strftime'):
            saida = saida_val.strftime('%d/%m/%Y')
        elif saida_val:
            saida = str(saida_val)
        else:
            saida = 'N/A'
        f.write(f"{i}. {c['contrato']} - {c['cliente']} - Saída: {saida}\n")

print("Detalhes salvos em: resultado_detalhado_nao_embarcados_bl.txt")
