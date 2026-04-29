"""
Tools LangChain para criação de contratos via API ADA
"""
import json
import logging
import asyncio
import redis as sync_redis
from typing import Optional, Dict, Any
from langchain_core.tools import StructuredTool

from app.core.ada_api_client import ada_api_client
from app.core.config import settings
from app.models.contrato_ada import ContratoVendaExportacao, FixacaoContrato, ComissaoContrato
from app.utils.field_resolver import field_resolver

logger = logging.getLogger(__name__)

# Redis sync client (singleton) para persistir estado do contrato entre turnos
_redis_sync = None


def _get_redis_sync():
    """Retorna cliente Redis síncrono (singleton)"""
    global _redis_sync
    if _redis_sync is None:
        _redis_sync = sync_redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_sync


class ADATools:
    """Tools para interação com API ADA - session-aware com estado persistente"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._redis_key = f"contrato_pendente:{session_id}"

    def _load_pending_data(self) -> Dict[str, Any]:
        """Carrega dados do contrato pendente do Redis"""
        try:
            r = _get_redis_sync()
            data = r.get(self._redis_key)
            if data:
                loaded = json.loads(data)
                logger.info(f"[ADA STATE] Dados carregados do Redis: {list(loaded.keys())}")
                # Log detalhado de campos importantes
                if 'fixacao_contrato_json' in loaded:
                    logger.info(f"[ADA STATE]    fixacao_contrato_json (primeiros 100 chars): {str(loaded['fixacao_contrato_json'])[:100]}")
                if 'tipo_contrato' in loaded:
                    logger.info(f"[ADA STATE]    tipo_contrato: {loaded['tipo_contrato']}")
                if 'quantidade_embalagem' in loaded:
                    logger.info(f"[ADA STATE]    quantidade_embalagem: {loaded['quantidade_embalagem']}")
                return loaded
        except Exception as e:
            logger.warning(f"[ADA STATE] Erro ao carregar dados pendentes: {e}")
        return {}

    def _save_pending_data(self, data: Dict[str, Any]):
        """Salva dados do contrato pendente no Redis (TTL 1 hora)"""
        try:
            r = _get_redis_sync()
            # Log detalhado antes de salvar
            logger.info(f"[ADA STATE] Salvando dados no Redis: {list(data.keys())}")
            if 'fixacao_contrato_json' in data:
                logger.info(f"[ADA STATE]    fixacao_contrato_json (primeiros 100 chars): {str(data['fixacao_contrato_json'])[:100]}")
            if 'tipo_contrato' in data:
                logger.info(f"[ADA STATE]    tipo_contrato: {data['tipo_contrato']}")
            if 'quantidade_embalagem' in data:
                logger.info(f"[ADA STATE]    quantidade_embalagem: {data['quantidade_embalagem']}")
            r.setex(self._redis_key, 3600, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"[ADA STATE] Erro ao salvar dados pendentes: {e}")

    def _clear_pending_data(self):
        """Limpa dados do contrato pendente do Redis"""
        try:
            r = _get_redis_sync()
            r.delete(self._redis_key)
            logger.info("[ADA STATE] Dados pendentes limpos do Redis")
        except Exception as e:
            logger.warning(f"[ADA STATE] Erro ao limpar dados pendentes: {e}")
    
    def _formatar_resumo_contrato(self, json_data: Dict[str, Any]) -> str:
        """Formata dados do contrato de forma legível para o usuário"""
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
        # Exibe descrição da embalagem com código entre parênteses, ou só código se não tiver descrição
        codigo_emb = json_data.get('codigoEmbalagem', 'N/A')
        desc_emb = json_data.get('descricaoEmbalagem')
        if desc_emb:
            linhas.append(f"   • Embalagem: {desc_emb} ({codigo_emb})")
        else:
            linhas.append(f"   • Embalagem: {codigo_emb}")
        
        # Exibe descrição do padrão de qualidade com código entre parênteses, ou só código se não tiver descrição
        codigo_pq = json_data.get('padraoQualidade', 'N/A')
        desc_pq = json_data.get('descricaoPadraoQualidade')
        if desc_pq:
            linhas.append(f"   • Padrão Qualidade: {desc_pq} ({codigo_pq})")
        else:
            linhas.append(f"   • Padrão Qualidade: {codigo_pq}")
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
        
        # Exibe descrição da condição de entrega com código entre parênteses, ou só código se não tiver descrição
        codigo_ce = json_data.get('condicaoEntrega', 'N/A')
        desc_ce = json_data.get('descricaoCondicaoEntrega')
        if desc_ce:
            linhas.append(f"   • Condição Entrega: {desc_ce} ({codigo_ce})")
        else:
            linhas.append(f"   • Condição Entrega: {codigo_ce}")
        
        # Exibe descrição da condição de peso com código entre parênteses, ou só código se não tiver descrição
        codigo_cp = json_data.get('condicaoPeso', 'N/A')
        desc_cp = json_data.get('descricaoCondicaoPeso')
        if desc_cp:
            linhas.append(f"   • Condição Peso: {desc_cp} ({codigo_cp})")
        else:
            linhas.append(f"   • Condição Peso: {codigo_cp}")
        linhas.append(f"   • Mês Embarque: {json_data.get('mesEmbarque', 'N/A')}")
        if json_data.get('dataPrevisaoEntrega'):
            linhas.append(f"   • Previsão Entrega: {json_data.get('dataPrevisaoEntrega')}")
        linhas.append("")
        
        # Comercial
        linhas.append("💰 **COMERCIAL:**")
        # Exibe descrição do tipo de contrato com código entre parênteses, ou só código se não tiver descrição
        codigo_tc = json_data.get('tipoContrato', 'N/A')
        desc_tc = json_data.get('descricaoTipoContrato')
        if desc_tc:
            linhas.append(f"   • Tipo Contrato: {desc_tc} ({codigo_tc})")
        else:
            linhas.append(f"   • Tipo Contrato: {codigo_tc}")
        
        # Exibe descrição da modalidade de pagamento com código entre parênteses, ou só código se não tiver descrição
        codigo_mp = json_data.get('modalidadePagamento', 'N/A')
        desc_mp = json_data.get('descricaoModalidadePagamento')
        if desc_mp:
            linhas.append(f"   • Modalidade Pagamento: {desc_mp} ({codigo_mp})")
        else:
            linhas.append(f"   • Modalidade Pagamento: {codigo_mp}")
        
        # Exibe descrição da moeda de fixação com código entre parênteses, ou só código se não tiver descrição
        codigo_mf = json_data.get('moedaFixacao', 'N/A')
        desc_mf = json_data.get('descricaoMoedaFixacao')
        if desc_mf:
            linhas.append(f"   • Moeda Fixação: {desc_mf} ({codigo_mf})")
        else:
            linhas.append(f"   • Moeda Fixação: {codigo_mf}")
        
        linhas.append(f"   • Taxa Dólar: {json_data.get('taxaDolar', 0):.3f}")
        linhas.append("")
        
        # Requisitos
        linhas.append("📋 **REQUISITOS:**")
        linhas.append(f"   • EUDR: {'Sim' if json_data.get('exigeEudr') == 'S' else 'Não'}")
        linhas.append(f"   • OTA: {'Sim' if json_data.get('exigeOTA') == 'S' else 'Não'}")
        linhas.append(f"   • Amostra Pré-Embarque: {'Sim' if json_data.get('amostraPreEmbarque') == 'S' else 'Não'}")
        linhas.append("")
        
        # Fixação
        linhas.append("📊 **FIXAÇÃO:**")
        if json_data.get('fixacaoContrato') and len(json_data.get('fixacaoContrato', [])) > 0:
            for i, fix in enumerate(json_data.get('fixacaoContrato', []), 1):
                sacas = fix.get('sacasFixacao', 0)
                
                # Tipo de Preço com descrição
                tipo = fix.get('tipoPrecoFixacao', 'N/A')
                desc_tipo = fix.get('descricaoTipoPrecoFixacao')
                tipo_display = f"{desc_tipo} ({tipo})" if desc_tipo else tipo
                
                ref = fix.get('referenciaBolsaNy', fix.get('referenciaPrecoFixacao', 'N/A'))
                linhas.append(f"   [{i}] Sacas: {sacas} | Tipo: {tipo_display} | Referência: {ref}")
                
                if fix.get('tipoPrecoFixacao') == 'A':
                    # Fixador com descrição
                    fixador = fix.get('fixadorPreco', 'N/A')
                    desc_fixador = fix.get('descricaoFixadorPreco')
                    fixador_display = f"{desc_fixador} ({fixador})" if desc_fixador else fixador
                    
                    linhas.append(f"       Fixador: {fixador_display} | Mês/Ano: {fix.get('mesAnoFixacao', 'N/A')}")
                
                # Tipo Valor com descrição
                tipo_valor = fix.get('tipoValor', 'N/A')
                desc_tipo_valor = fix.get('descricaoTipoValor')
                tipo_valor_display = f"{desc_tipo_valor} ({tipo_valor})" if desc_tipo_valor else tipo_valor
                
                linhas.append(f"       Tipo Valor: {tipo_valor_display}")
        else:
            linhas.append("   ⚠️ NENHUMA FIXAÇÃO CADASTRADA")
        linhas.append("")
        
        # Comissão
        if json_data.get('comissaoContrato'):
            linhas.append("💵 **COMISSÃO:**")
            for i, com in enumerate(json_data.get('comissaoContrato', []), 1):
                codigo_agente = com.get('codigoAgenteExportacao', 'N/A')
                loja_agente = com.get('lojaAgenteExportacao', 'N/A')
                nome_agente = com.get('nomeAgenteExportacao', 'N/A')
                percentual = com.get('percentualComissao', 0)
                
                # Tipo de comissão com descrição
                tipo_comissao = com.get('tipoComissao', 'N/A')
                desc_tipo_comissao = com.get('descricaoTipoComissao')
                tipo_comissao_display = f"{desc_tipo_comissao} ({tipo_comissao})" if desc_tipo_comissao else tipo_comissao
                
                linhas.append(f"   [{i}] Código: {codigo_agente} | Loja: {loja_agente}")
                if nome_agente != 'N/A':
                    linhas.append(f"       Nome: {nome_agente}")
                linhas.append(f"       Percentual: {percentual}% | Tipo: {tipo_comissao_display}")
            linhas.append("")
        
        # Informações Adicionais (campos opcionais - só exibe se preenchidos)
        campos_adicionais = []
        
        # Qualidade e Descrições
        if json_data.get('descricaoQualidade'):
            campos_adicionais.append(f"   • Descrição Qualidade: {json_data.get('descricaoQualidade')}")
        if json_data.get('descricaoDetalhada'):
            campos_adicionais.append(f"   • Descrição Detalhada: {json_data.get('descricaoDetalhada')}")
        
        # Referências
        if json_data.get('referenciaCliente'):
            campos_adicionais.append(f"   • Referência Cliente: {json_data.get('referenciaCliente')}")
        if json_data.get('referenciaCorretor'):
            campos_adicionais.append(f"   • Referência Corretor: {json_data.get('referenciaCorretor')}")
        
        # Pagamento e Bancário
        if json_data.get('condicaoPagamento'):
            codigo_cp = json_data.get('condicaoPagamento')
            desc_cp = json_data.get('descricaoCondicaoPagamento')
            if desc_cp:
                campos_adicionais.append(f"   • Condição Pagamento: {desc_cp} ({codigo_cp})")
            else:
                campos_adicionais.append(f"   • Condição Pagamento: {codigo_cp}")
        if json_data.get('codigoBanco'):
            campos_adicionais.append(f"   • Banco: {json_data.get('codigoBanco')}")
        if json_data.get('agenciaBancaria'):
            agencia = json_data.get('agenciaBancaria')
            if json_data.get('digitoVerificadorAgencia'):
                agencia += f"-{json_data.get('digitoVerificadorAgencia')}"
            campos_adicionais.append(f"   • Agência: {agencia}")
        if json_data.get('contaCorrente'):
            conta = json_data.get('contaCorrente')
            if json_data.get('digitoVerificadorContaCorrente'):
                conta += f"-{json_data.get('digitoVerificadorContaCorrente')}"
            campos_adicionais.append(f"   • Conta Corrente: {conta}")
        
        # Logística Adicional
        if json_data.get('armazemPreparo'):
            codigo_ap = json_data.get('armazemPreparo')
            desc_ap = json_data.get('descricaoArmazemPreparo')
            if desc_ap:
                campos_adicionais.append(f"   • Armazém Preparo: {desc_ap} ({codigo_ap})")
            else:
                campos_adicionais.append(f"   • Armazém Preparo: {codigo_ap}")
        if json_data.get('armazemDestino'):
            codigo_ad = json_data.get('armazemDestino')
            desc_ad = json_data.get('descricaoArmazemDestino')
            if desc_ad:
                campos_adicionais.append(f"   • Armazém Destino: {desc_ad} ({codigo_ad})")
            else:
                campos_adicionais.append(f"   • Armazém Destino: {codigo_ad}")
        if json_data.get('periodoEmbarque'):
            campos_adicionais.append(f"   • Período Embarque: {json_data.get('periodoEmbarque')}")
        if json_data.get('incoterm'):
            codigo_inc = json_data.get('incoterm')
            desc_inc = json_data.get('descricaoIncoterm')
            if desc_inc:
                campos_adicionais.append(f"   • Incoterm: {desc_inc} ({codigo_inc})")
            else:
                campos_adicionais.append(f"   • Incoterm: {codigo_inc}")
        if json_data.get('embarcador'):
            codigo_emb = json_data.get('embarcador')
            desc_emb = json_data.get('descricaoEmbarcador')
            if desc_emb:
                campos_adicionais.append(f"   • Embarcador: {desc_emb} ({codigo_emb})")
            else:
                campos_adicionais.append(f"   • Embarcador: {codigo_emb}")
        
        # Produto e Exportação
        if json_data.get('produtoExportacao'):
            codigo_pe = json_data.get('produtoExportacao')
            desc_pe = json_data.get('descricaoProdutoExportacao')
            if desc_pe:
                campos_adicionais.append(f"   • Produto Exportação: {desc_pe} ({codigo_pe})")
            else:
                campos_adicionais.append(f"   • Produto Exportação: {codigo_pe}")
        if json_data.get('tipoVenda'):
            campos_adicionais.append(f"   • Tipo Venda: {json_data.get('tipoVenda')}")
        if json_data.get('certificador'):
            campos_adicionais.append(f"   • Certificador: {json_data.get('certificador')}")
        if json_data.get('sampleConditions'):
            campos_adicionais.append(f"   • Sample Conditions: {json_data.get('sampleConditions')}")
        if json_data.get('spot'):
            codigo_spot = json_data.get('spot')
            desc_spot = json_data.get('descricaoSpot')
            if desc_spot:
                campos_adicionais.append(f"   • Spot: {desc_spot} ({codigo_spot})")
            else:
                campos_adicionais.append(f"   • Spot: {codigo_spot}")
        if json_data.get('bolsaFixacao'):
            codigo_bf = json_data.get('bolsaFixacao')
            desc_bf = json_data.get('descricaoBolsaFixacao')
            if desc_bf:
                campos_adicionais.append(f"   • Bolsa Fixação: {desc_bf} ({codigo_bf})")
            else:
                campos_adicionais.append(f"   • Bolsa Fixação: {codigo_bf}")
        
        # Controle e Gestão
        if json_data.get('contratoLiberado'):
            campos_adicionais.append(f"   • Contrato Liberado: {'Sim' if json_data.get('contratoLiberado') == 'S' else 'Não'}")
        if json_data.get('pilhaPassada'):
            campos_adicionais.append(f"   • Pilha Passada: {'Sim' if json_data.get('pilhaPassada') == 'S' else 'Não'}")
        if json_data.get('responsavelDocumento'):
            codigo_rd = json_data.get('responsavelDocumento')
            desc_rd = json_data.get('descricaoResponsavelDocumento')
            if desc_rd:
                campos_adicionais.append(f"   • Responsável Documento: {desc_rd} ({codigo_rd})")
            else:
                campos_adicionais.append(f"   • Responsável Documento: {codigo_rd}")
        if json_data.get('vendedor'):
            codigo_vend = json_data.get('vendedor')
            desc_vend = json_data.get('descricaoVendedor')
            if desc_vend:
                campos_adicionais.append(f"   • Vendedor: {desc_vend} ({codigo_vend})")
            else:
                campos_adicionais.append(f"   • Vendedor: {codigo_vend}")
        if json_data.get('variacaoPeso'):
            campos_adicionais.append(f"   • Variação Peso: {json_data.get('variacaoPeso')}")
        
        # Valores e Diferenciais
        if json_data.get('totalCostDdp') and json_data.get('totalCostDdp') != 0:
            campos_adicionais.append(f"   • Total Cost DDP: {json_data.get('totalCostDdp'):.2f}")
        if json_data.get('difCashAgainst') and json_data.get('difCashAgainst') != 0:
            campos_adicionais.append(f"   • Dif Cash Against: {json_data.get('difCashAgainst'):.2f}")
        if json_data.get('diferencialClienteFinal') and json_data.get('diferencialClienteFinal') != 0:
            campos_adicionais.append(f"   • Diferencial Cliente Final: {json_data.get('diferencialClienteFinal'):.2f}")
        
        # Cliente Final
        if json_data.get('codigoClienteFinal'):
            campos_adicionais.append(f"   • Cliente Final: {json_data.get('codigoClienteFinal')}")
            if json_data.get('lojaClienteFinal'):
                campos_adicionais.append(f"     Loja: {json_data.get('lojaClienteFinal')}")
            if json_data.get('nomeClienteFinal'):
                campos_adicionais.append(f"     Nome: {json_data.get('nomeClienteFinal')}")
        
        # Observações (sempre por último)
        if json_data.get('alerta'):
            campos_adicionais.append(f"   • ⚠️ Alerta: {json_data.get('alerta')}")
        if json_data.get('notas'):
            campos_adicionais.append(f"   • 📝 Notas: {json_data.get('notas')}")
        
        # Adiciona seção apenas se houver campos preenchidos
        if campos_adicionais:
            linhas.append("📝 **INFORMAÇÕES ADICIONAIS:**")
            linhas.extend(campos_adicionais)
            linhas.append("")
        
        linhas.append("="* 70)
        
        return "\n".join(linhas)

    def criar_contrato_venda(
        self,
        # Confirmação
        confirmar_envio: Optional[bool] = None,  # True = usuário confirmou envio para API
        
        # Cliente
        codigo_cliente: Optional[str] = None,
        loja_cliente: Optional[str] = None,
        nome_cliente: Optional[str] = None,
        
        # Detalhes do contrato
        codigo_embalagem: Optional[str] = None,
        quantidade_kg: Optional[float] = None,
        padrao_qualidade: Optional[str] = None,
        modalidade_pagamento: Optional[str] = None,
        quantidade_container: Optional[int] = None,
        mes_embarque: Optional[str] = None,
        exige_eudr: Optional[str] = None,
        exige_ota: Optional[str] = None,
        amostra_pre_embarque: Optional[str] = None,
        condicao_entrega: Optional[str] = None,
        moeda_fixacao: Optional[str] = None,
        tipo_contrato: Optional[str] = None,
        condicao_peso: Optional[str] = None,
        data_previsao_entrega: Optional[str] = None,
        quantidade_embalagem: Optional[int] = None,
        quantidade_pallet: Optional[int] = None,
        peneira_14: Optional[bool] = None,
        peneira_17: Optional[bool] = None,
        peneira_grinder: Optional[bool] = None,
        taxa_dolar: Optional[float] = None,
        sem_comissao: Optional[bool] = None,  # Flag para indicar "não quero comissão"
        
        # Campos opcionais adicionais
        descricao_qualidade: Optional[str] = None,
        referencia_cliente: Optional[str] = None,
        condicao_pagamento: Optional[str] = None,
        armazem_preparo: Optional[str] = None,
        produto_exportacao: Optional[str] = None,
        descricao_detalhada: Optional[str] = None,
        codigo_banco: Optional[str] = None,
        agencia_bancaria: Optional[str] = None,
        digito_verificador_agencia: Optional[str] = None,
        conta_corrente: Optional[str] = None,
        digito_verificador_conta_corrente: Optional[str] = None,
        periodo_embarque: Optional[str] = None,
        responsavel_documento: Optional[str] = None,
        embarcador: Optional[str] = None,
        tipo_venda: Optional[str] = None,
        incoterm: Optional[str] = None,
        certificador: Optional[str] = None,
        contrato_liberado: Optional[str] = None,
        referencia_corretor: Optional[str] = None,
        armazem_destino: Optional[str] = None,
        vendedor: Optional[str] = None,
        variacao_peso: Optional[str] = None,
        total_cost_ddp: Optional[float] = None,
        dif_cash_against: Optional[float] = None,
        alerta: Optional[str] = None,
        notas: Optional[str] = None,
        pilha_passada: Optional[str] = None,
        sample_conditions: Optional[str] = None,
        spot: Optional[str] = None,
        bolsa_fixacao: Optional[str] = None,
        codigo_cliente_final: Optional[str] = None,
        loja_cliente_final: Optional[str] = None,
        nome_cliente_final: Optional[str] = None,
        diferencial_cliente_final: Optional[float] = None,
        
        # Arrays (JSON strings)
        fixacao_contrato_json: Optional[str] = None,
        comissao_contrato_json: Optional[str] = None,
        
        # Remoção de itens de arrays (índice começa em 1 para o usuário)
        remover_fixacao_indice: Optional[int] = None,
        remover_comissao_indice: Optional[int] = None,
        
        # Alteração de item específico de array (índice começa em 1 para o usuário)
        alterar_fixacao_indice: Optional[int] = None,
        alterar_comissao_indice: Optional[int] = None
    ) -> str:
        """Cria contrato de venda/exportação. Acumula dados em Redis - passe apenas dados NOVOS.
        
        REGRAS DE USO DA TOOL:
        
        1. ADICIONAR/ALTERAR CAMPOS (chame COM parâmetros específicos):
           Se usuário menciona adicionar, incluir, alterar, mudar campos:
           - "quero adicionar pilha passada como não" → pilha_passada="N"
           - "adicione notas: urgente" → notas="urgente"
           - "inclua incoterm FOB" → incoterm="FOB"
           - "altere taxa dolar para 5.5" → taxa_dolar=5.5
           - SEMPRE passe o parâmetro do campo mencionado!
        
        2. CONFIRMAR ENVIO (chame SEM parâmetros):
           SOMENTE se usuário usar palavras de confirmação PURAS, sem verbos de ação:
           - "sim" (sozinho)
           - "ok"
           - "confirmar"
           - "pode enviar"
           - NÃO confunda com "adicionar...como sim" - nesse caso "sim" é VALOR!
        
        3. PRIORIDADE: SEMPRE verifique PRIMEIRO se é adição/alteração antes de confirmar!
        """
        try:
            logger.info("[ADA TOOL] Iniciando criação de contrato...")
            
            # 1. Carrega dados já coletados anteriormente do Redis
            pending = self._load_pending_data()
            
            # 2. Detecção IMEDIATA de confirmação via parâmetro explícito
            if confirmar_envio is True:
                logger.info("[ADA TOOL] ✅ Confirmação EXPLÍCITA recebida via parâmetro confirmar_envio=True")
                # Força confirmação - ignora qualquer outro campo que possa ter sido passado
                esta_confirmando_explicito = True
                current = {}  # Limpa - não processa outros campos quando confirmando
            else:
                esta_confirmando_explicito = False
                # Constrói dict com dados da chamada atual (somente não-None)
                current = {}
                param_map = {
                    "codigo_cliente": codigo_cliente,
                    "loja_cliente": loja_cliente,
                    "nome_cliente": nome_cliente,
                    "codigo_embalagem": codigo_embalagem,
                    "quantidade_kg": quantidade_kg,
                    "padrao_qualidade": padrao_qualidade,
                    "modalidade_pagamento": modalidade_pagamento,
                    "quantidade_container": quantidade_container,
                    "mes_embarque": mes_embarque,
                    "exige_eudr": exige_eudr,
                    "exige_ota": exige_ota,
                    "amostra_pre_embarque": amostra_pre_embarque,
                    "condicao_entrega": condicao_entrega,
                    "moeda_fixacao": moeda_fixacao,
                    "tipo_contrato": tipo_contrato,
                    "condicao_peso": condicao_peso,
                    "data_previsao_entrega": data_previsao_entrega,
                    "quantidade_embalagem": quantidade_embalagem,
                    "quantidade_pallet": quantidade_pallet,
                    "peneira_14": peneira_14,
                    "peneira_17": peneira_17,
                    "peneira_grinder": peneira_grinder,
                    "taxa_dolar": taxa_dolar,
                    "sem_comissao": sem_comissao,
                    "fixacao_contrato_json": fixacao_contrato_json,
                    "comissao_contrato_json": comissao_contrato_json,
                    # Campos opcionais adicionais (37 campos)
                    "descricao_qualidade": descricao_qualidade,
                    "referencia_cliente": referencia_cliente,
                    "condicao_pagamento": condicao_pagamento,
                    "armazem_preparo": armazem_preparo,
                    "produto_exportacao": produto_exportacao,
                    "descricao_detalhada": descricao_detalhada,
                    "codigo_banco": codigo_banco,
                    "agencia_bancaria": agencia_bancaria,
                    "digito_verificador_agencia": digito_verificador_agencia,
                    "conta_corrente": conta_corrente,
                    "digito_verificador_conta_corrente": digito_verificador_conta_corrente,
                    "periodo_embarque": periodo_embarque,
                    "responsavel_documento": responsavel_documento,
                    "embarcador": embarcador,
                    "tipo_venda": tipo_venda,
                    "incoterm": incoterm,
                    "certificador": certificador,
                    "contrato_liberado": contrato_liberado,
                    "referencia_corretor": referencia_corretor,
                    "armazem_destino": armazem_destino,
                    "vendedor": vendedor,
                    "variacao_peso": variacao_peso,
                    "total_cost_ddp": total_cost_ddp,
                    "dif_cash_against": dif_cash_against,
                    "alerta": alerta,
                    "notas": notas,
                    "pilha_passada": pilha_passada,
                    "sample_conditions": sample_conditions,
                    "spot": spot,
                    "bolsa_fixacao": bolsa_fixacao,
                    "codigo_cliente_final": codigo_cliente_final,
                    "loja_cliente_final": loja_cliente_final,
                    "nome_cliente_final": nome_cliente_final,
                    "diferencial_cliente_final": diferencial_cliente_final,
                    # Remoção
                    "remover_fixacao_indice": remover_fixacao_indice,
                    "remover_comissao_indice": remover_comissao_indice,
                    # Alteração
                    "alterar_fixacao_indice": alterar_fixacao_indice,
                    "alterar_comissao_indice": alterar_comissao_indice,
                }
                for key, val in param_map.items():
                    if val is not None:
                        current[key] = val
            
            # 2.5. RESOLUÇÃO DE CAMPOS - converte descrições em códigos via API F3
            # Isso acontece ANTES de qualquer validação ou merge
            if current and not esta_confirmando_explicito:
                logger.info("[ADA TOOL] 🔍 Iniciando resolução de campos (conversão descrição → código)...")
                
                # CASO ESPECIAL: Se usuário informou nome_cliente, buscar código automaticamente
                if "nome_cliente" in current and not current.get("codigo_cliente"):
                    nome_informado = current["nome_cliente"]
                    logger.info(f"[ADA TOOL] 🔍 Nome do cliente informado: '{nome_informado}' - buscando código...")
                    
                    try:
                        # Busca usando o resolver com threshold mais baixo para nomes (aceita 60% de similaridade)
                        try:
                            loop = asyncio.get_running_loop()
                            import nest_asyncio
                            nest_asyncio.apply()
                            codigo_resolvido, descricao_api, loja_resolvida = asyncio.run(field_resolver.resolve_field("codigo_cliente", nome_informado, threshold=60))
                        except RuntimeError:
                            codigo_resolvido, descricao_api, loja_resolvida = asyncio.run(field_resolver.resolve_field("codigo_cliente", nome_informado, threshold=60))
                        
                        if codigo_resolvido and codigo_resolvido != nome_informado:
                            logger.info(f"[ADA TOOL] ✅ Cliente encontrado na API!")
                            logger.info(f"[ADA TOOL]    Código: {codigo_resolvido}")
                            logger.info(f"[ADA TOOL]    Descrição: {descricao_api}")
                            logger.info(f"[ADA TOOL]    Loja: {loja_resolvida}")
                            
                            # Preenche automaticamente código e loja
                            current["codigo_cliente"] = codigo_resolvido
                            if loja_resolvida:
                                current["loja_cliente"] = loja_resolvida
                            # Atualiza o nome com a descrição retornada pela API (mais precisa)
                            if descricao_api:
                                current["nome_cliente"] = descricao_api
                        else:
                            logger.warning(f"[ADA TOOL] ⚠️ Cliente '{nome_informado}' não encontrado na API")
                            logger.warning(f"[ADA TOOL] ℹ️ Usuário precisará informar código e loja manualmente")
                    except Exception as e:
                        logger.warning(f"[ADA TOOL] ⚠️ Erro ao buscar cliente: {e}")
                        logger.warning(f"[ADA TOOL] ℹ️ Continuando com nome informado pelo usuário")
                
                # Campos que podem precisar de resolução
                campos_para_resolver = [
                    "codigo_embalagem",
                    "codigo_cliente", 
                    "padrao_qualidade",
                    "modalidade_pagamento",
                    "condicao_entrega",
                    "moeda_fixacao",
                    "tipo_contrato",
                    "condicao_peso",
                    "condicao_pagamento",
                    # Campos opcionais adicionais
                    "armazem_preparo",
                    "produto_exportacao",
                    "responsavel_documento",
                    "embarcador",
                    "incoterm",
                    "armazem_destino",
                    "vendedor",
                    "spot",
                    "bolsa_fixacao"
                ]
                
                # Campos de comissão que precisam resolução especial
                campos_comissao_para_resolver = [
                    "codigo_agente_exportacao"
                ]
                
                # Resolve cada campo (se presente no current)
                for campo in campos_para_resolver:
                    if campo in current:
                        valor_original = current[campo]
                        logger.info(f"[ADA TOOL] 🔍 Verificando campo '{campo}' com valor: '{valor_original}'")
                        
                        try:
                            # Define threshold baseado no campo (alguns precisam de threshold mais baixo)
                            threshold = 60 if campo in ["padrao_qualidade", "codigo_cliente", "modalidade_pagamento", "moeda_fixacao", 
                                                       "condicao_entrega", "condicao_peso", "tipo_contrato", "condicao_pagamento",
                                                       "armazem_preparo", "produto_exportacao", "responsavel_documento", 
                                                       "embarcador", "incoterm", "armazem_destino", "vendedor", "spot", "bolsa_fixacao"] else 70
                            
                            logger.info(f"[ADA TOOL] 🔍 Chamando resolver para '{campo}' (threshold={threshold}%)...")
                            
                            # Chama resolver de forma síncrona (cria event loop se necessário)
                            try:
                                loop = asyncio.get_running_loop()
                                import nest_asyncio
                                nest_asyncio.apply()
                                valor_resolvido, descricao, loja = asyncio.run(field_resolver.resolve_field(campo, str(valor_original), threshold=threshold))
                            except RuntimeError:
                                valor_resolvido, descricao, loja = asyncio.run(field_resolver.resolve_field(campo, str(valor_original), threshold=threshold))
                            
                            logger.info(f"[ADA TOOL] 🔍 Resolver retornou: valor='{valor_resolvido}', descricao='{descricao}', loja='{loja}'")
                            
                            # Atualiza o código se foi resolvido
                            if valor_resolvido and valor_resolvido != valor_original:
                                logger.info(f"[ADA TOOL] ✅ Campo '{campo}' resolvido: '{valor_original}' → '{valor_resolvido}'")
                                current[campo] = valor_resolvido
                            elif valor_resolvido == valor_original:
                                logger.info(f"[ADA TOOL] ℹ️ Campo '{campo}' mantido: '{valor_original}' (já é código correto)")
                            
                            # Armazena descrições INDEPENDENTEMENTE de o código ter mudado
                            if campo == "codigo_embalagem" and descricao:
                                current["descricao_embalagem"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da embalagem armazenada: '{descricao}'")
                            
                            if campo == "padrao_qualidade" and descricao:
                                current["descricao_padrao_qualidade"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do padrão de qualidade armazenada: '{descricao}'")
                            
                            if campo == "modalidade_pagamento" and descricao:
                                current["descricao_modalidade_pagamento"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da modalidade de pagamento armazenada: '{descricao}'")
                            
                            if campo == "condicao_entrega" and descricao:
                                current["descricao_condicao_entrega"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da condição de entrega armazenada: '{descricao}'")
                            
                            if campo == "moeda_fixacao" and descricao:
                                current["descricao_moeda_fixacao"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da moeda de fixação armazenada: '{descricao}'")
                            
                            if campo == "tipo_contrato" and descricao:
                                current["descricao_tipo_contrato"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do tipo de contrato armazenada: '{descricao}'")
                            
                            if campo == "condicao_peso" and descricao:
                                current["descricao_condicao_peso"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da condição de peso armazenada: '{descricao}'")
                            
                            if campo == "condicao_pagamento" and descricao:
                                current["descricao_condicao_pagamento"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da condição de pagamento armazenada: '{descricao}'")
                            
                            if campo == "armazem_preparo" and descricao:
                                current["descricao_armazem_preparo"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do armazém preparo armazenada: '{descricao}'")
                            
                            if campo == "produto_exportacao" and descricao:
                                current["descricao_produto_exportacao"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do produto exportação armazenada: '{descricao}'")
                            
                            if campo == "responsavel_documento" and descricao:
                                current["descricao_responsavel_documento"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do responsável documento armazenada: '{descricao}'")
                            
                            if campo == "embarcador" and descricao:
                                current["descricao_embarcador"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do embarcador armazenada: '{descricao}'")
                            
                            if campo == "incoterm" and descricao:
                                current["descricao_incoterm"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do incoterm armazenada: '{descricao}'")
                            
                            if campo == "armazem_destino" and descricao:
                                current["descricao_armazem_destino"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do armazém destino armazenada: '{descricao}'")
                            
                            if campo == "vendedor" and descricao:
                                current["descricao_vendedor"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do vendedor armazenada: '{descricao}'")
                            
                            if campo == "spot" and descricao:
                                current["descricao_spot"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição do spot armazenada: '{descricao}'")
                            
                            if campo == "bolsa_fixacao" and descricao:
                                current["descricao_bolsa_fixacao"] = descricao
                                logger.info(f"[ADA TOOL] ✅ Descrição da bolsa de fixação armazenada: '{descricao}'")
                            
                            if campo == "codigo_cliente":
                                if descricao:
                                    # ⚠️ CORREÇÃO: Verifica nome em MERGED (não current) porque pode estar no pending
                                    nome_atual = merged.get("nome_cliente")
                                    # SEMPRE sobrescreve com o nome da API quando resolver código
                                    # (o nome digitado pelo usuário pode estar errado, mas o código é a fonte da verdade)
                                    current["nome_cliente"] = descricao
                                    logger.info(f"[ADA TOOL] ✅ Nome do cliente atualizado da API: '{descricao}' (anterior: '{nome_atual}')")
                                if loja:
                                    current["loja_cliente"] = loja
                                    logger.info(f"[ADA TOOL] ✅ Loja do cliente armazenada: '{loja}'")
                            
                            # Log de avisos apenas se realmente não resolveu
                            if not valor_resolvido:
                                logger.warning(f"[ADA TOOL] ⚠️ Campo '{campo}': '{valor_original}' não resolvido (threshold={threshold}%) - mantendo valor original")
                        except Exception as e:
                            logger.warning(f"[ADA TOOL] ⚠️ Erro ao resolver campo '{campo}': {e}")
                            # Em caso de erro, mantém valor original
                            logger.warning(f"[ADA TOOL] Mantendo valor original: '{valor_original}'")
            
            # DETECÇÃO DE CONFIRMAÇÃO - antes de qualquer merge ou processamento
            # Detecta se os "novos campos" são apenas variações de "SIM" (confirmação)
            palavras_confirmacao = ['sim', 's', 'yes', 'y', 'ok', 'confirmar', 'confirmo', 'enviar', 'envie', 'envia', 
                                   'pode enviar', 'quero enviar', 'pode mandar', 'quero mandar', 'manda', 'mande',
                                   'correto', 'certo', 'está certo', 'tá certo', 'perfeito', 'beleza', 'blz',
                                   'tudo certo', 'tudo ok', 'pode ir', 'vai', 'vamo', 'vamos']
            palavras_alteracao = ['mude', 'muda', 'mudar', 'altere', 'altera', 'alterar', 'corrija', 'corrige', 'corrigir', 
                                 'troque', 'troca', 'trocar', 'ajuste', 'ajusta', 'ajustar', 'modifique', 'modifica', 'modificar',
                                 'adicione', 'adiciona', 'adicionar', 'inclua', 'inclui', 'incluir', 
                                 'insira', 'insere', 'inserir', 'coloque', 'coloca', 'colocar', 'ponha', 'põe', 'pôr']
            eh_so_confirmacao = False
            contem_palavra_alteracao = False  # Inicializa aqui, pode ser modificada abaixo
            
            # PROTEÇÃO 0 (CRÍTICA): Se está adicionando campos NOVOS que não existiam antes, NUNCA é confirmação
            # Isso pega casos como "Adicione pilha_passada como Sim" onde "Sim" poderia ser confundido com confirmação
            campos_novos = set(current.keys()) - set(pending.keys())
            # Exclui campos que podem aparecer naturalmente durante alteração/confirmação
            campos_especiais = {'confirmar_envio', 'fixacao_contrato_json', 'comissao_contrato_json'}
            campos_novos_reais = campos_novos - campos_especiais
            
            if campos_novos_reais:
                logger.info(f"[ADA TOOL] 🆕 Detectados CAMPOS NOVOS sendo adicionados: {campos_novos_reais}")
                logger.info(f"[ADA TOOL] 🚫 Campos novos = SEMPRE alteração, NUNCA confirmação")
                eh_so_confirmacao = False
                contem_palavra_alteracao = True  # Força detecção como alteração
            
            # Junta todos os valores dos campos em um único texto
            texto_campos = " ".join(str(v).lower() for v in current.values() if v is not None).strip()
            
            # PROTEÇÃO 1: Verifica se há palavras de alteração nos valores
            if not contem_palavra_alteracao:  # Só verifica se não foi detectado na PROTEÇÃO 0
                contem_palavra_alteracao = any(palavra in texto_campos for palavra in palavras_alteracao)
            
            # PROTEÇÃO 2: Verifica se contém palavras de confirmação
            contem_palavra_confirmacao = any(palavra in texto_campos for palavra in palavras_confirmacao)
            
            # PROTEÇÃO 3: Verifica se tem números/códigos (indica dados reais, não confirmação)
            # Ignora números pequenos (0-9) que podem estar em frases
            import re
            tem_dados_reais = bool(re.search(r'\d{2,}', texto_campos))  # 2+ dígitos seguidos
            
            if contem_palavra_alteracao:
                logger.info(f"[ADA TOOL] 🚫 Detectado pedido de alteração - NÃO é confirmação")
                eh_so_confirmacao = False
            elif contem_palavra_confirmacao and not tem_dados_reais:
                # Contém palavra de confirmação E não tem dados reais (números/códigos)
                logger.info(f"[ADA TOOL] ✅ Detectado confirmação explícita: '{texto_campos}'")
                eh_so_confirmacao = True
                # Limpa completamente current - são apenas confirmações, não dados reais
                current.clear()
            elif current and not tem_dados_reais:
                # Não tem palavras específicas mas também não tem dados reais
                # Verifica se TODOS os valores são palavras simples de confirmação
                valores_validos = [str(v).strip().lower() for v in current.values() if v is not None and str(v).strip()]
                if valores_validos and all(len(v.split()) <= 3 and not re.search(r'[0-9]', v) for v in valores_validos):
                    # Todos os valores são frases curtas (até 3 palavras) e sem números
                    # Provável confirmação
                    logger.info(f"[ADA TOOL] ✅ Detectado provável confirmação (frases curtas sem dados): {valores_validos}")
                    eh_so_confirmacao = True
                    current.clear()
            
            # Normaliza valores comuns de entrada (antes de merge)
            if 'exige_eudr' in current:
                val = str(current['exige_eudr']).strip().upper()
                if val in ['SIM', 'S', 'YES', 'Y', '1', 'TRUE']:
                    current['exige_eudr'] = 'S'
                elif val in ['NAO', 'NÃO', 'N', 'NO', '0', 'FALSE']:
                    current['exige_eudr'] = 'N'
            
            if 'exige_ota' in current:
                val = str(current['exige_ota']).strip().upper()
                if val in ['SIM', 'S', 'YES', 'Y', '1', 'TRUE']:
                    current['exige_ota'] = 'S'
                elif val in ['NAO', 'NÃO', 'N', 'NO', '0', 'FALSE']:
                    current['exige_ota'] = 'N'
            
            if 'amostra_pre_embarque' in current:
                val = str(current['amostra_pre_embarque']).strip().upper()
                if val in ['SIM', 'S', 'YES', 'Y', '1', 'TRUE']:
                    current['amostra_pre_embarque'] = 'S'
                elif val in ['NAO', 'NÃO', 'N', 'NO', '0', 'FALSE']:
                    current['amostra_pre_embarque'] = 'N'
            
            # Normaliza campos opcionais S/N
            if 'contrato_liberado' in current:
                val = str(current['contrato_liberado']).strip().upper()
                if val in ['SIM', 'S', 'YES', 'Y', '1', 'TRUE']:
                    current['contrato_liberado'] = 'S'
                elif val in ['NAO', 'NÃO', 'N', 'NO', '0', 'FALSE']:
                    current['contrato_liberado'] = 'N'
            
            if 'pilha_passada' in current:
                val = str(current['pilha_passada']).strip().upper()
                if val in ['SIM', 'S', 'YES', 'Y', '1', 'TRUE']:
                    current['pilha_passada'] = 'S'
                elif val in ['NAO', 'NÃO', 'N', 'NO', '0', 'FALSE']:
                    current['pilha_passada'] = 'N'
            
            # Normaliza peneiras
            for peneira_key in ['peneira_14', 'peneira_17', 'peneira_grinder']:
                if peneira_key in current:
                    val = str(current[peneira_key]).strip().upper()
                    if val in ['SIM', 'S', 'YES', 'Y', '1', 'TRUE', 'TEM', 'POSSUI']:
                        current[peneira_key] = True
                    elif val in ['NAO', 'NÃO', 'N', 'NO', '0', 'FALSE', 'NAO TEM', 'NÃO TEM']:
                        current[peneira_key] = False
            
            # Log detalhado do que foi recebido
            if current:
                logger.info(f"[ADA TOOL] 🔵 Parâmetros recebidos nesta chamada:")
                for k, v in current.items():
                    logger.info(f"[ADA TOOL]    {k} = {v}")
            
            # 3. FILTROS DE SANIDADE: detecta quando LLM confunde campos da fixação com campos do contrato
            bloqueios = []
            if pending.get('aguardando_confirmacao') and current:
                logger.info(f"[ADA TOOL] 🛡️ Aplicando filtros de sanidade para alterações...")
                
                # Tipo de contrato não pode ser "A" ou "F" (são valores de tipoPrecoFixacao)
                if current.get('tipo_contrato') in ['A', 'F']:
                    logger.warning(f"[ADA TOOL] ⚠️ BLOQUEADO tipo_contrato='{current['tipo_contrato']}' (confusão com tipoPrecoFixacao)")
                    logger.warning(f"[ADA TOOL] 💡 DICA: Para alterar o tipo de preço da fixação, use fixacao_contrato_json!")
                    bloqueios.append(f"tipo_contrato='{current['tipo_contrato']}' bloqueado (provável confusão com tipoPrecoFixacao da fixação)")
                    current.pop('tipo_contrato', None)
                
                # Se quantidade_embalagem coincide exatamente com sacasFixacao do pending, pode ser confusão
                if 'fixacao_contrato_json' in pending:
                    try:
                        fix_json = pending['fixacao_contrato_json']
                        if isinstance(fix_json, str):
                            fix_data = json.loads(fix_json)
                            if isinstance(fix_data, list) and len(fix_data) > 0:
                                sacas_fixacao = fix_data[0].get('sacasFixacao') or fix_data[0].get('sacas')
                                if current.get('quantidade_embalagem') == sacas_fixacao:
                                    logger.warning(f"[ADA TOOL] ⚠️ BLOQUEADO quantidade_embalagem={current['quantidade_embalagem']} (confusão com sacasFixacao)")
                                    logger.warning(f"[ADA TOOL] 💡 DICA: Para alterar sacas da fixação, use fixacao_contrato_json!")
                                    bloqueios.append(f"quantidade_embalagem={current['quantidade_embalagem']} bloqueado (provável confusão com sacasFixacao da fixação)")
                                    current.pop('quantidade_embalagem', None)
                    except:
                        pass
            
            # Se houve bloqueios durante alteração, retorna erro explicativo
            if bloqueios and pending.get('aguardando_confirmacao'):
                msg_erro = "ERRO_ALTERACAO: Detectei alterações em campos incorretos. Parece que você está tentando alterar dados de FIXAÇÃO, mas passou campos do CONTRATO.\n\n"
                msg_erro += "BLOQUEIOS:\n" + "\n".join(f"  • {b}" for b in bloqueios)
                msg_erro += "\n\n💡 COMO CORRIGIR:\n"
                msg_erro += "Para alterar dados de FIXAÇÃO (sacas, tipo de preço, referência), você precisa chamar a tool com:\n"
                msg_erro += "fixacao_contrato_json='[{\"sacas\": 300, \"tipo_preco\": \"A\", \"referencia\": 400, \"tipo_valor\": \"C\"}]'\n\n"
                msg_erro += "Pergunte ao usuário EXATAMENTE quais dados de fixação ele quer (sacas, tipo de preço, referência, etc) e monte o JSON."
                logger.warning(f"[ADA TOOL] ❌ Retornando erro de alteração com instruções: {msg_erro}")
                return msg_erro
            
            # 4. Merge: dados novos sobrescrevem dados antigos (após filtros)
            
            # 🗑️ REMOÇÃO DE FIXAÇÃO (processado ANTES de adição/alteração)
            if current.get('remover_fixacao_indice') and pending.get('fixacao_contrato_json'):
                try:
                    indice = int(current['remover_fixacao_indice']) - 1  # Usuário conta de 1, array de 0
                    old_fix = pending['fixacao_contrato_json']
                    old_data = old_fix if isinstance(old_fix, list) else json.loads(old_fix) if isinstance(old_fix, str) else old_fix
                    if isinstance(old_data, dict): old_data = [old_data]
                    
                    if isinstance(old_data, list) and 0 <= indice < len(old_data):
                        logger.info(f"[ADA TOOL] 🗑️ Removendo fixação no índice {indice + 1} (posição {indice})")
                        old_data.pop(indice)
                        # Atualiza pending diretamente para que o merge use o array já modificado
                        pending['fixacao_contrato_json'] = json.dumps(old_data, ensure_ascii=False) if old_data else None
                        # Remove o current pra não tentar merge depois
                        if 'fixacao_contrato_json' in current:
                            del current['fixacao_contrato_json']
                        logger.info(f"[ADA TOOL] ✅ Fixação removida. Total restante: {len(old_data)}")
                    else:
                        logger.warning(f"[ADA TOOL] ⚠️ Índice {indice + 1} inválido para fixação (total: {len(old_data) if isinstance(old_data, list) else 0})")
                except Exception as e:
                    logger.warning(f"[ADA TOOL] ⚠️ Erro ao remover fixação: {e}")
            
            # 🗑️ REMOÇÃO DE COMISSÃO (processado ANTES de adição/alteração)
            if current.get('remover_comissao_indice') and pending.get('comissao_contrato_json'):
                try:
                    indice = int(current['remover_comissao_indice']) - 1  # Usuário conta de 1, array de 0
                    old_com = pending['comissao_contrato_json']
                    old_data = old_com if isinstance(old_com, list) else json.loads(old_com) if isinstance(old_com, str) else old_com
                    if isinstance(old_data, dict): old_data = [old_data]
                    
                    if isinstance(old_data, list) and 0 <= indice < len(old_data):
                        logger.info(f"[ADA TOOL] 🗑️ Removendo comissão no índice {indice + 1} (posição {indice})")
                        old_data.pop(indice)
                        # Atualiza pending diretamente para que o merge use o array já modificado
                        pending['comissao_contrato_json'] = json.dumps(old_data, ensure_ascii=False) if old_data else None
                        # Remove o current pra não tentar merge depois
                        if 'comissao_contrato_json' in current:
                            del current['comissao_contrato_json']
                        logger.info(f"[ADA TOOL] ✅ Comissão removida. Total restante: {len(old_data)}")
                    else:
                        logger.warning(f"[ADA TOOL] ⚠️ Índice {indice + 1} inválido para comissão (total: {len(old_data) if isinstance(old_data, list) else 0})")
                except Exception as e:
                    logger.warning(f"[ADA TOOL] ⚠️ Erro ao remover comissão: {e}")
            
            # MERGE ESPECIAL para fixação: se já existe fixação no pending e veio nova fixação,
            # decide se é ADIÇÃO (append) ou ALTERAÇÃO (merge) baseado no contexto
            if current.get('fixacao_contrato_json') and pending.get('fixacao_contrato_json'):
                try:
                    old_fix = pending['fixacao_contrato_json']
                    new_fix = current['fixacao_contrato_json']
                    # Parse ambos
                    old_data = old_fix if isinstance(old_fix, list) else json.loads(old_fix) if isinstance(old_fix, str) else old_fix
                    new_data = new_fix if isinstance(new_fix, list) else json.loads(new_fix) if isinstance(new_fix, str) else new_fix
                    if isinstance(old_data, dict): old_data = [old_data]
                    if isinstance(new_data, dict): new_data = [new_data]
                    
                    if isinstance(old_data, list) and isinstance(new_data, list):
                        # DETECÇÃO: É ADIÇÃO ou ALTERAÇÃO?
                        # Se está aguardando confirmação E tem fixações antigas:
                        #   - Se a nova fixação tem valores COMPLETOS e DIFERENTES → ADIÇÃO
                        #   - Se a nova fixação tem valores PARCIAIS ou SIMILARES → ALTERAÇÃO
                        
                        eh_adicao = False
                        if pending.get('aguardando_confirmacao') and len(old_data) > 0 and len(new_data) > 0:
                            # Pega primeira fixação nova
                            first_new = new_data[0]
                            # Verifica se tem campos principais preenchidos (sacas, tipo, referência)
                            tem_sacas = first_new.get('sacasFixacao') or first_new.get('sacas')
                            tem_tipo = first_new.get('tipoPrecoFixacao') or first_new.get('tipo_preco') or first_new.get('tipoPreco')
                            tem_ref = first_new.get('referenciaBolsaNy') or first_new.get('referencia') or first_new.get('referenciaPrecoFixacao')
                            
                            # Se tem todos os campos principais → provável ADIÇÃO
                            if tem_sacas and tem_tipo and tem_ref:
                                # Verifica se é diferente da fixação existente
                                for old_item in old_data:
                                    old_sacas = old_item.get('sacasFixacao') or old_item.get('sacas')
                                    old_tipo = old_item.get('tipoPrecoFixacao') or old_item.get('tipo_preco') or old_item.get('tipoPreco')
                                    old_ref = old_item.get('referenciaBolsaNy') or old_item.get('referencia') or old_item.get('referenciaPrecoFixacao')
                                    
                                    # Se os valores são DIFERENTES → é ADIÇÃO
                                    if (tem_sacas != old_sacas or tem_tipo != old_tipo or tem_ref != old_ref):
                                        eh_adicao = True
                                        break
                        
                        if eh_adicao:
                            # ADIÇÃO: concatena fixações antigas + novas
                            logger.info(f"[ADA TOOL] ➕ Detectado ADIÇÃO de fixação - concatenando com existentes")
                            merged_fix = old_data + new_data
                            current['fixacao_contrato_json'] = json.dumps(merged_fix, ensure_ascii=False)
                            logger.info(f"[ADA TOOL] ✅ Total de fixações após adição: {len(merged_fix)}")
                        else:
                            # ALTERAÇÃO: merge por índice
                            # Se foi fornecido alterar_fixacao_indice, altera apenas esse item específico
                            if current.get('alterar_fixacao_indice'):
                                indice = int(current['alterar_fixacao_indice']) - 1  # Usuário conta de 1, array de 0
                                logger.info(f"[ADA TOOL] 🔄 Alterando fixação específica no índice {indice + 1}")
                                if 0 <= indice < len(old_data) and len(new_data) > 0:
                                    # Pega a primeira fixação do new_data (os dados novos)
                                    new_item = new_data[0]
                                    new_item_clean = {k: v for k, v in new_item.items() if v is not None and v != '' and v != 0}
                                    # Merge apenas no índice especificado
                                    old_data[indice] = {**old_data[indice], **new_item_clean}
                                    merged_fix = old_data
                                    logger.info(f"[ADA TOOL] ✅ Fixação {indice + 1} alterada com sucesso")
                                else:
                                    logger.warning(f"[ADA TOOL] ⚠️ Índice {indice + 1} inválido, mantendo dados antigos")
                                    merged_fix = old_data
                            else:
                                # Merge sequencial (comportamento antigo)
                                logger.info(f"[ADA TOOL] 🔄 Detectado ALTERAÇÃO de fixação - fazendo merge sequencial")
                                merged_fix = []
                                for i in range(max(len(old_data), len(new_data))):
                                    old_item = old_data[i] if i < len(old_data) else {}
                                    new_item = new_data[i] if i < len(new_data) else {}
                                    # Remove None/empty do novo para não sobrescrever com vazio
                                    new_item_clean = {k: v for k, v in new_item.items() if v is not None and v != '' and v != 0}
                                    merged_item = {**old_item, **new_item_clean}
                                    merged_fix.append(merged_item)
                            current['fixacao_contrato_json'] = json.dumps(merged_fix, ensure_ascii=False)
                            logger.info(f"[ADA TOOL] 🔄 Merge de fixação concluído: {len(merged_fix)} fixações")
                except Exception as e:
                    logger.warning(f"[ADA TOOL] ⚠️ Erro ao processar fixação, substituindo: {e}")
            
            # MERGE ESPECIAL para comissão: mesma lógica de adição vs alteração
            if current.get('comissao_contrato_json') and pending.get('comissao_contrato_json'):
                try:
                    old_com = pending['comissao_contrato_json']
                    new_com = current['comissao_contrato_json']
                    # Parse ambos
                    old_data = old_com if isinstance(old_com, list) else json.loads(old_com) if isinstance(old_com, str) else old_com
                    new_data = new_com if isinstance(new_com, list) else json.loads(new_com) if isinstance(new_com, str) else new_com
                    if isinstance(old_data, dict): old_data = [old_data]
                    if isinstance(new_data, dict): new_data = [new_data]
                    
                    if isinstance(old_data, list) and isinstance(new_data, list):
                        # DETECÇÃO: É ADIÇÃO ou ALTERAÇÃO?
                        eh_adicao = False
                        if pending.get('aguardando_confirmacao') and len(old_data) > 0 and len(new_data) > 0:
                            # Pega primeira comissão nova
                            first_new = new_data[0]
                            # Verifica se tem campos principais preenchidos (agente, percentual, tipo)
                            tem_agente = first_new.get('codigoAgenteExportacao') or first_new.get('codigo_agente') or first_new.get('nome_agente')
                            tem_percentual = first_new.get('percentualComissao') or first_new.get('percentual')
                            tem_tipo = first_new.get('tipoComissao') or first_new.get('tipo') or first_new.get('tipo_comissao')
                            
                            # Se tem todos os campos principais → provável ADIÇÃO
                            if tem_agente and tem_percentual and tem_tipo:
                                # Verifica se é diferente da comissão existente
                                for old_item in old_data:
                                    old_agente = old_item.get('codigoAgenteExportacao') or old_item.get('codigo_agente') or old_item.get('nome_agente')
                                    old_percentual = old_item.get('percentualComissao') or old_item.get('percentual')
                                    old_tipo = old_item.get('tipoComissao') or old_item.get('tipo') or old_item.get('tipo_comissao')
                                    
                                    # Se os valores são DIFERENTES → é ADIÇÃO
                                    if (tem_agente != old_agente or tem_percentual != old_percentual or tem_tipo != old_tipo):
                                        eh_adicao = True
                                        break
                        
                        if eh_adicao:
                            # ADIÇÃO: concatena comissões antigas + novas
                            logger.info(f"[ADA TOOL] ➕ Detectado ADIÇÃO de comissão - concatenando com existentes")
                            merged_com = old_data + new_data
                            current['comissao_contrato_json'] = json.dumps(merged_com, ensure_ascii=False)
                            logger.info(f"[ADA TOOL] ✅ Total de comissões após adição: {len(merged_com)}")
                        else:
                            # ALTERAÇÃO: merge por índice
                            # Se foi fornecido alterar_comissao_indice, altera apenas esse item específico
                            if current.get('alterar_comissao_indice'):
                                indice = int(current['alterar_comissao_indice']) - 1  # Usuário conta de 1, array de 0
                                logger.info(f"[ADA TOOL] 🔄 Alterando comissão específica no índice {indice + 1}")
                                if 0 <= indice < len(old_data) and len(new_data) > 0:
                                    # Pega a primeira comissão do new_data (os dados novos)
                                    new_item = new_data[0]
                                    new_item_clean = {k: v for k, v in new_item.items() if v is not None and v != '' and v != 0}
                                    # Merge apenas no índice especificado
                                    old_data[indice] = {**old_data[indice], **new_item_clean}
                                    merged_com = old_data
                                    logger.info(f"[ADA TOOL] ✅ Comissão {indice + 1} alterada com sucesso")
                                else:
                                    logger.warning(f"[ADA TOOL] ⚠️ Índice {indice + 1} inválido, mantendo dados antigos")
                                    merged_com = old_data
                            else:
                                # Merge sequencial (comportamento antigo)
                                logger.info(f"[ADA TOOL] 🔄 Detectado ALTERAÇÃO de comissão - fazendo merge sequencial")
                                merged_com = []
                                for i in range(max(len(old_data), len(new_data))):
                                    old_item = old_data[i] if i < len(old_data) else {}
                                    new_item = new_data[i] if i < len(new_data) else {}
                                    # Remove None/empty do novo para não sobrescrever com vazio
                                    new_item_clean = {k: v for k, v in new_item.items() if v is not None and v != '' and v != 0}
                                    merged_item = {**old_item, **new_item_clean}
                                    merged_com.append(merged_item)
                            current['comissao_contrato_json'] = json.dumps(merged_com, ensure_ascii=False)
                            logger.info(f"[ADA TOOL] 🔄 Merge de comissão concluído: {len(merged_com)} comissões")
                except Exception as e:
                    logger.warning(f"[ADA TOOL] ⚠️ Erro ao processar comissão, substituindo: {e}")
            
            merged = {**pending, **current}
            
            # 3.4.5. PROTEÇÃO CRÍTICA: Se estava aguardando resposta de comissão e recebeu dados de comissão,
            # NÃO é confirmação do contrato - é resposta à pergunta de comissão
            if merged.get('comissao_perguntada') and 'comissao_contrato_json' in current:
                logger.info("[ADA TOOL] 🔄 Detectado resposta de comissão - resetando flag de confirmação")
                # Usuário está RESPONDENDO à pergunta de comissão, não confirmando o contrato
                # Reseta flags para forçar novo resumo após processar comissão
                merged.pop('aguardando_confirmacao', None)  # Remove flag de confirmação anterior
                merged.pop('comissao_perguntada', None)  # Remove flag de pergunta
                merged['reprocessar_apos_alteracao'] = True  # Marca para reprocessar e mostrar novo resumo
                logger.info("[ADA TOOL] ✅ Flags resetadas - vai processar comissão e mostrar novo resumo")
            
            # 3.5. Verifica se está aguardando confirmação (detecta, mas não processa ainda)
            aguardando_confirmacao = merged.get('aguardando_confirmacao', False)
            tem_novos_campos = len(current) > 0
            
            # LÓGICA CRÍTICA DE CONFIRMAÇÃO vs ALTERAÇÃO:
            # - PRIORIDADE 1: Se confirmar_envio=True (parâmetro explícito) → É CONFIRMAÇÃO
            # - PRIORIDADE 2: Se está aguardando E recebeu novos campos:
            #   - Se são APENAS palavras de confirmação (sim, s, ok) → É CONFIRMAÇÃO
            #   - Se NÃO são apenas confirmações → É ALTERAÇÃO (não envia!)
            # - Se não estava aguardando ou não tem campos novos → primeira vez
            
            if esta_confirmando_explicito and aguardando_confirmacao:
                # Confirmação explícita via parâmetro confirmar_envio=True
                esta_confirmando = True
                esta_alterando = False
                logger.info("[ADA TOOL] ✅ CONFIRMAÇÃO EXPLÍCITA via parâmetro confirmar_envio=True")
            elif aguardando_confirmacao and tem_novos_campos:
                # Estava aguardando confirmação e recebeu campos
                if eh_so_confirmacao:
                    # São APENAS confirmações (sim, s, ok) - pode enviar
                    esta_confirmando = True
                    esta_alterando = False
                    logger.info("[ADA TOOL] ✅ Detectado CONFIRMAÇÃO explícita (apenas 'sim', 's', etc)")
                else:
                    # Recebeu campos que NÃO são só confirmações - É ALTERAÇÃO
                    esta_confirmando = False
                    esta_alterando = True
                    logger.info(f"[ADA TOOL] ✏️ Detectado ALTERAÇÃO (campos recebidos: {list(current.keys())})")
            elif aguardando_confirmacao and not tem_novos_campos:
                # Estava aguardando mas não recebeu campos - edge case, trata como não confirmado
                esta_confirmando = False
                esta_alterando = False
                logger.info("[ADA TOOL] ⚠️ Aguardando confirmação mas sem campos recebidos")
            else:
                # Não estava aguardando ou primeira vez
                esta_confirmando = False
                esta_alterando = False
            
            logger.info(f"[ADA TOOL] 🔍 Estado de confirmação:")
            logger.info(f"[ADA TOOL]    aguardando_confirmacao: {aguardando_confirmacao}")
            logger.info(f"[ADA TOOL]    tem_novos_campos: {tem_novos_campos}")
            logger.info(f"[ADA TOOL]    campos_novos_reais: {campos_novos_reais if 'campos_novos_reais' in locals() else 'N/A'}")
            logger.info(f"[ADA TOOL]    eh_so_confirmacao: {eh_so_confirmacao}")
            logger.info(f"[ADA TOOL]    contem_palavra_alteracao: {contem_palavra_alteracao}")
            logger.info(f"[ADA TOOL]    contem_palavra_confirmacao: {contem_palavra_confirmacao}")
            logger.info(f"[ADA TOOL]    tem_dados_reais: {tem_dados_reais}")
            logger.info(f"[ADA TOOL]    texto_campos: '{texto_campos}'")
            logger.info(f"[ADA TOOL]    esta_confirmando: {esta_confirmando}")
            logger.info(f"[ADA TOOL]    esta_alterando: {esta_alterando}")
            
            if esta_confirmando:
                # Usuário está confirmando - vamos processar normalmente mas enviar no final
                logger.info("[ADA TOOL] ✅ Usuário confirmou - processando para enviar...")
                # NÃO remove a flag ainda - será usada mais abaixo para detectar que deve enviar
                # merged.pop('aguardando_confirmacao', None)  # COMENTADO - mantém a flag
            
            elif esta_alterando:
                # Usuário quer alterar alguns campos - continua fluxo normal
                logger.info(f"[ADA TOOL] ✏️ Usuário quer alterar campos: {list(current.keys())}")
                logger.info(f"[ADA TOOL] 📋 Estado antes da alteração:")
                logger.info(f"[ADA TOOL]    fixacao_contrato_json: {str(pending.get('fixacao_contrato_json', 'N/A'))[:100]}...")
                logger.info(f"[ADA TOOL]    tipo_contrato: {pending.get('tipo_contrato', 'N/A')}")
                logger.info(f"[ADA TOOL]    quantidade_embalagem: {pending.get('quantidade_embalagem', 'N/A')}")
                # Remove flag para reprocessar e mostrar novo resumo
                merged.pop('aguardando_confirmacao', None)
                # FORÇAR flag de reprocessamento para garantir que mostra resumo novamente
                merged['reprocessar_apos_alteracao'] = True
            
            # 3.1. Detecta quando usuário diz que NÃO tem algo ("sem", "nenhum", "não tem")
            # e converte para valor especial que a validação reconhece
            if "nome_cliente" in current:
                val = str(current["nome_cliente"]).strip().lower()
                sem_palavras = ["sem", "nenhum", "não tem", "nao tem", "sem nome", "vazio", "n/a", "na"]
                if any(palavra in val for palavra in sem_palavras):
                    merged["nome_cliente"] = "SEM_NOME"
            
            # 3.2. Detecta quando usuário diz que NÃO quer comissão
            # Resposta do usuário pode estar em qualquer campo de texto
            texto_completo = " ".join(str(v).lower() for v in current.values() if v is not None)
            palavras_nao_comissao = ["não quero comiss", "nao quero comiss", "sem comiss", "não adicionar comiss", "nao adicionar comiss", "não desejo comiss", "nao desejo comiss"]
            palavras_sim_comissao = ["sim", "s", "quero comiss", "adicionar comiss", "desejo comiss"]
            
            if any(palavra in texto_completo for palavra in palavras_nao_comissao) or ("comissao" not in texto_completo.lower() and any(texto_completo.strip() == p for p in ["n", "não", "nao", "nope", "no"])):
                merged["sem_comissao"] = True
                # Reseta aguardando_confirmacao para forçar mostrar resumo final
                merged.pop('aguardando_confirmacao', None)
                logger.info("[ADA TOOL] ✅ Usuário disse que NÃO quer comissão - marcando como sem_comissao=True e resetando aguardando_confirmacao")
            elif "comissao" in current.get("comissao_contrato_json", "").lower() or any(palavra in texto_completo for palavra in palavras_sim_comissao):
                # Usuário disse SIM para comissão - não marca sem_comissao
                # Reseta aguardando_confirmacao para forçar mostrar resumo final após processar comissão
                merged.pop('aguardando_confirmacao', None)
                logger.info("[ADA TOOL] ✅ Usuário quer adicionar comissão - resetando aguardando_confirmacao para mostrar resumo após processar")
            
            logger.info(f"[ADA TOOL] Dados pendentes: {list(pending.keys())}")
            logger.info(f"[ADA TOOL] Dados novos: {list(current.keys())}")
            logger.info(f"[ADA TOOL] Dados totais: {list(merged.keys())}")
            
            # 4. Normaliza campos S/N (LLM pode mandar 'sim', 'não', True, False, etc)
            # Inclui tanto campos obrigatórios quanto opcionais que usam S/N
            for campo_sn in ('exige_eudr', 'exige_ota', 'amostra_pre_embarque', 'peneira_14', 'peneira_17', 'peneira_grinder', 
                            'contrato_liberado', 'pilha_passada'):
                val = merged.get(campo_sn)
                if val is not None:
                    val_str = str(val).strip().lower()
                    if val_str in ('s', 'sim', 'yes', 'true', '1'):
                        merged[campo_sn] = True if 'peneira' in campo_sn else 'S'
                    elif val_str in ('n', 'não', 'nao', 'no', 'false', '0'):
                        merged[campo_sn] = False if 'peneira' in campo_sn else 'N'
                    # Se já é 'S' ou 'N' maiúsculo, mantém
            
            # 5. Salva estado acumulado no Redis
            self._save_pending_data(merged)
            
            # 6. Parse de arrays JSON (do merged) com normalização de campo
            # Mapas de aliases para nome correto (LLM pode mandar snake_case ou abreviado)
            _FIXACAO_ALIASES = {
                "sacas_fixacao": "sacasFixacao", "sacas": "sacasFixacao", "quantidade_sacas": "sacasFixacao", "sacasFixacao": "sacasFixacao", "numero_sacas": "sacasFixacao",
                "tipo_preco_fixacao": "tipoPrecoFixacao", "tipo_preco": "tipoPrecoFixacao", "tipoPreco": "tipoPrecoFixacao", "tipoPrecoFixacao": "tipoPrecoFixacao", "tipo": "tipoPrecoFixacao",
                "tipo_valor": "tipoValor", "tipoValor": "tipoValor",
                "referencia_bolsa_ny": "referenciaBolsaNy", "referencia_bolsa": "referenciaBolsaNy", "referenciaBolsa": "referenciaBolsaNy", "bolsa_ny": "referenciaBolsaNy", "referenciaBolsaNy": "referenciaBolsaNy", "referencia": "referenciaBolsaNy",
                "mes_ano_fixacao": "mesAnoFixacao", "mes_ano": "mesAnoFixacao", "mesAno": "mesAnoFixacao", "mesAnoFixacao": "mesAnoFixacao", "mes": "mesAnoFixacao",
                "fixador_preco": "fixadorPreco", "fixador": "fixadorPreco", "fixadorPreco": "fixadorPreco",
            }
            _COMISSAO_ALIASES = {
                "codigo_agente_exportacao": "codigoAgenteExportacao", "codigo_agente": "codigoAgenteExportacao", "codigoAgente": "codigoAgenteExportacao", "agente": "codigoAgenteExportacao", "codigoAgenteExportacao": "codigoAgenteExportacao",
                "loja_agente_exportacao": "lojaAgenteExportacao", "loja_agente": "lojaAgenteExportacao", "lojaAgente": "lojaAgenteExportacao", "loja": "lojaAgenteExportacao", "lojaAgenteExportacao": "lojaAgenteExportacao",
                "nome_agente_exportacao": "nomeAgenteExportacao", "nome_agente": "nomeAgenteExportacao", "nomeAgente": "nomeAgenteExportacao", "nomeAgenteExportacao": "nomeAgenteExportacao",
                "percentual_comissao": "percentualComissao", "percentual": "percentualComissao", "percentualComissao": "percentualComissao",
                "tipo_comissao": "tipoComissao", "tipo": "tipoComissao", "tipoComissao": "tipoComissao",
            }

            def _normalize_keys(d: dict, aliases: dict) -> dict:
                """Normaliza nomes de chaves usando mapa de aliases"""
                result = {}
                for k, v in d.items():
                    canonical = aliases.get(k, k)
                    result[canonical] = v
                return result
            
            def _filter_valid_fields(d: dict, model_class) -> dict:
                """Remove campos que não existem no modelo Pydantic"""
                valid_fields = set(model_class.__fields__.keys())
                return {k: v for k, v in d.items() if k in valid_fields}

            def _coerce_fixacao_values(d: dict) -> dict:
                """Normaliza valores de fixação (LLM pode mandar formatos variados)"""
                import re as _re
                # referenciaBolsaNy: "NY 400" -> 400, "400.5" -> 400.5
                if "referenciaBolsaNy" in d and d["referenciaBolsaNy"] is not None:
                    val = str(d["referenciaBolsaNy"]).strip()
                    nums = _re.findall(r'[\d.]+', val)
                    d["referenciaBolsaNy"] = float(nums[-1]) if nums else 0
                # sacasFixacao: "300 sacas" -> 300
                if "sacasFixacao" in d and d["sacasFixacao"] is not None:
                    val = str(d["sacasFixacao"]).strip()
                    nums = _re.findall(r'\d+', val)
                    d["sacasFixacao"] = int(nums[0]) if nums else 0
                # tipoPrecoFixacao: "A fixar" -> "A", "Fixado" -> "F"
                if "tipoPrecoFixacao" in d and d["tipoPrecoFixacao"] is not None:
                    val = str(d["tipoPrecoFixacao"]).strip().upper()
                    if val.startswith("A"):
                        d["tipoPrecoFixacao"] = "A"
                    elif val.startswith("F"):
                        d["tipoPrecoFixacao"] = "F"
                # FALLBACK: Se tipoPrecoFixacao não foi informado mas tem fixadorPreco, assume "A" (a fixar)
                elif "fixadorPreco" in d and d.get("fixadorPreco"):
                    logger.info(f"[ADA TOOL] ⚠️ tipoPrecoFixacao não informado mas fixadorPreco presente - assumindo 'A' (a fixar)")
                    d["tipoPrecoFixacao"] = "A"
                # fixadorPreco: "E"/"Exportador"/"exportação" -> "E", "I"/"Importador"/"importação" -> "I"
                if "fixadorPreco" in d and d["fixadorPreco"] is not None:
                    val = str(d["fixadorPreco"]).strip().upper()
                    if val.startswith("E"):
                        d["fixadorPreco"] = "E"
                    elif val.startswith("I") or val.startswith("C"):  # C = Comprador = Importador
                        d["fixadorPreco"] = "I"
                # tipoValor: normaliza variações comuns, deixa outros valores para o resolver processar
                if "tipoValor" in d and d["tipoValor"] is not None:
                    val = str(d["tipoValor"]).strip().upper()
                    # Mapeamento direto apenas de valores conhecidos que não estão na API
                    # Valores como "US$ KG", "CTS/LB" são resolvidos pelo resolver
                    mapa_tipo_valor = {
                        "CENTAVOS": "C",
                        "CENTS": "C",
                        "CTS": "C",
                    }
                    # Verifica se é um dos valores conhecidos
                    if val in mapa_tipo_valor:
                        d["tipoValor"] = mapa_tipo_valor[val]
                    # Senão, mantém o valor original para o resolver processar
                    # NÃO define default "C" aqui - deixa o resolver fazer o trabalho
                return d

            def _coerce_comissao_values(d: dict) -> dict:
                """Normaliza valores de comissão"""
                import re as _re
                if "percentualComissao" in d and d["percentualComissao"] is not None:
                    val = str(d["percentualComissao"]).strip().replace("%", "")
                    nums = _re.findall(r'[\d.]+', val)
                    d["percentualComissao"] = float(nums[0]) if nums else 0
                return d

            def _parse_json_array(raw, aliases: dict, model_class, coerce_fn=None):
                """Parse JSON string/dict/list para lista de model instances"""
                data = raw
                while isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, dict):
                    data = [data]
                if not isinstance(data, list):
                    raise ValueError(f"Tipo inesperado: {type(data)}")
                results = []
                for item in data:
                    if isinstance(item, dict):
                        normalized = _normalize_keys(item, aliases)
                        if coerce_fn:
                            normalized = coerce_fn(normalized)
                        # Filtra apenas campos válidos do modelo
                        filtered = _filter_valid_fields(normalized, model_class)
                        results.append(model_class(**filtered))
                    else:
                        results.append(item)
                return results

            fixacao_list = []
            fix_json = merged.get("fixacao_contrato_json")
            # Valida se não é string vazia antes de parsear
            if fix_json and str(fix_json).strip():
                logger.info(f"[ADA TOOL] 🔍 Parseando fixação... Tipo: {type(fix_json)}")
                logger.info(f"[ADA TOOL] 🔍 JSON bruto (primeiros 200 chars): {str(fix_json)[:200]}")
                try:
                    fixacao_list = _parse_json_array(fix_json, _FIXACAO_ALIASES, FixacaoContrato, _coerce_fixacao_values)
                    logger.info(f"[ADA TOOL] ✅ Fixação parseada com sucesso: {len(fixacao_list)} item(s)")
                    
                    # Resolve campos de fixação (tipo_preco_fixacao, tipo_valor, fixador_preco)
                    for idx, fix in enumerate(fixacao_list):
                        fix_dict = fix.dict()
                        logger.info(f"[ADA TOOL]   Fixação #{idx+1}: {fix_dict}")
                        
                        # Campos de fixação que precisam resolução
                        campos_fixacao_para_resolver = ["tipo_preco_fixacao", "tipo_valor", "fixador_preco"]
                        
                        for campo in campos_fixacao_para_resolver:
                            # Mapeia campo snake_case para camelCase
                            campo_camel = {
                                "tipo_preco_fixacao": "tipoPrecoFixacao",
                                "tipo_valor": "tipoValor",
                                "fixador_preco": "fixadorPreco"
                            }.get(campo)
                            
                            if campo_camel and fix_dict.get(campo_camel):
                                valor_original = fix_dict[campo_camel]
                                logger.info(f"[ADA TOOL] 🔍 Resolvendo fixação[{idx}].{campo}: '{valor_original}'")
                                
                                try:
                                    # Threshold mais baixo para campos de fixação (caracteres especiais como $ podem atrapalhar)
                                    threshold = 40 if campo == "tipo_valor" else 60
                                    
                                    try:
                                        loop = asyncio.get_running_loop()
                                        import nest_asyncio
                                        nest_asyncio.apply()
                                        valor_resolvido, descricao, loja = asyncio.run(field_resolver.resolve_field(campo, str(valor_original), threshold=threshold))
                                    except RuntimeError:
                                        valor_resolvido, descricao, loja = asyncio.run(field_resolver.resolve_field(campo, str(valor_original), threshold=threshold))
                                    
                                    logger.info(f"[ADA TOOL] 🔍 Resolver retornou para fixação[{idx}].{campo}: valor='{valor_resolvido}', descricao='{descricao}'")
                                    
                                    # Atualiza o valor no objeto fix
                                    if valor_resolvido:
                                        setattr(fix, campo_camel, valor_resolvido)
                                        logger.info(f"[ADA TOOL] ✅ Fixação[{idx}].{campo_camel} atualizado: '{valor_resolvido}'")
                                    else:
                                        # Se resolver falhou
                                        logger.warning(f"[ADA TOOL] ⚠️ Fixação[{idx}].{campo}: resolver falhou para '{valor_original}'")
                                        # Para tipoValor especificamente, usa "C" como fallback seguro
                                        if campo == "tipo_valor":
                                            setattr(fix, campo_camel, "C")
                                            logger.warning(f"[ADA TOOL] 🔧 Fixação[{idx}].{campo_camel} não resolvido, usando fallback 'C' (CTS/LB) para valor inválido '{valor_original}'")
                                        # Para outros campos, mantém valor original
                                        else:
                                            logger.warning(f"[ADA TOOL] ⚠️ Mantendo valor original '{valor_original}'")
                                    
                                    # Armazena descrição (adiciona ao objeto como atributo extra)
                                    if descricao:
                                        desc_field = f"descricao{campo_camel[0].upper()}{campo_camel[1:]}"
                                        setattr(fix, desc_field, descricao)
                                        logger.info(f"[ADA TOOL] ✅ Descrição armazenada: fixação[{idx}].{desc_field} = '{descricao}'")
                                
                                except Exception as e:
                                    logger.error(f"[ADA TOOL] ❌ Erro ao resolver fixação[{idx}].{campo}: {e}")
                    
                    # Limpa flag de aviso quando fixação é realmente recebida
                    if 'aviso_fixacao_dado' in merged:
                        logger.info(f"[ADA TOOL] 🧹 Limpando flag aviso_fixacao_dado pois fixação foi recebida")
                        merged.pop('aviso_fixacao_dado', None)
                except json.JSONDecodeError as e:
                    logger.error(f"[ADA TOOL] ❌ Erro JSON ao parsear fixacao_contrato_json: {e}")
                    logger.error(f"[ADA TOOL] JSON recebido: {fix_json}")
                    return f"ERRO: formato inválido de fixacao_contrato_json. Deve ser um JSON array válido."
                except Exception as e:
                    logger.error(f"[ADA TOOL] ❌ Erro ao parsear fixacao_contrato_json: {e}")
                    logger.error(f"[ADA TOOL] Stack trace:", exc_info=True)
                    logger.error(f"[ADA TOOL] JSON recebido: {fix_json}")
                    
                    # Se erro de validação Pydantic, mostra mensagem específica
                    erro_msg = str(e)
                    if "mesAnoFixacao" in erro_msg and "obrigatório" in erro_msg:
                        return f"""ERRO_FIXACAO_INCOMPLETA: O JSON de fixação está faltando o campo mes_ano_fixacao!

