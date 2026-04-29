"""
Models para criação de contrato via API ADA
"""
from typing import Optional, List
from pydantic import BaseModel, Field, validator, model_validator
from datetime import date


class FixacaoContrato(BaseModel):
    """Model para fixação de contrato"""
    sacasFixacao: Optional[int] = Field(None, description="Quantidade de sacas para fixação")
    tipoPrecoFixacao: Optional[str] = Field(None, description="Tipo de preço: 'A' (A fixar), 'F' (Fixo)")
    tipoValor: Optional[str] = Field(None, description="Tipo de valor")
    referenciaBolsaNy: Optional[float] = Field(None, description="Referência da bolsa NY")
    mesAnoFixacao: Optional[str] = Field(None, description="Mês/Ano fixação (obrigatório se tipoPrecoFixacao == 'A')")
    fixadorPreco: Optional[str] = Field(None, description="Fixador de preço (obrigatório se tipoPrecoFixacao == 'A')")

    @validator('mesAnoFixacao', always=True)
    def validar_mes_ano_fixacao(cls, v, values):
        """Valida que mesAnoFixacao é obrigatório quando tipoPrecoFixacao == 'A'"""
        if values.get('tipoPrecoFixacao') == 'A' and not v:
            raise ValueError("mesAnoFixacao é obrigatório quando tipoPrecoFixacao == 'A'")
        return v

    @validator('fixadorPreco', always=True)
    def validar_fixador_preco(cls, v, values):
        """Valida que fixadorPreco é obrigatório quando tipoPrecoFixacao == 'A'"""
        if values.get('tipoPrecoFixacao') == 'A' and not v:
            raise ValueError("fixadorPreco é obrigatório quando tipoPrecoFixacao == 'A'")
        return v

    class Config:
        """Permite campos extras"""
        extra = "allow"


class ComissaoContrato(BaseModel):
    """Model para comissão de contrato"""
    codigoAgenteExportacao: Optional[str] = Field(None, description="Código do agente (obrigatório se não informado nome)")
    lojaAgenteExportacao: Optional[str] = Field(None, description="Loja do agente (obrigatório se não informado nome)")
    nomeAgenteExportacao: Optional[str] = Field(None, description="Nome do agente (obrigatório se não informado código)")
    percentualComissao: Optional[float] = Field(None, description="Percentual de comissão")
    tipoComissao: Optional[str] = Field(None, description="Tipo de comissão")

    @model_validator(mode='after')
    def validar_agente(self):
        """Valida que código OU nome do agente foi informado"""
        if not self.codigoAgenteExportacao and not self.nomeAgenteExportacao:
            raise ValueError("Informe codigoAgenteExportacao/lojaAgenteExportacao OU nomeAgenteExportacao")
        return self
    
    class Config:
        """Permite campos extras"""
        extra = "allow"


