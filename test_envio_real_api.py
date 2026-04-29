"""
Teste de envio REAL para a API ADA com dados completos.
Envia o JSON diretamente para a API e mostra a resposta.

USO:
    py test_envio_real_api.py
"""
import asyncio
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Log visível no console
logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.core.ada_api_client import ada_api_client


CONTRATO_COMPLETO = {
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


async def main():
    print("=" * 80)
    print("ENVIO REAL PARA API ADA")
    print("=" * 80)

    print(f"\nURL: {ada_api_client.base_url}/rest/ia/api/v1/postADA/vendaExp")
    print(f"\nJSON enviado:\n{json.dumps(CONTRATO_COMPLETO, indent=2, ensure_ascii=False)}")
    print("\n" + "-" * 80)

    try:
        # 1. Autentica
        print("\n1. Obtendo token...")
        token = await ada_api_client.get_token()
        print(f"   Token obtido: {token[:20]}..." if token else "   FALHA ao obter token!")

        # 2. Envia contrato
        print("\n2. Enviando contrato para API...")
        resultado = await ada_api_client.criar_contrato_venda(CONTRATO_COMPLETO)

        # 3. Mostra resultado
        print("\n" + "=" * 80)
        print("RESULTADO DA API:")
        print("=" * 80)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        print("=" * 80)

    except Exception as e:
        print(f"\nERRO: {e}")


if __name__ == "__main__":
    asyncio.run(main())