Você recebeu do usuário algo como "mês 07/2026" mas NÃO incluiu no JSON.

JSON recebido (incompleto): {fix_json}

CORRETO seria:
fixacao_contrato_json='[{{"sacas": 300, "mes_ano_fixacao": "07/2026", "tipo_preco": "a fixar", "fixador_preco": "importador", "tipo_valor": "US$ KG", "referencia": 400}}]'

⚠️ TODOS os 6 campos são OBRIGATÓRIOS quando tipo_preco = "a fixar":
1. sacas
2. mes_ano_fixacao ← VOCÊ ESQUECEU ESTE!
3. tipo_preco
4. fixador_preco
5. tipo_valor
6. referencia

Releia a mensagem do usuário, identifique o MÊS/ANO que ele mencionou e monte o JSON COMPLETO."""
                    
                    return f"ERRO: formato inválido de fixacao_contrato_json. {erro_msg}"
            else:
                logger.warning(f"[ADA TOOL] ⚠️ Nenhuma fixação encontrada (fixacao_contrato_json vazio ou None)")
            
            comissao_list = []
            com_json = merged.get("comissao_contrato_json")
            # Valida se não é string vazia antes de parsear
            if com_json and str(com_json).strip():
                try:
                    comissao_list = _parse_json_array(com_json, _COMISSAO_ALIASES, ComissaoContrato, _coerce_comissao_values)
                    logger.info(f"[ADA TOOL] ✅ Comissão parseada com sucesso: {len(comissao_list)} item(s)")
                except json.JSONDecodeError as e:
                    logger.error(f"[ADA TOOL] Erro JSON ao parsear comissao_contrato_json: {e}")
                    logger.error(f"[ADA TOOL] JSON recebido: {com_json}")
                    # Não retorna erro - apenas ignora comissão vazia
                    logger.warning(f"[ADA TOOL] Ignorando comissao_contrato_json vazio ou inválido")
                except Exception as e:
                    logger.error(f"[ADA TOOL] Erro ao parsear comissao_contrato_json: {e}")
                    logger.error(f"[ADA TOOL] JSON recebido: {com_json}")
                    # Não retorna erro - apenas ignora comissão vazia
                    logger.warning(f"[ADA TOOL] Ignorando comissao_contrato_json vazio ou inválido")
            
            # Resolve campos de comissão que precisam buscar na API
            if comissao_list:
                logger.info(f"[ADA TOOL] 🔍 Verificando resolução de campos de comissão...")
                for idx, com in enumerate(comissao_list):
                    com_dict = com.dict() if hasattr(com, 'dict') else com
                    
                    # ⚠️ VERIFICAÇÃO IMPORTANTE: Se usuário já forneceu código E loja, NÃO tenta resolver!
                    # Isso evita split incorreto quando ambos os valores já foram especificados
                    if com_dict.get("codigoAgenteExportacao") and com_dict.get("lojaAgenteExportacao"):
                        logger.info(f"[ADA TOOL] ✅ Comissão[{idx}] já tem código E loja - pulando resolução")
                        logger.info(f"[ADA TOOL]    codigo='{com_dict['codigoAgenteExportacao']}', loja='{com_dict['lojaAgenteExportacao']}'")
                        # Pula para o próximo item sem tentar resolver
                        continue
                    
                    # Determina qual campo usar para resolução
                    valor_para_resolver = None
                    campo_origem = None
                    
                    # Prioridade 1: Se tem codigoAgenteExportacao (mas NÃO tem loja), usa ele para buscar
                    if com_dict.get("codigoAgenteExportacao") and not com_dict.get("lojaAgenteExportacao"):
                        valor_para_resolver = str(com_dict["codigoAgenteExportacao"])
                        campo_origem = "codigoAgenteExportacao"
                    # Prioridade 2: Se tem apenas nomeAgenteExportacao (sem código), usa o nome para buscar
                    elif com_dict.get("nomeAgenteExportacao") and not com_dict.get("codigoAgenteExportacao"):
                        valor_para_resolver = str(com_dict["nomeAgenteExportacao"])
                        campo_origem = "nomeAgenteExportacao"
                    
                    # Só resolve se encontrou algum valor
                    if valor_para_resolver:
                        logger.info(f"[ADA TOOL] 🔍 Resolvendo comissão[{idx}] usando {campo_origem}: '{valor_para_resolver}'")
                        
                        try:
                            # Chama resolver
                            try:
                                loop = asyncio.get_running_loop()
                                import nest_asyncio
                                nest_asyncio.apply()
                                codigo_resolvido, nome_agente, loja_agente = asyncio.run(field_resolver.resolve_field("codigo_agente_exportacao", valor_para_resolver, threshold=60))
                            except RuntimeError:
                                codigo_resolvido, nome_agente, loja_agente = asyncio.run(field_resolver.resolve_field("codigo_agente_exportacao", valor_para_resolver, threshold=60))
                            
                            logger.info(f"[ADA TOOL] 🔍 Resolver retornou: codigo='{codigo_resolvido}', nome='{nome_agente}', loja='{loja_agente}'")
                            
                            # O código pode vir em 2 formatos:
                            # 1. Com espaço: "07889486 0001"
                            # 2. Sem espaço: "JS00000300001", "IMPS000240001"
                            if codigo_resolvido:
                                import re
                                
                                # Tenta primeiro com espaço (padrão mais comum)
                                match_espaco = re.match(r'^(.+)\s+(\d{4,5})$', codigo_resolvido.strip())
                                if match_espaco:
                                    codigo_agente = match_espaco.group(1)
                                    loja_agente_split = match_espaco.group(2)
                                    logger.info(f"[ADA TOOL] 📋 Split com espaço: codigo='{codigo_agente}', loja='{loja_agente_split}'")
                                else:
                                    # Sem espaço - identifica últimos 4 dígitos como loja (padrão mais comum)
                                    # Usa greedy .+ para capturar máximo possível no código
                                    match_sem_espaco = re.match(r'^(.+)(\d{4})$', codigo_resolvido.strip())
                                    if match_sem_espaco:
                                        codigo_agente = match_sem_espaco.group(1)
                                        loja_agente_split = match_sem_espaco.group(2)
                                        logger.info(f"[ADA TOOL] 📋 Split sem espaço (4 dígitos): codigo='{codigo_agente}', loja='{loja_agente_split}'")
                                    else:
                                        # Não conseguiu identificar padrão - usa código completo e loja padrão
                                        logger.warning(f"[ADA TOOL] ⚠️ Não conseguiu identificar padrão em '{codigo_resolvido}' - usando loja padrão '0001'")
                                        codigo_agente = codigo_resolvido
                                        loja_agente_split = "0001"
                                
                                # Atualiza objeto
                                com.codigoAgenteExportacao = codigo_agente
                                com.lojaAgenteExportacao = loja_agente_split
                                logger.info(f"[ADA TOOL] ✅ Comissão[{idx}] resolvida: codigo='{codigo_agente}', loja='{loja_agente_split}'")
                                
                                # Armazena nome do agente se disponível
                                if nome_agente:
                                    com.nomeAgenteExportacao = nome_agente
                                    logger.info(f"[ADA TOOL] ✅ Nome do agente armazenado: '{nome_agente}'")
                            else:
                                # Resolver não encontrou nada
                                logger.warning(f"[ADA TOOL] ⚠️ Resolver não encontrou correspondência para '{valor_para_resolver}'")
                                # Se veio do nomeAgenteExportacao, não sobrescreve (deixa o nome original)
                                # Se veio do codigoAgenteExportacao, também mantém original
                        
                        except Exception as e:
                            logger.warning(f"[ADA TOOL] ⚠️ Erro ao resolver comissão[{idx}].{campo_origem}: {e}")
                            logger.warning(f"[ADA TOOL] Mantendo valor original: '{valor_para_resolver}'")
                    
                    # Resolve tipoComissao se presente
                    if com_dict.get("tipoComissao"):
                        tipo_comissao_original = str(com_dict["tipoComissao"])
                        logger.info(f"[ADA TOOL] 🔍 Resolvendo comissão[{idx}].tipo_comissao: '{tipo_comissao_original}'")
                        
                        try:
                            # Chama resolver
                            try:
                                loop = asyncio.get_running_loop()
                                import nest_asyncio
                                nest_asyncio.apply()
                                tipo_resolvido, descricao_tipo, _ = asyncio.run(field_resolver.resolve_field("tipo_comissao", tipo_comissao_original, threshold=60))
                            except RuntimeError:
                                tipo_resolvido, descricao_tipo, _ = asyncio.run(field_resolver.resolve_field("tipo_comissao", tipo_comissao_original, threshold=60))
                            
                            logger.info(f"[ADA TOOL] 🔍 Resolver retornou: tipo='{tipo_resolvido}', descricao='{descricao_tipo}'")
                            
                            # Atualiza código se resolvido
                            if tipo_resolvido:
                                com.tipoComissao = tipo_resolvido
                                logger.info(f"[ADA TOOL] ✅ Comissão[{idx}].tipoComissao atualizado: '{tipo_resolvido}'")
                            
                            # Armazena descrição
                            if descricao_tipo:
                                com.descricaoTipoComissao = descricao_tipo
                                logger.info(f"[ADA TOOL] ✅ Descrição do tipo de comissão armazenada: '{descricao_tipo}'")
                        
                        except Exception as e:
                            logger.warning(f"[ADA TOOL] ⚠️ Erro ao resolver comissão[{idx}].tipo_comissao: {e}")
                            logger.warning(f"[ADA TOOL] Mantendo valor original: '{tipo_comissao_original}'")

            
            # 7. Cria model com TODOS os dados acumulados
            # Limpa valor especial "SEM_NOME" antes de criar o contrato
            nome_cliente_final = merged.get("nome_cliente")
            if nome_cliente_final and str(nome_cliente_final).upper() in ["SEM_NOME", "SEM NOME", "NENHUM", "VAZIO", "N/A"]:
                nome_cliente_final = None
            
            # Marca flag de "perguntado sobre comissão" se usuário respondeu
            sem_comissao_marcado = merged.get("sem_comissao", False)
            
            contrato = ContratoVendaExportacao(
                codigoFilial="05",
                codigoCliente=merged.get("codigo_cliente"),
                lojaCliente=merged.get("loja_cliente"),
                nomeCliente=nome_cliente_final,
                codigoEmbalagem=merged.get("codigo_embalagem"),
                quantidadeKg=merged.get("quantidade_kg"),
                padraoQualidade=merged.get("padrao_qualidade"),
                modalidadePagamento=merged.get("modalidade_pagamento"),
                quantidadeContainer=merged.get("quantidade_container"),
                mesEmbarque=merged.get("mes_embarque"),
                exigeEudr=merged.get("exige_eudr"),
                exigeOTA=merged.get("exige_ota"),
                amostraPreEmbarque=merged.get("amostra_pre_embarque"),
                condicaoEntrega=merged.get("condicao_entrega"),
                moedaFixacao=merged.get("moeda_fixacao"),
                tipoContrato=merged.get("tipo_contrato"),
                condicaoPeso=merged.get("condicao_peso"),
                dataPrevisaoEntrega=merged.get("data_previsao_entrega"),
                quantidadeEmbalagem=merged.get("quantidade_embalagem"),
                quantidadePallet=merged.get("quantidade_pallet"),
                peneira14=merged.get("peneira_14"),
                peneira17=merged.get("peneira_17"),
                peneiraGrinder=merged.get("peneira_grinder"),
                taxaDolar=merged.get("taxa_dolar"),
                # Campos opcionais adicionais
                descricaoQualidade=merged.get("descricao_qualidade"),
                referenciaCliente=merged.get("referencia_cliente"),
                condicaoPagamento=merged.get("condicao_pagamento"),
                armazemPreparo=merged.get("armazem_preparo"),
                produtoExportacao=merged.get("produto_exportacao"),
                descricaoDetalhada=merged.get("descricao_detalhada"),
                codigoBanco=merged.get("codigo_banco"),
                agenciaBancaria=merged.get("agencia_bancaria"),
                digitoVerificadorAgencia=merged.get("digito_verificador_agencia"),
                contaCorrente=merged.get("conta_corrente"),
                digitoVerificadorContaCorrente=merged.get("digito_verificador_conta_corrente"),
                periodoEmbarque=merged.get("periodo_embarque"),
                responsavelDocumento=merged.get("responsavel_documento"),
                embarcador=merged.get("embarcador"),
                tipoVenda=merged.get("tipo_venda"),
                incoterm=merged.get("incoterm"),
                certificador=merged.get("certificador"),
                contratoLiberado=merged.get("contrato_liberado"),
                referenciaCorretor=merged.get("referencia_corretor"),
                armazemDestino=merged.get("armazem_destino"),
                vendedor=merged.get("vendedor"),
                variacaoPeso=merged.get("variacao_peso"),
                totalCostDdp=merged.get("total_cost_ddp"),
                difCashAgainst=merged.get("dif_cash_against"),
                alerta=merged.get("alerta"),
                notas=merged.get("notas"),
                pilhaPassada=merged.get("pilha_passada"),
                sampleConditions=merged.get("sample_conditions"),
                spot=merged.get("spot"),
                codigoClienteFinal=merged.get("codigo_cliente_final"),
                lojaClienteFinal=merged.get("loja_cliente_final"),
                nomeClienteFinal=merged.get("nome_cliente_final"),
                diferencialClienteFinal=merged.get("diferencial_cliente_final"),
                # Arrays
                fixacaoContrato=fixacao_list,
                comissaoContrato=comissao_list
            )
            
            # Marca a flag interna para não perguntar comissão novamente
            if sem_comissao_marcado:
                contrato._sem_comissao_perguntado = True
            
            # 8. Verifica campos obrigatórios faltantes
            missing_fields = contrato.get_missing_fields()
            if missing_fields:
                logger.info(f"[ADA TOOL] Campos faltantes: {missing_fields}")
                
                # Mostra os que já foram coletados
                coletados = [k for k in merged.keys() if k not in ("fixacao_contrato_json", "comissao_contrato_json", "aguardando_confirmacao", "aviso_fixacao_dado")]
                
                # Retorna no máximo 3 campos por vez
                campos_para_perguntar = missing_fields[:3]
                
                resumo = ""
                if coletados:
                    resumo = f"DADOS JÁ COLETADOS: {', '.join(coletados)}\n\n"
                
                # NÃO pergunta sobre fixação aqui - só quando todos os campos estiverem preenchidos
                return f"PRECISA_PERGUNTAR: {resumo}Para completar o contrato, preciso que informe:\n\n" + "\n".join(campos_para_perguntar)
            
            # 9. Todos os campos OK - AGORA verifica se tem fixação
            logger.info("[ADA TOOL] ✅ Todos os campos obrigatórios preenchidos")
            
            # Se não tem fixação, pergunta AGORA (penúltimo passo)
            if not fixacao_list and not merged.get('aviso_fixacao_dado'):
                logger.info("[ADA TOOL] 📊 Todos campos OK mas sem fixação - perguntando agora...")
                merged['aviso_fixacao_dado'] = True
                self._save_pending_data(merged)
                
                return """PRECISA_PERGUNTAR: Todos os campos do contrato estão preenchidos! 