class ContratoVendaExportacao(BaseModel):
    """Model completo para criação de contrato de venda exportação"""
    
    # Campos obrigatórios
    codigoFilial: str = Field(default="05", description="Código da filial (sempre 05)")
    
    # Cliente (código+loja OU nome)
    codigoCliente: Optional[str] = Field(None, description="Código do cliente (obrigatório se não informado nome)")
    lojaCliente: Optional[str] = Field(None, description="Loja do cliente (obrigatório se não informado nome)")
    nomeCliente: Optional[str] = Field(None, description="Nome do cliente (obrigatório se não informado código)")
    
    # Detalhes do contrato
    codigoEmbalagem: Optional[str] = Field(None, description="Código da embalagem")
    quantidadeKg: Optional[float] = Field(None, description="Quantidade em KG")
    padraoQualidade: Optional[str] = Field(None, description="Padrão de qualidade")
    modalidadePagamento: Optional[str] = Field(None, description="Modalidade de pagamento")
    quantidadeContainer: Optional[int] = Field(None, description="Quantidade de containers")
    mesEmbarque: Optional[str] = Field(None, description="Mês de embarque")
    exigeEudr: Optional[str] = Field(None, description="Exige EUDR? (S ou N)")
    exigeOTA: Optional[str] = Field(None, description="Exige OTA? (S ou N)")
    amostraPreEmbarque: Optional[str] = Field(None, description="Requer amostra pré-embarque? (S ou N)")
    condicaoEntrega: Optional[str] = Field(None, description="Condição de entrega")
    moedaFixacao: Optional[str] = Field(None, description="Moeda de fixação")
    tipoContrato: Optional[str] = Field(None, description="Tipo de contrato")
    condicaoPeso: Optional[str] = Field(None, description="Condição de peso")
    dataPrevisaoEntrega: Optional[str] = Field(None, description="Data previsão entrega (obrigatório se condicaoEntrega == 'ENT')")
    quantidadeEmbalagem: Optional[int] = Field(None, description="Quantidade de embalagens")
    quantidadePallet: Optional[int] = Field(None, description="Quantidade de pallets")
    taxaFixacao: Optional[float] = Field(0, description="Taxa de fixação")
    peneira14: Optional[bool] = Field(None, description="Peneira 14")
    peneira17: Optional[bool] = Field(None, description="Peneira 17")
    peneiraGrinder: Optional[bool] = Field(None, description="Peneira Grinder")
    taxaDolar: Optional[float] = Field(None, description="Taxa do dólar")
    
    # Campos opcionais adicionais
    descricaoQualidade: Optional[str] = Field(None, description="Descrição livre da qualidade")
    referenciaCliente: Optional[str] = Field(None, description="Referência do cliente")
    condicaoPagamento: Optional[str] = Field(None, description="Condição de pagamento (ex: B30)")
    armazemPreparo: Optional[str] = Field(None, description="Armazém de preparo")
    produtoExportacao: Optional[str] = Field(None, description="Código do produto de exportação")
    descricaoDetalhada: Optional[str] = Field(None, description="Descrição detalhada")
    codigoBanco: Optional[str] = Field(None, description="Código do banco")
    agenciaBancaria: Optional[str] = Field(None, description="Agência bancária")
    digitoVerificadorAgencia: Optional[str] = Field(None, description="Dígito verificador da agência")
    contaCorrente: Optional[str] = Field(None, description="Conta corrente")
    digitoVerificadorContaCorrente: Optional[str] = Field(None, description="Dígito verificador da conta corrente")
    periodoEmbarque: Optional[str] = Field(None, description="Período de embarque")
    responsavelDocumento: Optional[str] = Field(None, description="Responsável pelo documento")
    embarcador: Optional[str] = Field(None, description="Embarcador")
    tipoVenda: Optional[str] = Field(None, description="Tipo de venda (ex: N)")
    incoterm: Optional[str] = Field(None, description="Incoterm (ex: FOB)")
    certificador: Optional[str] = Field(None, description="Certificador")
    contratoLiberado: Optional[str] = Field(None, description="Contrato liberado (S ou N)")
    referenciaCorretor: Optional[str] = Field(None, description="Referência do corretor")
    armazemDestino: Optional[str] = Field(None, description="Armazém de destino")
    vendedor: Optional[str] = Field(None, description="Vendedor")
    variacaoPeso: Optional[str] = Field(None, description="Variação de peso")
    totalCostDdp: Optional[float] = Field(None, description="Total cost DDP")
    difCashAgainst: Optional[float] = Field(None, description="Diferencial cash against")
    alerta: Optional[str] = Field(None, description="Alerta")
    notas: Optional[str] = Field(None, description="Notas")
    pilhaPassada: Optional[str] = Field(None, description="Pilha passada (S ou N)")
    sampleConditions: Optional[str] = Field(None, description="Condições de amostra")
    spot: Optional[str] = Field(None, description="Spot")
    bolsaFixacao: Optional[str] = Field(None, description="Bolsa de fixação")
    codigoClienteFinal: Optional[str] = Field(None, description="Código do cliente final")
    lojaClienteFinal: Optional[str] = Field(None, description="Loja do cliente final")
    nomeClienteFinal: Optional[str] = Field(None, description="Nome do cliente final")
    diferencialClienteFinal: Optional[float] = Field(None, description="Diferencial do cliente final")
    
    # Arrays
    fixacaoContrato: Optional[List[FixacaoContrato]] = Field(default_factory=list, description="Lista de fixações")
    comissaoContrato: Optional[List[ComissaoContrato]] = Field(default_factory=list, description="Lista de comissões")
    
    class Config:
        """Permite campos extras"""
        extra = "allow"
        # Desabilita validação automática para permitir validação manual
        validate_assignment = False

    def validar_cliente(self) -> bool:
        """Valida que código+loja OU nome do cliente foi informado"""
        if not self.codigoCliente and not self.nomeCliente:
            return False
        if self.codigoCliente and not self.lojaCliente:
            return False
        return True

    def validar_data_entrega(self) -> bool:
        """Valida que data de entrega é obrigatória quando condição = ENT"""
        if self.condicaoEntrega == 'ENT' and not self.dataPrevisaoEntrega:
            return False
        return True

    def to_dict(self):
        """Converte para dict removendo campos None e serializando sublistas corretamente"""
        # Usa dict() do Pydantic para obter todos os campos
        data = {}
        
        # Campos simples em ordem
        if self.codigoFilial: data['codigoFilial'] = self.codigoFilial
        if self.codigoCliente: data['codigoCliente'] = self.codigoCliente
        if self.lojaCliente: data['lojaCliente'] = self.lojaCliente
        if self.nomeCliente: data['nomeCliente'] = self.nomeCliente
        if self.codigoEmbalagem: data['codigoEmbalagem'] = self.codigoEmbalagem
        if self.quantidadeKg is not None: data['quantidadeKg'] = self.quantidadeKg
        if self.padraoQualidade: data['padraoQualidade'] = self.padraoQualidade
        if self.modalidadePagamento: data['modalidadePagamento'] = self.modalidadePagamento
        if self.peneira14 is not None: data['peneira14'] = self.peneira14
        if self.peneira17 is not None: data['peneira17'] = self.peneira17
        if self.peneiraGrinder is not None: data['peneiraGrinder'] = self.peneiraGrinder
        if self.quantidadeContainer is not None: data['quantidadeContainer'] = self.quantidadeContainer
        if self.mesEmbarque: data['mesEmbarque'] = self.mesEmbarque
        if self.exigeEudr: data['exigeEudr'] = self.exigeEudr
        if self.exigeOTA: data['exigeOTA'] = self.exigeOTA
        if self.amostraPreEmbarque: data['amostraPreEmbarque'] = self.amostraPreEmbarque
        if self.condicaoEntrega: data['condicaoEntrega'] = self.condicaoEntrega
        if self.moedaFixacao: data['moedaFixacao'] = self.moedaFixacao
        if self.tipoContrato: data['tipoContrato'] = self.tipoContrato
        if self.condicaoPeso: data['condicaoPeso'] = self.condicaoPeso
        if self.dataPrevisaoEntrega: data['dataPrevisaoEntrega'] = self.dataPrevisaoEntrega
        if self.quantidadeEmbalagem is not None: data['quantidadeEmbalagem'] = self.quantidadeEmbalagem
        if self.quantidadePallet is not None: data['quantidadePallet'] = self.quantidadePallet
        if self.taxaFixacao is not None: data['taxaFixacao'] = self.taxaFixacao
        if self.taxaDolar is not None: data['taxaDolar'] = self.taxaDolar
        
        # Campos opcionais adicionais - SEMPRE incluídos (vazios ou não)
        data['descricaoQualidade'] = self.descricaoQualidade or ""
        data['referenciaCliente'] = self.referenciaCliente or ""
        data['condicaoPagamento'] = self.condicaoPagamento or ""
        data['armazemPreparo'] = self.armazemPreparo or ""
        data['produtoExportacao'] = self.produtoExportacao or ""
        data['descricaoDetalhada'] = self.descricaoDetalhada or ""
        data['codigoBanco'] = self.codigoBanco or ""
        data['agenciaBancaria'] = self.agenciaBancaria or ""
        data['digitoVerificadorAgencia'] = self.digitoVerificadorAgencia or ""
        data['contaCorrente'] = self.contaCorrente or ""
        data['digitoVerificadorContaCorrente'] = self.digitoVerificadorContaCorrente or ""
        data['periodoEmbarque'] = self.periodoEmbarque or ""
        data['responsavelDocumento'] = self.responsavelDocumento or ""
        data['embarcador'] = self.embarcador or ""
        data['tipoVenda'] = self.tipoVenda or ""
        data['incoterm'] = self.incoterm or ""
        data['certificador'] = self.certificador or ""
        data['contratoLiberado'] = self.contratoLiberado or ""
        data['referenciaCorretor'] = self.referenciaCorretor or ""
        data['armazemDestino'] = self.armazemDestino or ""
        data['vendedor'] = self.vendedor or ""
        data['variacaoPeso'] = self.variacaoPeso or ""
        data['totalCostDdp'] = self.totalCostDdp if self.totalCostDdp is not None else 0
        data['difCashAgainst'] = self.difCashAgainst if self.difCashAgainst is not None else 0
        data['alerta'] = self.alerta or ""
        data['notas'] = self.notas or ""
        data['pilhaPassada'] = self.pilhaPassada or ""
        data['sampleConditions'] = self.sampleConditions or ""
        data['spot'] = self.spot or ""
        data['bolsaFixacao'] = self.bolsaFixacao or ""
        data['codigoClienteFinal'] = self.codigoClienteFinal or ""
        data['lojaClienteFinal'] = self.lojaClienteFinal or ""
        data['nomeClienteFinal'] = self.nomeClienteFinal or ""
        data['diferencialClienteFinal'] = self.diferencialClienteFinal if self.diferencialClienteFinal is not None else 0
        
        # Arrays - serializa objetos Pydantic para dicts
        if self.fixacaoContrato:
            data['fixacaoContrato'] = [
                fix.dict(exclude_none=True) if hasattr(fix, 'dict') else fix
                for fix in self.fixacaoContrato
            ]
        
        if self.comissaoContrato:
            data['comissaoContrato'] = [
                com.dict(exclude_none=True) if hasattr(com, 'dict') else com
                for com in self.comissaoContrato
            ]
        
        return data

    def get_missing_fields(self) -> List[str]:
        """Retorna lista de campos obrigatórios que estão faltando (priorizados)"""
        missing = []
        
        # PRIORIDADE 1: Cliente (código+loja OU nome são obrigatórios)
        # Aceita "SEM_NOME" como sinal de que usuário disse que não tem nome
        tem_nome = self.nomeCliente and self.nomeCliente.upper() not in ["SEM_NOME", "SEM NOME", "NENHUM", "VAZIO", "N/A"]
        tem_codigo = bool(self.codigoCliente)
        tem_loja = bool(self.lojaCliente)
        
        # Se usuário disse "sem nome", DEVE informar código+loja
        if self.nomeCliente and self.nomeCliente.upper() in ["SEM_NOME", "SEM NOME", "NENHUM", "VAZIO", "N/A"]:
            if not tem_codigo:
                missing.append("1. Código do cliente (obrigatório pois você informou que não tem nome)")
            elif not tem_loja:
                missing.append("1. Loja do cliente (obrigatório pois você informou que não tem nome)")
        # Se não tem nem nome nem código
        elif not tem_codigo and not tem_nome:
            missing.append("1. Nome do cliente (a IA buscará automaticamente o código e loja)")
        elif tem_codigo and not tem_loja:
            missing.append("1. Loja do cliente (obrigatório quando informado o código)")
        
        # PRIORIDADE 2: Campos essenciais do contrato
        if not self.quantidadeKg:
            missing.append("2. Quantidade em KG")
        
        if not self.condicaoEntrega:
            missing.append("3. Condição de ENTREGA")
        
        if not self.mesEmbarque:
            missing.append("4. Mês de embarque (ex: 05/2026)")
        
        if not self.modalidadePagamento:
            missing.append("5. Modalidade de pagamento")
        
        # PRIORIDADE 3: Campos complementares
        if not self.codigoEmbalagem:
            missing.append("6. Embalagem")
        
        if not self.padraoQualidade:
            missing.append("7. Padrão de qualidade")
        
        if not self.moedaFixacao:
            missing.append("8. Moeda de fixação")
        
        if not self.tipoContrato:
            missing.append("9. Tipo de contrato")
        
        if not self.condicaoPeso:
            missing.append("10. Condição de PESO")
        
        if not self.quantidadeContainer:
            missing.append("11. Quantidade de containers")
        
        if not self.quantidadeEmbalagem:
            missing.append("12. Quantidade de embalagens")
        
        if not self.taxaDolar:
            missing.append("13. Taxa do dólar")
        
        if self.exigeEudr is None:
            missing.append("14. Exige EUDR? (S ou N)")
        
        if self.exigeOTA is None:
            missing.append("15. Exige OTA? (S ou N)")
        
        if self.amostraPreEmbarque is None:
            missing.append("16. Requer amostra pré-embarque? (S ou N)")
        
        # Validação de peneiras - pergunta todas juntas se nenhuma foi informada
        if self.peneira14 is None and self.peneira17 is None and self.peneiraGrinder is None:
            missing.append("17. Peneiras - informe S ou N para cada uma:\n   • Peneira 14\n   • Peneira 17\n   • Peneira Grinder")
        
        # PRIORIDADE 4: Campos condicionais
        # Data de entrega (se ENT)
        if self.condicaoEntrega == 'ENT' and not self.dataPrevisaoEntrega:
            missing.append("18. Data previsão de entrega (obrigatório para entregas)")
        
        # NOTA: Fixação e Comissão são tratados separadamente no fluxo da tool (ada_tools.py)
        # Fixação é perguntada DEPOIS de todos os campos acima
        # Comissão é perguntada DEPOIS da fixação
        
        return missing
