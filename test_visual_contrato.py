"""
Teste visual do formato de apresentação do contrato
"""

# Exemplo de JSON de contrato
json_exemplo = {
    "codigoCliente": "EX288915O",
    "lojaCliente": "01",
    "nomeCliente": "EMPRESA EXEMPLO LTDA",
    "codigoEmbalagem": "00316",
    "padraoQualidade": "NYC2/3SC17",
    "quantidadeKg": 50000.0,
    "quantidadeContainer": 1,
    "quantidadeEmbalagem": 30,
    "quantidadePallet": 20,
    "peneira14": True,
    "peneira17": False,
    "peneiraGrinder": True,
    "condicaoEntrega": "EMB",
    "condicaoPeso": "NDW",
    "mesEmbarque": "07/2026",
    "dataPrevisaoEntrega": "2026-07-15",
    "tipoContrato": "VDA",
    "modalidadePagamento": "30DD",
    "moedaFixacao": "USD",
    "taxaDolar": 5.223,
    "exigeEudr": "N",
    "amostraPreEmbarque": "N",
    "fixacaoContrato": [
        {
            "sacasFixacao": 300,
            "tipoPrecoFixacao": "A",
            "referenciaPrecoFixacao": 400,
            "fixadorPreco": "E",
            "mesAnoFixacao": "07/2026",
            "tipoValor": "C"
        }
    ],
    "comissaoContrato": []
}

def formatar_resumo_contrato(json_data):
    """Formata dados do contrato de forma legível"""
    linhas = []
    linhas.append("="* 70)
    linhas.append("📋 **RESUMO DO CONTRATO DE VENDA/EXPORTAÇÃO**")
    linhas.append("="* 70)
    linhas.append("")
    
    # Cliente
    linhas.append("👤 **CLIENTE:**")
    linhas.append(f"   • Código: {json_data.get('codigoCliente', 'N/A')}")
    linhas.append(f"   • Loja: {json_data.get('lojaCliente', 'N/A')}")
    if json_data.get('nomeCliente') and json_data.get('nomeCliente') != 'SEM_NOME':
        linhas.append(f"   • Nome: {json_data.get('nomeCliente')}")
    linhas.append("")
    
    # Produto
    linhas.append("📦 **PRODUTO:**")
    linhas.append(f"   • Embalagem: {json_data.get('codigoEmbalagem', 'N/A')}")
    linhas.append(f"   • Padrão Qualidade: {json_data.get('padraoQualidade', 'N/A')}")
    linhas.append(f"   • Quantidade: {json_data.get('quantidadeKg', 0):,.0f} kg")
    linhas.append(f"   • Containers: {json_data.get('quantidadeContainer', 0)}")
    linhas.append(f"   • Embalagens: {json_data.get('quantidadeEmbalagem', 0)}")
    if json_data.get('quantidadePallet'):
        linhas.append(f"   • Pallets: {json_data.get('quantidadePallet', 0)}")
    linhas.append("")
    
    # Peneiras
    peneiras_ativas = []
    if json_data.get('peneira14'):
        peneiras_ativas.append("14")
    if json_data.get('peneira17'):
        peneiras_ativas.append("17")
    if json_data.get('peneiraGrinder'):
        peneiras_ativas.append("Grinder")
    if peneiras_ativas:
        linhas.append("🔍 **PENEIRAS:**")
        linhas.append(f"   • {', '.join(peneiras_ativas)}")
        linhas.append("")
    
    # Logística
    linhas.append("🚢 **LOGÍSTICA:**")
    linhas.append(f"   • Condição Entrega: {json_data.get('condicaoEntrega', 'N/A')}")
    linhas.append(f"   • Condição Peso: {json_data.get('condicaoPeso', 'N/A')}")
    linhas.append(f"   • Mês Embarque: {json_data.get('mesEmbarque', 'N/A')}")
    if json_data.get('dataPrevisaoEntrega'):
        linhas.append(f"   • Previsão Entrega: {json_data.get('dataPrevisaoEntrega')}")
    linhas.append("")
    
    # Comercial
    linhas.append("💰 **COMERCIAL:**")
    linhas.append(f"   • Tipo Contrato: {json_data.get('tipoContrato', 'N/A')}")
    linhas.append(f"   • Modalidade Pagamento: {json_data.get('modalidadePagamento', 'N/A')}")
    linhas.append(f"   • Moeda Fixação: {json_data.get('moedaFixacao', 'N/A')}")
    linhas.append(f"   • Taxa Dólar: {json_data.get('taxaDolar', 0):.3f}")
    linhas.append("")
    
    # Requisitos
    linhas.append("📋 **REQUISITOS:**")
    linhas.append(f"   • EUDR: {'Sim' if json_data.get('exigeEudr') == 'S' else 'Não'}")
    linhas.append(f"   • Amostra Pré-Embarque: {'Sim' if json_data.get('amostraPreEmbarque') == 'S' else 'Não'}")
    linhas.append("")
    
    # Fixação
    if json_data.get('fixacaoContrato'):
        linhas.append("📊 **FIXAÇÃO:**")
        for i, fix in enumerate(json_data.get('fixacaoContrato', []), 1):
            linhas.append(f"   [{i}] Sacas: {fix.get('sacasFixacao', 0)} | Tipo: {fix.get('tipoPrecoFixacao', 'N/A')} | Referência: {fix.get('referenciaPrecoFixacao', 'N/A')}")
            if fix.get('tipoPrecoFixacao') == 'A':
                linhas.append(f"       Fixador: {fix.get('fixadorPreco', 'N/A')} | Mês/Ano: {fix.get('mesAnoFixacao', 'N/A')}")
            linhas.append(f"       Tipo Valor: {fix.get('tipoValor', 'N/A')}")
        linhas.append("")
    
    # Comissão
    if json_data.get('comissaoContrato'):
        linhas.append("💵 **COMISSÃO:**")
        for i, com in enumerate(json_data.get('comissaoContrato', []), 1):
            linhas.append(f"   [{i}] Valor: {com.get('valorComissao', 0)} | Percentual: {com.get('percentualComissao', 0)}% | País: {com.get('paisComissao', 'N/A')}")
        linhas.append("")
    
    linhas.append("="* 70)
    
    return "\n".join(linhas)

print("\n" + formatar_resumo_contrato(json_exemplo))

print("\n✅ **Os dados estão corretos?**")
print("   • Digite **SIM** para enviar para a API")
print("   • Ou informe o campo que deseja alterar (ex: 'mudar quantidade para 50000')")