Agora preciso dos dados de FIXAÇÃO:

1. Quantas sacas deseja fixar?
2. Qual o tipo de preço?
3. Qual a referência da bolsa NY?
4. Quem vai fixar o preço?
5. Qual o mês/ano de fixação?
6. Qual o tipo de valor?

Aguardo sua resposta com todos estes dados."""
            
            # Se tem fixação mas não perguntou sobre comissão ainda (último passo ANTES do resumo)
            if not comissao_list and not merged.get('sem_comissao') and not merged.get('comissao_perguntada'):
                logger.info("[ADA TOOL] 💵 Fixação OK - perguntando sobre comissão (último passo antes do resumo)...")
                merged['comissao_perguntada'] = True
                self._save_pending_data(merged)
                
                # NÃO mostra resumo ainda - apenas pergunta sobre comissão
                return """PRECISA_PERGUNTAR_COMISSAO: Fixação registrada com sucesso!

Deseja adicionar COMISSÃO ao contrato? 

• Digite sim, caso não queira digite não:
  - **Nome do agente**
  - **Percentual de comissão**
  - **Tipo de comissão**

O sistema buscará automaticamente o código e loja do agente.

Aguardo sua resposta para gerar o resumo final."""
            
            # 10. Campos OK, fixação OK, comissão OK/dispensada - continua para validação
            logger.info("[ADA TOOL] ✅ Todos os campos, fixação e comissão preenchidos")
            
            json_final = contrato.to_dict()
            
            # Adiciona descricaoEmbalagem ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_embalagem"):
                json_final["descricaoEmbalagem"] = merged.get("descricao_embalagem")
                logger.info(f"[ADA TOOL] 📦 Descrição da embalagem adicionada ao resumo: {merged.get('descricao_embalagem')}")
            
            # Adiciona descricaoPadraoQualidade ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_padrao_qualidade"):
                json_final["descricaoPadraoQualidade"] = merged.get("descricao_padrao_qualidade")
                logger.info(f"[ADA TOOL] 📋 Descrição do padrão de qualidade adicionada ao resumo: {merged.get('descricao_padrao_qualidade')}")
            
            # Adiciona descricaoModalidadePagamento ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_modalidade_pagamento"):
                json_final["descricaoModalidadePagamento"] = merged.get("descricao_modalidade_pagamento")
                logger.info(f"[ADA TOOL] 💳 Descrição da modalidade de pagamento adicionada ao resumo: {merged.get('descricao_modalidade_pagamento')}")
            
            # Adiciona descricaoCondicaoEntrega ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_condicao_entrega"):
                json_final["descricaoCondicaoEntrega"] = merged.get("descricao_condicao_entrega")
                logger.info(f"[ADA TOOL] 🚚 Descrição da condição de entrega adicionada ao resumo: {merged.get('descricao_condicao_entrega')}")
            
            # Adiciona descricaoMoedaFixacao ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_moeda_fixacao"):
                json_final["descricaoMoedaFixacao"] = merged.get("descricao_moeda_fixacao")
                logger.info(f"[ADA TOOL] 💵 Descrição da moeda de fixação adicionada ao resumo: {merged.get('descricao_moeda_fixacao')}")
            
            # Adiciona descricaoTipoContrato ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_tipo_contrato"):
                json_final["descricaoTipoContrato"] = merged.get("descricao_tipo_contrato")
                logger.info(f"[ADA TOOL] 📋 Descrição do tipo de contrato adicionada ao resumo: {merged.get('descricao_tipo_contrato')}")
            
            # Adiciona descricaoCondicaoPeso ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_condicao_peso"):
                json_final["descricaoCondicaoPeso"] = merged.get("descricao_condicao_peso")
                logger.info(f"[ADA TOOL] ⚖️ Descrição da condição de peso adicionada ao resumo: {merged.get('descricao_condicao_peso')}")
            
            # Adiciona descricaoCondicaoPagamento ao json_final para exibir no resumo (não enviado à API)
            if merged.get("descricao_condicao_pagamento"):
                json_final["descricaoCondicaoPagamento"] = merged.get("descricao_condicao_pagamento")
                logger.info(f"[ADA TOOL] 💳 Descrição da condição de pagamento adicionada ao resumo: {merged.get('descricao_condicao_pagamento')}")
            
            # Adiciona descrições dos campos opcionais adicionais
            if merged.get("descricao_armazem_preparo"):
                json_final["descricaoArmazemPreparo"] = merged.get("descricao_armazem_preparo")
                logger.info(f"[ADA TOOL] 🏢 Descrição do armazém preparo adicionada ao resumo: {merged.get('descricao_armazem_preparo')}")
            
            if merged.get("descricao_produto_exportacao"):
                json_final["descricaoProdutoExportacao"] = merged.get("descricao_produto_exportacao")
                logger.info(f"[ADA TOOL] 📦 Descrição do produto exportação adicionada ao resumo: {merged.get('descricao_produto_exportacao')}")
            
            if merged.get("descricao_responsavel_documento"):
                json_final["descricaoResponsavelDocumento"] = merged.get("descricao_responsavel_documento")
                logger.info(f"[ADA TOOL] 👤 Descrição do responsável documento adicionada ao resumo: {merged.get('descricao_responsavel_documento')}")
            
            if merged.get("descricao_embarcador"):
                json_final["descricaoEmbarcador"] = merged.get("descricao_embarcador")
                logger.info(f"[ADA TOOL] 🚢 Descrição do embarcador adicionada ao resumo: {merged.get('descricao_embarcador')}")
            
            if merged.get("descricao_incoterm"):
                json_final["descricaoIncoterm"] = merged.get("descricao_incoterm")
                logger.info(f"[ADA TOOL] 📋 Descrição do incoterm adicionada ao resumo: {merged.get('descricao_incoterm')}")
            
            if merged.get("descricao_armazem_destino"):
                json_final["descricaoArmazemDestino"] = merged.get("descricao_armazem_destino")
                logger.info(f"[ADA TOOL] 🏢 Descrição do armazém destino adicionada ao resumo: {merged.get('descricao_armazem_destino')}")
            
            if merged.get("descricao_vendedor"):
                json_final["descricaoVendedor"] = merged.get("descricao_vendedor")
                logger.info(f"[ADA TOOL] 👤 Descrição do vendedor adicionada ao resumo: {merged.get('descricao_vendedor')}")
            
            if merged.get("descricao_spot"):
                json_final["descricaoSpot"] = merged.get("descricao_spot")
                logger.info(f"[ADA TOOL] 📊 Descrição do spot adicionada ao resumo: {merged.get('descricao_spot')}")
            
            if merged.get("descricao_bolsa_fixacao"):
                json_final["descricaoBolsaFixacao"] = merged.get("descricao_bolsa_fixacao")
                logger.info(f"[ADA TOOL] 📈 Descrição da bolsa de fixação adicionada ao resumo: {merged.get('descricao_bolsa_fixacao')}")
            
            logger.info(f"[ADA TOOL] 📋 JSON FINAL gerado:")
            logger.info(f"[ADA TOOL]    tipo_contrato: {json_final.get('tipoContrato')}")
            logger.info(f"[ADA TOOL]    quantidade_embalagem: {json_final.get('quantidadeEmbalagem')}")
            logger.info(f"[ADA TOOL]    taxa_dolar: {json_final.get('taxaDolar')}")
            logger.info(f"[ADA TOOL]    fixacao: {len(json_final.get('fixacaoContrato', []))} items")
            if json_final.get('fixacaoContrato'):
                for idx, fix in enumerate(json_final['fixacaoContrato']):
                    logger.info(f"[ADA TOOL]       Fix #{idx+1}: sacas={fix.get('sacasFixacao')}, tipo={fix.get('tipoPrecoFixacao')}, ref={fix.get('referenciaPrecoFixacao')}")
            
            # Validações finais do JSON
            logger.info("[ADA TOOL] 🔍 Validando JSON final...")
            
            # Verifica fixação
            if 'fixacaoContrato' in json_final and json_final['fixacaoContrato']:
                for idx, fix in enumerate(json_final['fixacaoContrato']):
                    if fix.get('tipoPrecoFixacao') == 'A':
                        if not fix.get('fixadorPreco'):
                            logger.error(f"[ADA TOOL] ❌ Fixação #{idx+1}: falta fixadorPreco quando tipoPrecoFixacao='A'")
                            return f"ERRO: Fixação incompleta - falta informar o fixadorPreco (Exportador ou Importador) quando tipo de preço é 'A fixar'"
                        if not fix.get('mesAnoFixacao'):
                            logger.error(f"[ADA TOOL] ❌ Fixação #{idx+1}: falta mesAnoFixacao quando tipoPrecoFixacao='A'")
                            return f"ERRO: Fixação incompleta - falta informar o mesAnoFixacao quando tipo de preço é 'A fixar'"
            
            # Verifica se código embalagem é igual ao código cliente (provável erro do LLM)
            if json_final.get('codigoEmbalagem') == json_final.get('codigoCliente'):
                logger.error(f"[ADA TOOL] ❌ ERRO: codigoEmbalagem ({json_final.get('codigoEmbalagem')}) NÃO PODE ser igual a codigoCliente!")
                return f"ERRO: O código da embalagem ({json_final.get('codigoEmbalagem')}) NÃO PODE ser igual ao código do cliente. Pergunte ao usuário qual é o CÓDIGO DO CLIENTE (diferente do código da embalagem)."
            
            # Verifica se condicaoEntrega está com valor típico de condicaoPeso
            valores_condicao_peso = ['NDW', 'GW', 'NW']
            if json_final.get('condicaoEntrega') in valores_condicao_peso:
                logger.error(f"[ADA TOOL] ❌ ERRO: condicaoEntrega ({json_final.get('condicaoEntrega')}) parece ser um valor de condicaoPeso!")
                return f"ERRO: Condição de entrega '{json_final.get('condicaoEntrega')}' é na verdade um valor de condição de PESO. Pergunte ao usuário qual é a CONDIÇÃO DE ENTREGA (FOB, EMB, CIF, ENT, etc)."
            
            # Testa se o JSON é válido
            try:
                json_str = json.dumps(json_final, indent=2, ensure_ascii=False)
                json.loads(json_str)  # Testa parse
            except Exception as e:
                logger.error(f"[ADA TOOL] ❌ JSON inválido: {e}")
                return f"ERRO: JSON gerado está malformado: {str(e)}"
            
            # Verifica se usuário está confirmando ou se é primeira vez mostrando o JSON
            # Usa a variável esta_confirmando definida no início
            
            # PROTEÇÃO CRÍTICA: Se marcou reprocessar_apos_alteracao, NUNCA envia - sempre mostra resumo
            if merged.get('reprocessar_apos_alteracao'):
                logger.info("[ADA TOOL] 🔄 Reprocessando após alteração - mostrando novo resumo...")
                merged.pop('reprocessar_apos_alteracao', None)  # Remove flag de reprocessamento
                merged['aguardando_confirmacao'] = True  # Marca que está aguardando nova confirmação
                self._save_pending_data(merged)
                
                # Formata dados de forma legível
                resumo_contrato = self._formatar_resumo_contrato(json_final)
                
                # IMPRIME NO CONSOLE para garantir que usuário veja (independente do LLM)
                print("\n" + "="*80, flush=True)
                print("📝 RESUMO ATUALIZADO (após alteração):", flush=True)
                print("="*80, flush=True)
                print(resumo_contrato, flush=True)
                print("\n✅ **Os dados estão corretos agora?**", flush=True)
                print("   • Digite **SIM** para enviar para a API", flush=True)
                print("   • Ou informe o campo que deseja alterar (ex: 'mudar quantidade para 50000')", flush=True)
                print("   • Ou adicione informações extras:", flush=True)
                print("     - 'adicione pilha passada como sim'", flush=True)
                print("     - 'inclua incoterm FOB'", flush=True)
                print("     - 'adicione nota: acompanhar embarque'", flush=True)
                print("="*80 + "\n", flush=True)
                
                return f"AGUARDANDO_CONFIRMACAO: Os dados foram atualizados e exibidos no console. Pergunte ao usuário se ele confirma o envio (SIM), se deseja alterar algo, ou se quer adicionar informações extras."
            
            elif esta_confirmando:
                # Usuário JÁ viu o JSON e confirmou - ENVIAR PARA API
                logger.info("[ADA TOOL] 📋 Enviando contrato confirmado para API...")
                
                # Remove campos de descrição antes de enviar (são apenas para exibição no resumo)
                campos_apenas_exibicao = [
                    'descricaoEmbalagem', 
                    'descricaoPadraoQualidade', 
                    'descricaoModalidadePagamento',
                    'descricaoCondicaoEntrega',
                    'descricaoMoedaFixacao',
                    'descricaoTipoContrato',
                    'descricaoCondicaoPeso',
                    'descricaoCondicaoPagamento',
                    'descricaoArmazemPreparo',
                    'descricaoProdutoExportacao',
                    'descricaoResponsavelDocumento',
                    'descricaoEmbarcador',
                    'descricaoIncoterm',
                    'descricaoArmazemDestino',
                    'descricaoVendedor',
                    'descricaoSpot',
                    'descricaoBolsaFixacao'
                ]
                json_para_api = {k: v for k, v in json_final.items() if k not in campos_apenas_exibicao}
                
                # Remove campos de descrição de dentro de fixacaoContrato
                if 'fixacaoContrato' in json_para_api and json_para_api['fixacaoContrato']:
                    for fix in json_para_api['fixacaoContrato']:
                        # Remove descrições da fixação
                        fix.pop('descricaoTipoPrecoFixacao', None)
                        fix.pop('descricaoTipoValor', None)
                        fix.pop('descricaoFixadorPreco', None)
                
                # Remove campos de descrição de dentro de comissaoContrato
                if 'comissaoContrato' in json_para_api and json_para_api['comissaoContrato']:
                    for com in json_para_api['comissaoContrato']:
                        # Remove descrições da comissão
                        com.pop('descricaoTipoComissao', None)
                        # Remove nome (API só precisa código e loja)
                        com.pop('nomeAgenteExportacao', None)
                
                json_str_api = json.dumps(json_para_api, indent=2, ensure_ascii=False)
                
                # Log e print para visibilidade
                logger.info("=" * 80)
                logger.info("📋 ENVIANDO CONTRATO PARA API:")
                logger.info("=" * 80)
                logger.info(json_str_api)
                logger.info("=" * 80)
                
                print("\n" + "=" * 80, flush=True)
                print("📋 ENVIANDO CONTRATO PARA API ADA:", flush=True)
                print("=" * 80, flush=True)
                print(json_str_api, flush=True)
                print("=" * 80 + "\n", flush=True)
                
                # Envia para API
                try:
                    loop = asyncio.get_running_loop()
                    import nest_asyncio
                    nest_asyncio.apply()
                    result = asyncio.run(ada_api_client.criar_contrato_venda(json_para_api))
                except RuntimeError:
                    result = asyncio.run(ada_api_client.criar_contrato_venda(json_para_api))
                except ImportError:
                    result = asyncio.run(ada_api_client.criar_contrato_venda(json_para_api))
                
                # Limpa estado
                self._clear_pending_data()
                
                logger.info(f"[ADA TOOL] ✅ Contrato criado com sucesso!")
                
                # Extrai número do contrato para destacar
                numero_contrato = result.get('numeroContrato') or result.get('numero') or result.get('contrato')
                mensagem_api = result.get('message', '')
                
                msg_sucesso = "CONTRATO_CRIADO_SUCESSO:\n\n"
                msg_sucesso += "🎉 **CONTRATO CRIADO COM SUCESSO!** 🎉\n\n"
                
                if numero_contrato:
                    msg_sucesso += f"📋 **NÚMERO DO CONTRATO: {numero_contrato}**\n\n"
                
                if mensagem_api:
                    msg_sucesso += f"✅ {mensagem_api}\n\n"
                
                # Adiciona detalhes completos
                msg_sucesso += f"Detalhes da resposta da API:\n{json.dumps(result, indent=2, ensure_ascii=False)}"
                
                return msg_sucesso
            
            elif not merged.get('aguardando_confirmacao', False):
                # Primeira vez (ou pós-alteração) - salva flag e mostra JSON para confirmação
                merged['aguardando_confirmacao'] = True
                self._save_pending_data(merged)
                
                logger.info("[ADA TOOL] 📋 Aguardando confirmação do usuário")
                
                # Formata dados de forma legível
                resumo_contrato = self._formatar_resumo_contrato(json_final)
                
                # IMPRIME NO CONSOLE para garantir que usuário veja (independente do LLM)
                print("\n" + "="*80, flush=True)
                print(resumo_contrato, flush=True)
                print("\n✅ **Os dados estão corretos?**", flush=True)
                print("   • Digite **SIM** para enviar para a API", flush=True)
                print("   • Ou informe o campo que deseja alterar (ex: 'mudar quantidade para 50000')", flush=True)
                print("   • Ou adicione informações extras:", flush=True)
                print("     - 'adicione pilha passada como sim'", flush=True)
                print("     - 'inclua incoterm FOB'", flush=True)
                print("     - 'adicione nota: acompanhar embarque'", flush=True)
                print("="*80 + "\n", flush=True)
                
                return f"AGUARDANDO_CONFIRMACAO: Os dados do contrato foram exibidos no console. Pergunte ao usuário se ele confirma o envio (SIM), se deseja alterar algo, ou se quer adicionar informações extras."
            
            else:
                # Se chegou aqui com aguardando_confirmacao=True mas não é confirmação nem alteração,
                # LLM provavelmente chamou a tool sem parâmetros (edge case)
                logger.warning("[ADA TOOL] ⚠️ Edge case: aguardando_confirmacao=True mas tool chamada sem parâmetros")
                logger.warning("[ADA TOOL] 💡 Possível causa: LLM não passou nenhum campo quando usuário disse 'sim'")
                # NÃO remove aguardando_confirmacao - mantém o estado
                # Retorna instrução MUITO CLARA para LLM usar confirmar_envio=True
                return "AGUARDANDO_CONFIRMACAO_EXPLÍCITA: Você DEVE chamar a tool novamente com o parâmetro confirmar_envio=True se o usuário confirmou (disse SIM/OK/ENVIAR). Se o usuário quer alterar algo, passe o campo e novo valor. NUNCA chame a tool sem parâmetros!"
            

            
        except Exception as e:
            logger.error(f"[ADA TOOL] Erro ao criar contrato: {e}")
            # NÃO limpa pending data no erro — dados permanecem para próxima tentativa
            return f"ERRO_CRIACAO: Erro ao criar contrato: {str(e)}"

    def get_tool(self) -> StructuredTool:
        """Retorna a StructuredTool do LangChain para criação de contratos"""
        return StructuredTool.from_function(
            func=self.criar_contrato_venda,
            name="criar_contrato_venda_exportacao",
            description=(
                "Cria/registra NOVOS contratos de venda/exportação via sistema ADA.\n\n"
                "QUANDO USAR:\n"
                "- criar contrato, novo contrato, adicionar contrato, registrar venda\n\n"
                "PROTOCOLO:\n"
                "1. Usuário pede para criar contrato: chame IMEDIATAMENTE com os dados fornecidos\n"
                "2. Tool retorna PRECISA_PERGUNTAR: pergunte ao usuário (máximo 3 por vez)\n"
                "3. Usuário responde: chame novamente APENAS com os dados NOVOS\n"
                "4. Tool retorna AGUARDANDO_CONFIRMACAO: usuário viu resumo, aguarde confirmação\n"
                "5. Usuário confirma (sim/enviar/ok): chame com confirmar_envio=True\n"
                "6. Usuário quer alterar: chame com o campo e novo valor\n"
                "7. Repita até retornar CONTRATO_CRIADO_SUCESSO\n\n"
                "CONFIRMAÇÃO (CRÍTICO):\n"
                "- Se usuário confirmou (SIM/OK/ENVIAR/PODE ENVIAR/MANDA): confirmar_envio=True\n"
                "- Exemplo: criar_contrato_venda_exportacao(confirmar_envio=True)\n"
                "- NUNCA chame a tool sem parâmetros!\n\n"
                "ALTERAÇÃO:\n"
                "- Se usuário quer alterar: passe o campo e novo valor\n"
                "- Exemplo: criar_contrato_venda_exportacao(quantidade_kg=30000)\n\n"
                "ADIÇÃO DE CAMPOS OPCIONAIS:\n"
                "- Após confirmação inicial, usuário pode adicionar campos extras\n"
                "- Exemplos: pilha_passada='S', notas='acompanhar embarque', incoterm='FOB'\n"
                "- Campos S/N: pilha_passada, contrato_liberado (aceita S/N ou Sim/Não)\n"
                "- Campos texto: notas, alerta, descricao_qualidade, referencia_cliente, etc\n"
                "- Quando usuário disser 'adicione X', 'inclua Y': passe o campo correspondente\n\n"
                "DADOS DE FIXAÇÃO:\n"
                "- Formato: fixacao_contrato_json='[{\"sacas\": 300, \"tipo_preco\": \"A\", \"referencia\": 400}]'\n\n"
                "DADOS DE COMISSÃO:\n"
                "- Formato: comissao_contrato_json='[{\"nome_agente\": \"NOME DO AGENTE\", \"percentual\": 0.5, \"tipo\": \"LIB\"}]'\n"
                "- Use 'nome_agente' (sistema busca código/loja automaticamente) OU 'codigo_agente'+'loja_agente' se fornecido\n"
                "- Extraia nome_agente, percentual e tipo da resposta do usuário\n\n"
                "IMPORTANTE: A tool ACUMULA dados via Redis. Passe SOMENTE dados NOVOS."
            )
        )


def create_ada_tools(session_id: str) -> ADATools:
    """Factory function para criar ADATools com session_id"""
    return ADATools(session_id=session_id)
