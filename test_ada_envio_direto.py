"""
Teste de envio direto para API ADA
Envia os dados de exemplo exatos fornecidos pelo usuário
"""

import asyncio
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.ada_api_client import ADAApiClient


async def main():
    """Testa envio direto dos dados para a API ADA"""
    
    # Dados de exemplo fornecidos pelo usuário
    dados_contrato = {
        "codigoFilial": "05",
        "codigoCliente": "EX288915O",
        "lojaCliente": "0001",
        "codigoEmbalagem": "00316",
        "quantidadeKg": 38400,
        "padraoQualidade": "GRD",
        "modalidadePagamento": "INT",
        "quantidadeContainer": 1,
        "mesEmbarque": "06/2026",
        "exigeEudr": "N",
        "amostraPreEmbarque": "N",
        "condicaoEntrega": "EMB",
        "moedaFixacao": "USD",
        "tipoContrato": "ESCC",
        "condicaoPeso": "NDW",
        "nomeCliente": "JDE",
        "dataPrevisaoEntrega": "",
        "quantidadeEmbalagem": 40,
        "quantidadePallet": 0,
        "taxaFixacao": 0,
        "peneira14": True,
        "taxaDolar": 5.123,
        "fixacaoContrato": [
            {
                "sacasFixacao": 300,
                "mesAnoFixacao": "07/2026",
                "tipoPrecoFixacao": "A",
                "fixadorPreco": "E",
                "tipoValor": "C",
                "referenciaBolsaNy": 400
            }
        ],
        "comissaoContrato": [
            {
                "codigoAgenteExportacao": "INPS00030",
                "lojaAgenteExportacao": "0001",
                "nomeAgenteExportacao": "",
                "percentualComissao": 0.5,
                "tipoComissao": "LIB"
            }
        ]
    }
    
    print("=" * 80)
    print("TESTE DE ENVIO DIRETO - API ADA")
    print("=" * 80)
    print("\nDADOS DO CONTRATO:")
    print(f"Cliente: {dados_contrato['nomeCliente']} ({dados_contrato['codigoCliente']})")
    print(f"Quantidade: {dados_contrato['quantidadeKg']:,}kg")
    print(f"Embalagem: {dados_contrato['codigoEmbalagem']}")
    print(f"Mês Embarque: {dados_contrato['mesEmbarque']}")
    print(f"Tipo Contrato: {dados_contrato['tipoContrato']}")
    print(f"Condição Entrega: {dados_contrato['condicaoEntrega']}")
    print(f"\nFixação: {dados_contrato['fixacaoContrato'][0]['sacasFixacao']} sacas em {dados_contrato['fixacaoContrato'][0]['mesAnoFixacao']}")
    print(f"Comissão: {dados_contrato['comissaoContrato'][0]['percentualComissao']}% ({dados_contrato['comissaoContrato'][0]['tipoComissao']})")
    
    print("\n" + "-" * 80)
    print("ETAPA 1: Autenticação")
    print("-" * 80)
    
    # Criar cliente ADA
    client = ADAApiClient()
    
    # Obter token
    token = await client.get_token()
    
    if token:
        print(f"✅ Token obtido: {token[:50]}...")
    else:
        print("❌ Falha ao obter token")
        return
    
    print("\n" + "-" * 80)
    print("ETAPA 2: Criar Contrato de Venda")
    print("-" * 80)
    
    try:
        # Enviar contrato
        resultado = await client.criar_contrato_venda(dados_contrato)
        
        print("\n" + "=" * 80)
        print("✅ CONTRATO CRIADO COM SUCESSO!")
        print("=" * 80)
        
        if resultado:
            if "numeroContrato" in resultado:
                print(f"\n🎉 Número do Contrato: {resultado['numeroContrato']}")
            
            if "message" in resultado:
                print(f"📄 Mensagem: {resultado['message']}")
            
            if resultado.get("alertas"):
                print(f"\n⚠️  Alertas:")
                for alerta in resultado["alertas"]:
                    if alerta:
                        print(f"   • {alerta}")
            
            print(f"\n📋 Resposta completa:")
            import json
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
        else:
            print("\n❌ Retorno vazio (None)")
    
    except Exception as erro:
        print("\n" + "=" * 80)
        print("❌ ERRO AO CRIAR CONTRATO")
        print("=" * 80)
        print(f"\n{erro}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
