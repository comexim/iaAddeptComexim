"""Testa o fluxo completo de resolução de comissão"""
import asyncio
import json
import nest_asyncio
from app.models.contrato_ada import ComissaoContrato
from app.utils.field_resolver import FieldResolver

nest_asyncio.apply()

# Simula o que o LLM extrai quando usuário diz "agente é BJORN com 0.8%"
comissao_json = """[{
    "nomeAgenteExportacao": "BJORN",
    "percentualComissao": 0.8,
    "tipoComissao": "LIB"
}]"""

print("=" * 70)
print("TESTE DE FLUXO COMPLETO: Resolução de Agente por Nome")
print("=" * 70)
print()

# 1. Parse JSON para modelo Pydantic
print("📥 1. PARSE JSON → PYDANTIC")
print(f"   Input: {comissao_json}")
data = json.loads(comissao_json)
comissao_list = [ComissaoContrato(**item) for item in data]
print(f"   ✅ Parseado com sucesso: {len(comissao_list)} comissão(ões)")
print(f"   • Nome: {comissao_list[0].nomeAgenteExportacao}")
print(f"   • Código: {comissao_list[0].codigoAgenteExportacao}")
print(f"   • Loja: {comissao_list[0].lojaAgenteExportacao}")
print()

# 2. Resolução via API
print("🔍 2. RESOLUÇÃO VIA API")
com = comissao_list[0]
fr = FieldResolver()

if com.nomeAgenteExportacao and not com.codigoAgenteExportacao:
    print(f"   Detectado: apenas nome informado ('{com.nomeAgenteExportacao}')")
    print(f"   Chamando resolver...")
    
    codigo_resolvido, nome_agente, loja_agente = asyncio.run(
        fr.resolve_field("codigo_agente_exportacao", com.nomeAgenteExportacao, threshold=60)
    )
    
    print(f"   Retorno da API:")
    print(f"   • Código completo: {codigo_resolvido}")
    print(f"   • Nome completo: {nome_agente}")
    print()
    
    # 3. Split do código
    print("✂️ 3. SPLIT DO CÓDIGO")
    if codigo_resolvido and " " in codigo_resolvido:
        partes = codigo_resolvido.strip().split()
        if len(partes) >= 2:
            com.codigoAgenteExportacao = partes[0]
            com.lojaAgenteExportacao = partes[1]
            print(f"   Split realizado:")
            print(f"   • Código agente: {partes[0]}")
            print(f"   • Loja agente: {partes[1]}")
        else:
            print(f"   ⚠️ Código sem formato esperado (sem espaço)")
    
    if nome_agente:
        com.nomeAgenteExportacao = nome_agente
        print(f"   • Nome atualizado: {nome_agente}")
    print()

# 4. Resultado final
print("✅ 4. RESULTADO FINAL")
print(f"   Código: {com.codigoAgenteExportacao}")
print(f"   Loja: {com.lojaAgenteExportacao}")
print(f"   Nome: {com.nomeAgenteExportacao}")
print(f"   Percentual: {com.percentualComissao}%")
print(f"   Tipo: {com.tipoComissao}")
print()
print("=" * 70)
