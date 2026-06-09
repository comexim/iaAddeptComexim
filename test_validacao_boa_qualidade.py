"""
Valida resposta da IA: "Temos café de boa qualidade em estoque?"
IA respondeu sobre certificações, mas deveria verificar impureza < 10%
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Temos café de boa qualidade em estoque?")
print("=" * 80)
print()

print("ANÁLISE: O que é 'boa qualidade'?")
print()
print("Critérios possíveis:")
print("  1. Certificações (4C, GC, RF, etc)")
print("  2. Impureza baixa (< 10%)")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros: {len(results)}")
print()

# ANÁLISE 1: Café com certificações
print("=" * 80)
print("ANÁLISE 1: Café com certificações")
print("=" * 80)
results_com_cert = [r for r in results if r.get("certificado", "").strip()]
print(f"Registros com certificação: {len(results_com_cert)}")

certificados = set()
sacas_por_cert = {}
for r in results_com_cert:
    cert = r.get("certificado", "").strip()
    if cert:
        certificados.add(cert)
        sacas_por_cert[cert] = sacas_por_cert.get(cert, 0) + (r.get("sacas", 0) or 0)

print(f"Certificados encontrados: {', '.join(sorted(certificados))}")
print()
print("Sacas por certificado:")
for cert in sorted(certificados):
    print(f"  {cert}: {sacas_por_cert[cert]:,.2f} sacas")
print()

# ANÁLISE 2: Café com baixa impureza (< 10%)
print("=" * 80)
print("ANÁLISE 2: Café com baixa impureza (< 10%)")
print("=" * 80)
results_baixa_impureza = [r for r in results if r.get("impureza", 100) < 10]
print(f"Registros com impureza < 10%: {len(results_baixa_impureza)}")

total_sacas_baixa_impureza = Decimal(0)
for r in results_baixa_impureza:
    sacas = r.get("sacas", 0)
    if sacas:
        if isinstance(sacas, Decimal):
            total_sacas_baixa_impureza += sacas
        else:
            total_sacas_baixa_impureza += Decimal(str(sacas))

print(f"Total de sacas com impureza < 10%: {float(total_sacas_baixa_impureza):,.2f}")
print()

# Estatísticas de impureza
impurezas = [r.get("impureza", 0) for r in results if r.get("impureza") is not None]
if impurezas:
    print("Estatísticas de impureza:")
    print(f"  Mínima: {min(impurezas):.2f}%")
    print(f"  Máxima: {max(impurezas):.2f}%")
    print(f"  Média: {sum(impurezas)/len(impurezas):.2f}%")
    print()

# ANÁLISE 3: Interseção (certificado + baixa impureza)
print("=" * 80)
print("ANÁLISE 3: Café com AMBOS (certificado E impureza < 10%)")
print("=" * 80)
results_ambos = [
    r for r in results
    if r.get("certificado", "").strip() and r.get("impureza", 100) < 10
]
print(f"Registros com certificado E impureza < 10%: {len(results_ambos)}")

total_sacas_ambos = Decimal(0)
for r in results_ambos:
    sacas = r.get("sacas", 0)
    if sacas:
        if isinstance(sacas, Decimal):
            total_sacas_ambos += sacas
        else:
            total_sacas_ambos += Decimal(str(sacas))

print(f"Total de sacas (certificado + baixa impureza): {float(total_sacas_ambos):,.2f}")
print()

# CONCLUSÃO
print("=" * 80)
print("CONCLUSÃO:")
print("=" * 80)
print()
print("A IA respondeu sobre CERTIFICACOES, o que esta correto:")
print(f"  [OK] Temos cafe com certificacoes (4C, GC, RF)")
print(f"  [OK] Total: {len(results_com_cert)} lotes com certificados")
print()
print("POREM, 'boa qualidade' tambem pode significar BAIXA IMPUREZA:")
print(f"  [INFO] Temos {float(total_sacas_baixa_impureza):,.2f} sacas com impureza < 10%")
print(f"  [INFO] Isso representa {len(results_baixa_impureza)} lotes")
print()
print("RECOMENDACAO:")
print("  Adicionar 'boa qualidade' como trigger para filtro de impureza < 10%")
print("  Assim a IA pode responder com dados mais objetivos.")
print()
print("=" * 80)
