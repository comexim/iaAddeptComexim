"""Testa se o modelo Pydantic aceita comissão apenas com nome"""
from app.models.contrato_ada import ComissaoContrato

# Teste 1: Apenas nome (deveria aceitar)
try:
    com1 = ComissaoContrato(
        nomeAgenteExportacao="BJORN R. PAASCHE AGENTUR A/S",
        percentualComissao=0.8,
        tipoComissao="LIB"
    )
    print("✅ Teste 1 PASSOU: Aceita apenas nome do agente")
    print(f"   Nome: {com1.nomeAgenteExportacao}")
    print(f"   Código: {com1.codigoAgenteExportacao}")
    print(f"   Loja: {com1.lojaAgenteExportacao}")
except Exception as e:
    print(f"❌ Teste 1 FALHOU: {e}")

print()

# Teste 2: Código e loja (deveria aceitar)
try:
    com2 = ComissaoContrato(
        codigoAgenteExportacao="07889486",
        lojaAgenteExportacao="0001",
        percentualComissao=0.8,
        tipoComissao="LIB"
    )
    print("✅ Teste 2 PASSOU: Aceita código e loja")
    print(f"   Código: {com2.codigoAgenteExportacao}")
    print(f"   Loja: {com2.lojaAgenteExportacao}")
except Exception as e:
    print(f"❌ Teste 2 FALHOU: {e}")

print()

# Teste 3: Nenhum (deveria rejeitar)
try:
    com3 = ComissaoContrato(
        percentualComissao=0.8,
        tipoComissao="LIB"
    )
    print("❌ Teste 3 FALHOU: Deveria rejeitar comissão sem nome ou código")
except ValueError as e:
    print(f"✅ Teste 3 PASSOU: Rejeitou corretamente - {e}")
except Exception as e:
    print(f"⚠️ Teste 3: Erro inesperado - {e}")
