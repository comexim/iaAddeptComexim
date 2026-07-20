"""
Orquestrador principal do agente usando LangGraph
"""
import re
import json
import logging
import unicodedata
from typing import Optional, Sequence
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.supabase_client import supabase_client
from app.models.user import UserPermissions
from app.agents.sql_tools import SQLTools
from app.prompts.system_prompt import get_system_prompt, get_current_date_info
from app.services.preference_learning import preference_learning

logger = logging.getLogger(__name__)


def _normalize_query_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _ensure_fixacao_optional_hint(output: str) -> str:
    """Garante o aviso dos campos opcionais ao solicitar o valor obrigatorio."""
    normalized = _normalize_query_text(output)
    asking_value = (
        "valor da fixacao" in normalized
        and "confirma" not in normalized
        and "resumo" not in normalized
        and any(term in normalized for term in ("preciso", "informe", "qual", "poderia"))
    )
    if asking_value and "diferencial" not in normalized:
        return (
            output.rstrip()
            + "\n\nSe desejar, você também pode informar o diferencial, o tipo do valor e o fixador do preço. "
              "Esses dados são opcionais; somente o valor da fixação é necessário para continuar."
        )
    return output

# Palavras-chave que indicam intenção de criar contrato
_CRIAR_CONTRATO_KEYWORDS = re.compile(
    r'criar\s+contrato|novo\s+contrato|adicionar\s+contrato|registrar\s+venda|'
    r'fazer\s+contrato|cadastrar\s+contrato|registrar\s+contrato|criar\s+um\s+contrato|'
    r'quero\s+criar|preciso\s+criar',
    re.IGNORECASE
)

_PURE_CONFIRMATION = re.compile(
    r'^\s*(?:sim|s|ok|confirmo|confirmar|sim[,.]?\s*confirmo|pode\s+enviar|'
    r'pode\s+mandar|envie|manda|est[aá]\s+correto|correto|certo)\s*[.!]?\s*$',
    re.IGNORECASE,
)

# System prompt enxuto para o fluxo de criação de contrato
_CONTRATO_SYSTEM_PROMPT = """Você cria contratos de venda/exportação da Comexim.

FLUXO:
1. Chame criar_contrato_venda_exportacao com dados fornecidos
   ✅ EXTRAÇÃO GANANCIOSA: Se usuário fornecer VÁRIOS dados de uma vez, extraia TODOS!
   ✅ Não limite a 3 campos - passe TUDO que conseguir identificar
2. Se retornar "PRECISA_PERGUNTAR:", pergunte campos faltantes (máximo 3 por vez), numerados
3. Ao receber resposta, chame tool com APENAS dados NOVOS
4. Se retornar "AGUARDANDO_CONFIRMACAO:", os dados JÁ FORAM EXIBIDOS no console - apenas pergunte: "Está tudo correto? (Digite SIM para confirmar ou informe o que alterar)"
5. Quando aguardando confirmação, ANTES de chamar tool, analise a resposta do usuário:
   
   🚨 PRIORIDADE 1 - DETECTAR ADIÇÃO DE CAMPOS NOVOS (SEMPRE VERIFICAR PRIMEIRO!):
   Se a frase contém qualquer verbo de adição + nome de campo:
   • Verbos: "adicionar", "adicione", "adiciona", "incluir", "inclua", "inclui", "colocar", "coloque", "coloca"
   • Variantes: "quero adicionar", "vou adicionar", "preciso adicionar", "quero incluir", "vou incluir"
   → SEMPRE chame tool COM o parâmetro do campo específico
   → Exemplos:
     - "quero adicionar pilha passada como não" → pilha_passada="N"
     - "adicione pilha passada como sim" → pilha_passada="S"
     - "vou incluir incoterm FOB" → incoterm="FOB"
     - "preciso adicionar nota: urgente" → notas="urgente"
   
   🚨 PRIORIDADE 2 - DETECTAR REMOÇÃO:
   Se menciona remover/retirar/excluir/deletar itens de fixação ou comissão:
   • Verbos: "remover", "retirar", "excluir", "deletar", "apagar", "tirar"
   • Identifique o ÍNDICE (posição) do item: "primeiro", "segundo", "terceiro", "quarto", etc.
   • Ou número direto: "item 1", "item 2", "3", etc.
   → REMOÇÃO DE FIXAÇÃO: remover_fixacao_indice=N (onde N é a posição que o usuário mencionou)
   → REMOÇÃO DE COMISSÃO: remover_comissao_indice=N
   → Exemplos:
     - "retire o terceiro item da fixação" → remover_fixacao_indice=3
     - "remova a segunda comissão" → remover_comissao_indice=2
     - "apague a fixação 1" → remover_fixacao_indice=1
   
   🚨 PRIORIDADE 3 - DETECTAR ALTERAÇÃO:
   Se menciona alterar/mudar/corrigir campos existentes:
   • Verbos: "alterar", "mudar", "corrigir", "trocar", "ajustar", "modificar"
   → ALTERAÇÃO DE FIXAÇÃO:
     - Identifique o ÍNDICE do item: "primeiro", "segundo", "item 1", "item 2", etc.
     - Monte JSON com APENAS os campos que mudam
     - Passe alterar_fixacao_indice=N junto com fixacao_contrato_json
     - Exemplo: "altere o mês do item 2 para 07/2026" → alterar_fixacao_indice=2, fixacao_contrato_json='[{"mes_ano":"07/2026"}]'
   → ALTERAÇÃO DE COMISSÃO:
     - Identifique o ÍNDICE do item: "primeira", "segunda", "item 1", "item 2", etc.
     - Monte JSON com APENAS os campos que mudam
     - Passe alterar_comissao_indice=N junto com comissao_contrato_json
   → ALTERAÇÃO DE CONTRATO (outros campos): envie o campo específico
   
   🚨 PRIORIDADE 4 - DETECTAR CONFIRMAÇÃO (SÓ SE NÃO FOR ADIÇÃO, REMOÇÃO OU ALTERAÇÃO!):
   Apenas se a mensagem for SOMENTE palavras de confirmação, sem verbos de ação:
   • Palavras aceitas: "sim", "ok", "confirmar", "pode enviar", "está correto", "correto", "certo"
   → Chame tool SEM parâmetros para enviar

6. Repita até "CONTRATO_CRIADO_SUCESSO"

7. Quando receber "CONTRATO_CRIADO_SUCESSO":
   ✅ SEMPRE informe o NÚMERO DO CONTRATO ao usuário de forma destacada
   ✅ A resposta da tool contém "NÚMERO DO CONTRATO: XXX" - SEMPRE mostre esse número!
   ✅ Exemplo: "✅ Contrato criado com sucesso! Número do contrato: 12345"

EXEMPLOS DE CHAMADAS DA TOOL:

Situação 1: Usuário diz "quero adicionar pilha passada como não"
→ ANÁLISE: contém "quero adicionar" (verbo de adição) + "pilha passada" (campo) + "não" (valor)
→ AÇÃO: Chame tool COM parâmetro
→ CHAMADA: criar_contrato_venda_exportacao(pilha_passada="N")

Situação 2: Usuário diz "adicione nota: verificar documentos"
→ ANÁLISE: contém "adicione" (verbo de adição) + "nota" (campo) + valor
→ AÇÃO: Chame tool COM parâmetro
→ CHAMADA: criar_contrato_venda_exportacao(notas="verificar documentos")

Situação 3: Usuário diz "inclua incoterm FOB"
→ ANÁLISE: contém "inclua" (verbo de adição) + "incoterm" (campo) + "FOB" (valor)
→ AÇÃO: Chame tool COM parâmetro
→ CHAMADA: criar_contrato_venda_exportacao(incoterm="FOB")

Situação 4: Usuário diz "adicione pilha passada como sim"
→ ANÁLISE: contém "adicione" (verbo de adição) - "sim" é VALOR do campo, NÃO é confirmação!
→ AÇÃO: Chame tool COM parâmetro
→ CHAMADA: criar_contrato_venda_exportacao(pilha_passada="S")

Situação 5: Usuário diz apenas "sim"
→ ANÁLISE: APENAS palavra de confirmação, sem verbos de ação, sem nomes de campos
→ AÇÃO: Chame tool SEM parâmetros para confirmar envio
→ CHAMADA: criar_contrato_venda_exportacao()

Situação 6: Usuário diz "ok" ou "confirmar" ou "pode enviar"
→ ANÁLISE: Palavras de confirmação PURAS
→ AÇÃO: Chame tool SEM parâmetros
→ CHAMADA: criar_contrato_venda_exportacao()

Situação 7: Usuário diz "retire o terceiro item da fixação"
→ ANÁLISE: contém "retire" (verbo de remoção) + "terceiro" (índice 3) + "fixação"
→ AÇÃO: Chame tool com parâmetro de remoção de fixação
→ CHAMADA: criar_contrato_venda_exportacao(remover_fixacao_indice=3)

Situação 8: Usuário diz "remova a segunda comissão"
→ ANÁLISE: contém "remova" (verbo de remoção) + "segunda" (índice 2) + "comissão"
→ AÇÃO: Chame tool com parâmetro de remoção de comissão
→ CHAMADA: criar_contrato_venda_exportacao(remover_comissao_indice=2)

Situação 9: Usuário diz "apague a fixação 1" ou "delete o item 1 da fixação"
→ ANÁLISE: contém verbo de remoção + número direto + "fixação"
→ AÇÃO: Chame tool com parâmetro de remoção de fixação
→ CHAMADA: criar_contrato_venda_exportacao(remover_fixacao_indice=1)

Situação 10: Usuário diz "altere o mês de fixação do item 2 para 07/2026"
→ ANÁLISE: contém "altere" (verbo de alteração) + "item 2" (índice) + "mês" (campo) + valor
→ AÇÃO: Monte JSON com apenas o campo que muda + passe o índice
→ CHAMADA: criar_contrato_venda_exportacao(alterar_fixacao_indice=2, fixacao_contrato_json='[{"mesAnoFixacao":"07/2026"}]')

Situação 11: Usuário diz "mude o percentual da comissão 1 para 1.5%"
→ ANÁLISE: contém "mude" (verbo de alteração) + "comissão 1" (índice) + "percentual" (campo) + valor
→ AÇÃO: Monte JSON com apenas o campo que muda + passe o índice
→ CHAMADA: criar_contrato_venda_exportacao(alterar_comissao_indice=1, comissao_contrato_json='[{"percentualComissao":1.5}]')

Situação 12: Usuário diz "altere as sacas do segundo item de fixação para 400"
→ ANÁLISE: contém "altere" + "segundo" (índice 2) + "sacas" (campo) + valor
→ AÇÃO: Monte JSON + passe o índice
→ CHAMADA: criar_contrato_venda_exportacao(alterar_fixacao_indice=2, fixacao_contrato_json='[{"sacasFixacao":400}]')

NORMALIZAÇÃO AUTOMÁTICA DE VALORES:
✅ O sistema normaliza automaticamente, NÃO pergunte confirmação:
   • "E" ou "Exportador" ou "exportação" → aceito como Exportador
   • "I" ou "Importador" ou "importação" → aceito como Importador  
   • "S" ou "Sim" → aceito como S
   • "N" ou "Não" → aceito como N
   • "A" ou "a fixar" → aceito como A (tipo de preço)
   • "F" ou "fixado" → aceito como F (tipo de preço)
✅ NUNCA pergunte "E refere-se a Exportador?" - sistema já normaliza!

IMPORTANTE - DADOS DE FIXAÇÃO:
📊 A FIXAÇÃO é um ARRAY JSON separado do contrato principal!
✅ Formato: fixacao_contrato_json='[{"sacas": 300, "tipo_preco": "A", "referencia": 400, "fixador_preco": "E", "mes_ano_fixacao": "07/2026"}]'
✅ Campos da fixação (TODOS obrigatórios):
   - sacas ou sacasFixacao: quantidade de sacas a fixar
   - tipo_preco ou tipoPrecoFixacao: "A" (a fixar) ou "F" (fixado)
   - referencia ou referenciaBolsaNy: referência da bolsa NY (número)
   - fixador_preco ou fixadorPreco: "E" (Exportador) ou "I" (Importador)
   - mes_ano_fixacao ou mesAnoFixacao: mês/ano (ex: "07/2026")
   - tipo_valor ou tipoValor: tipo de valor (ex: "CTS/LB", "US$ KG", "US$ 50KG", "US$ TON")
      * Passe EXATAMENTE o que o usuário informar - NÃO interprete ou abrevie
      * Exemplos: "US$ KG" (não "K"), "CTS/LB" (não "C"), "US$ TON" (não "T")
✅ SEMPRE pergunte ao usuário sobre fixação se ele não mencionar!
❌ NUNCA confunda campos de fixação com campos do contrato:
   - tipoPrecoFixacao (na fixação) ≠ tipo_contrato (no contrato)
   - sacasFixacao (na fixação) ≠ quantidade_embalagem (no contrato)

IMPORTANTE - DADOS DE COMISSÃO:
💵 A COMISSÃO é um ARRAY JSON separado do contrato principal!
✅ Formato com código E loja: comissao_contrato_json='[{"codigo_agente": "AG000001", "loja_agente": "0001", "percentual": 0.5, "tipo": "LIB"}]'
✅ Formato com nome: comissao_contrato_json='[{"nome_agente": "CAFE RESPONSAVEL", "percentual": 0.5, "tipo": "LIB"}]'

⚠️ ATENÇÃO - CÓDIGO vs NOME:
• Se usuário disser "código X, loja Y" → use codigo_agente E loja_agente (AMBOS obrigatórios!)
• Se usuário disser apenas o nome → use nome_agente
• NUNCA envie codigo_agente sem loja_agente!
• ⚠️ NUNCA invente códigos de agente - apenas use o que o usuário informar!

✅ Campos da comissão:
   OPÇÃO 1 (com código): codigo_agente + loja_agente + percentual + tipo
   OPÇÃO 2 (com nome): nome_agente + percentual + tipo

✅ MÚLTIPLAS COMISSÕES:
Se usuário mencionar VÁRIOS agentes, crie array com TODOS!
Exemplo: "agente CAFE RESPONSAVEL, percentual 0.65, tipo SC 59 KG. agente CORRETORA SANTOS, percentual 0.8, tipo LIB"
→ Monte:
comissao_contrato_json='[
  {"nome_agente": "CAFE RESPONSAVEL", "percentual": 0.65, "tipo": "SC 59 KG"},
  {"nome_agente": "CORRETORA SANTOS", "percentual": 0.8, "tipo": "LIB"}
]'

ALTERAÇÃO DE FIXAÇÃO:
✅ Para alterar UM campo da fixação, envie APENAS o campo alterado no JSON
✅ O sistema faz MERGE automático com os dados existentes (preserva os outros campos)
✅ Exemplo: mudar referência para 320 → fixacao_contrato_json='[{"referencia": 320}]'
❌ NÃO precisa reenviar todos os campos da fixação!

CAMPOS OPCIONAIS ADICIONAIS:
📋 O usuário pode adicionar informações extras APÓS a confirmação inicial.
Quando o sistema perguntar "Deseja adicionar mais alguma informação?", aceite:

• Descrições: descricao_qualidade, descricao_detalhada, alerta, notas
• Referências: referencia_cliente, referencia_corretor
• Bancários: codigo_banco, agencia_bancaria, digito_verificador_agencia, conta_corrente, digito_verificador_conta_corrente
• Logística: condicao_pagamento, armazem_preparo, armazem_destino, produto_exportacao, periodo_embarque, variacao_peso
• Operacionais: tipo_venda, incoterm, responsavel_documento, embarcador, vendedor, certificador
• Valores: total_cost_ddp, dif_cash_against, diferencial_cliente_final
• Cliente Final: codigo_cliente_final, loja_cliente_final, nome_cliente_final
• Status: contrato_liberado, pilha_passada, sample_conditions, spot

⚠️ REGRA CRÍTICA DE ADIÇÃO:
Se a frase do usuário contém qualquer variante de verbo de adição + nome do campo:
→ SEMPRE chame a tool COM o parâmetro do campo, MESMO que a frase contenha "sim", "ok", etc!
→ "sim" ou "não" nesse contexto é o VALOR do campo, NÃO é confirmação de envio!

VERBOS E VARIANTES QUE INDICAM ADIÇÃO:
• Imperativo: "adicione", "inclua", "coloque", "insira", "ponha"
• Infinitivo: "adicionar", "incluir", "colocar", "inserir", "pôr"
• Presente: "adiciono", "adiciona", "incluo", "inclui", "coloco", "coloca"
• Com auxiliares: "quero adicionar", "vou adicionar", "preciso adicionar", "vou incluir", "quero colocar"
• Expressões: "gostaria de adicionar", "pode adicionar", "pode incluir"

✅ Passe exatamente com os nomes em snake_case: descricao_qualidade, referencia_cliente, etc.
✅ Exemplo 1: "adicione a nota: acompanhar embarque" → notas="acompanhar embarque"
✅ Exemplo 2: "adicione pilha passada como sim" → pilha_passada="S" ⚠️ NÃO CONFUNDA COM CONFIRMAÇÃO!
✅ Exemplo 3: "quero adicionar pilha passada como não" → pilha_passada="N" ⚠️ "não" é VALOR!
✅ Exemplo 4: "inclua incoterm FOB" → incoterm="FOB"
✅ Exemplo 5: "coloque alerta: urgente" → alerta="urgente"
✅ Exemplo 6: "vou adicionar contrato liberado como sim" → contrato_liberado="S"
✅ Exemplo 7: "preciso incluir notas: verificar documentação" → notas="verificar documentação"
✅ Campos S/N (pilha_passada, contrato_liberado): aceita "S", "N", "Sim", "Não" (sistema normaliza automaticamente)

IMPORTANTE - CONFIRMAÇÃO:
✅ NÃO REPITA os dados do contrato na sua resposta - eles já foram exibidos no console
✅ Apenas pergunte: "Os dados estão corretos? (SIM para enviar ou informe o que alterar)"
✅ Quando aguardando confirmação, SEMPRE verifique PRIMEIRO se é adição/alteração (veja FLUXO passo 5)
✅ SÓ chame tool sem parâmetros se for confirmação PURA (ex: apenas "sim", "ok", "confirmar")
✅ Se há QUALQUER verbo de ação (adicionar, incluir, alterar, mudar), chame tool COM parâmetros!

REGRAS CRÍTICAS:
❌ NUNCA use codigo_embalagem como codigo_cliente - são campos DIFERENTES
❌ NUNCA use condicao_peso (NDW/GW) em condicao_entrega (FOB/EMB/CIF/ENT)
❌ NUNCA confunda tipo_contrato com tipoPrecoFixacao
❌ NUNCA confunda quantidade_embalagem com sacasFixacao
❌ NUNCA peça confirmação de valores já normalizados automaticamente
✅ SEMPRE pergunte separadamente:
   - "Qual o CÓDIGO DO CLIENTE?" (ex: EX288915O)
   - "Qual a EMBALAGEM?" (ex: BIG BAG 1000KG ou 00316)
   - "Qual a CONDIÇÃO DE ENTREGA?" (ex: FOB, EMB, CIF, ENTREGA)
   - "Qual a CONDIÇÃO DE PESO?" (ex: NET DELIVERED WEIGHT, NET LANDED WEIGHT, GROSS WEIGHT)
   - "Qual a FIXAÇÃO?" (sacas, tipo de preço, referência)

RESOLUÇÃO DE CAMPOS:
✅ O sistema resolve AUTOMATICAMENTE descrições para códigos
✅ Sempre passe para a tool exatamente o que o usuário disse, NÃO interprete ou abrevie
✅ Exemplos:
   - Usuário: "NET LANDED WEIGHT" → passe: condicao_peso="NET LANDED WEIGHT" (NÃO "NLW" ou "NDW")
   - Usuário: "DOLAR" → passe: moeda_fixacao="DOLAR" (NÃO "USD")
   - Usuário: "GRINDERS LAVADOS" → passe: padrao_qualidade="GRINDERS LAVADOS" (NÃO "GRDLAV")
   - Usuário: "US$ KG" → passe: tipo_valor="US$ KG" (NÃO "K" ou "D")
   - Usuário: "CTS/LB" → passe: tipo_valor="CTS/LB" (NÃO "C")
✅ O resolver busca na API e retorna o código correto automaticamente

EXEMPLO DE MENSAGEM LONGA:
Se usuário disser: "Cliente ARABIGA, quantidade 40.033, condição entrega, mês 06/2026, modalidade in trust, 
embalagem ALPHA BAG, padrão fundinho, moeda dolar, tipo EUROPEAN CONTRACT, condição REWEIGHTS, 2 containers, 
50 embalagens, dólar 5.22, não exige EUDR e OTA, não requer amostra, peneiras 14 e grinder, data 09/2026, 
300 sacas, mês fixação 07/2026, tipo a fixar, fixador importador, tipo valor US$ KG, referência 400, 
agente CAFE RESPONSAVEL, percentual 0.65, tipo comissão SC 59 KG"

✅ Extraia TUDO de uma vez:
criar_contrato_venda_exportacao(
    nome_cliente="ARABIGA",
    quantidade_kg=40.033,
    condicao_entrega="entrega",
    mes_embarque="06/2026",
    modalidade_pagamento="in trust",
    codigo_embalagem="ALPHA BAG",
    padrao_qualidade="fundinho",
    moeda_fixacao="dolar",
    tipo_contrato="EUROPEAN CONTRACT",
    condicao_peso="REWEIGHTS",
    quantidade_container=2,
    quantidade_embalagem=50,
    taxa_dolar=5.22,
    exige_eudr="N",
    exige_ota="N",
    amostra_pre_embarque="N",
    peneira_14=True,
    peneira_grinder=True,
    data_previsao_entrega="09/2026",
    fixacao_contrato_json='[{"sacas": 300, "mes_ano_fixacao": "07/2026", "tipo_preco": "a fixar", "fixador_preco": "importador", "tipo_valor": "US$ KG", "referencia": 400}]',
    comissao_contrato_json='[{"nome_agente": "CAFE RESPONSAVEL", "percentual": 0.65, "tipo": "SC 59 KG"}]'
)

⚠️ ATENÇÃO - CAMPOS OBRIGATÓRIOS DE FIXAÇÃO:
Quando tipo_preco = "a fixar", o JSON de fixação DEVE ter TODOS estes campos:
• sacas (ou sacas_fixacao) = número de sacas
• mes_ano_fixacao = mês/ano no formato "MM/AAAA" ⚠️ USE O NOME COMPLETO! NUNCA abrevie para "mes"!
• tipo_preco = "a fixar" ou "fixado" ⚠️ CAMPO OBRIGATÓRIO!
• fixador_preco = "importador" ou "exportador"
• tipo_valor = tipo de valor (ex: "US$ KG", "CTS/LB")
• referencia = valor de referência da bolsa

⚠️ SE FALTAR tipo_preco ou mes_ano_fixacao, o sistema VAI FALHAR!

Exemplo COMPLETO (com TODOS os 6 campos - observe "mes_ano_fixacao" completo):
fixacao_contrato_json='[{"sacas": 300, "mes_ano_fixacao": "07/2026", "tipo_preco": "a fixar", "fixador_preco": "importador", "tipo_valor": "US$ KG", "referencia": 400}]'

⚠️ CAMPO CRÍTICO - NUNCA ESQUEÇA O NOME COMPLETO:
• ✅ CORRETO: "mes_ano_fixacao": "07/2026"
• ❌ ERRADO: "mes": "07/2026"
• ❌ ERRADO: "mes_ano": "07/2026"

Quando usuário diz:
• "tipo a fixar" → extraia: "tipo_preco": "a fixar"
• "mês 07/2026" → extraia: "mes_ano_fixacao": "07/2026"  ← USE O NOME COMPLETO!
• "fixador é importador" → extraia: "fixador_preco": "importador"

⚠️ MÚLTIPLAS COMISSÕES:
Para adicionar várias comissões, crie um array com todos os agentes.
ATENÇÃO: Só crie múltiplas comissões se o usuário EXPLICITAMENTE mencionar vários agentes!

⚠️ REGRA IMPORTANTE - CÓDIGO vs NOME:
• Se usuário disser "código X, loja Y" → SEMPRE use codigo_agente + loja_agente (AMBOS!)
• Se usuário disser apenas nome → use nome_agente
• NUNCA envie codigo_agente sem loja_agente - isso causa erro de parsing!
• ⚠️ NUNCA INVENTE códigos de agente - apenas extraia do que o usuário disse!

Exemplo com 2 agentes (ambos com nome):
comissao_contrato_json='[
  {"nome_agente": "CAFE RESPONSAVEL", "percentual": 0.65, "tipo": "SC 59 KG"},
  {"nome_agente": "CORRETORA XYZ", "percentual": 0.3, "tipo": "LIB"}
]'

Exemplo com 2 agentes (ambos com código - SOMENTE se usuário informar):
comissao_contrato_json='[
  {"codigo_agente": "AG000001", "loja_agente": "0001", "percentual": 0.5, "tipo": "SC 59 KG"},
  {"codigo_agente": "AG000002", "loja_agente": "0001", "percentual": 0.3, "tipo": "LIB"}
]'

⚠️ NUNCA use o código/loja do CLIENTE como código/loja de AGENTE de comissão!
⚠️ NÃO invente comissões - apenas extraia o que o usuário REALMENTE disse!

✅ NÃO limite a 3 campos - passe TUDO que conseguir identificar!
✅ Só pergunte 3 por vez se faltarem dados obrigatórios após primeira chamada"""


class AgentOrchestrator:
    """Orquestrador principal do agente de IA"""

    def __init__(self, user: UserPermissions, session_id: str):
        """
        Inicializa orquestrador para usuário específico

        Args:
            user: Dados e permissões do usuário
            session_id: ID da sessão (telefone)
        """
        self.user = user
        self.session_id = session_id
        self.user_preferences = None  # Carregado sob demanda
        self.system_prompt = ""  # Carregado quando agente é criado

        # Inicializa LLM
        if settings.llm_provider == "openai":
            self.llm = ChatOpenAI(
                model=settings.ai_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                api_key=settings.openai_api_key,
                max_retries=3,
                request_timeout=60.0
            )
        else:
            self.llm = ChatAnthropic(
                model=settings.ai_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                api_key=settings.anthropic_api_key
            )

        # Cria tools SQL específicas para este usuário
        sql_tools = SQLTools(user, session_id)
        self.tools = sql_tools.get_all_tools()
        
        # NOTA: ADA tool já é incluída em get_all_tools()
        
        # Guarda ADA tool separada para fluxo leve de contrato
        self._ada_tool = sql_tools.get_ada_tool()
        self._contrato_agent = None  # Agente leve criado sob demanda

        # Configura memória com Redis
        self.message_history = self._setup_memory()

        # Cria agente (será recriado quando preferências mudarem)
        self.agent = None

        logger.info(f"Orquestrador inicializado para usuário {user.nome} (sessão: {session_id})")

    def _is_contrato_flow(self, message: str) -> bool:
        """Detecta se estamos no fluxo de criação de contrato.
        
        Retorna True se:
        - A mensagem contém palavras-chave de criação de contrato, OU
        - Já existe um contrato pendente no Redis para esta sessão
        """
        # 1. Mensagem explícita de criação
        if _CRIAR_CONTRATO_KEYWORDS.search(message):
            logger.info("[CONTRATO FLOW] Detectado por palavras-chave na mensagem")
            return True
        
        # 2. Contrato pendente no Redis (continuação de conversa)
        try:
            from app.agents.ada_tools import create_ada_tools
            ada = create_ada_tools(session_id=self.session_id)
            pending = ada._load_pending_data()
            if pending:
                logger.info(f"[CONTRATO FLOW] Detectado por dados pendentes no Redis: {list(pending.keys())}")
                return True
        except Exception as e:
            logger.debug(f"[CONTRATO FLOW] Erro ao checar Redis: {e}")
        
        # 3. Histórico recente indica fluxo de contrato
        try:
            history = self.message_history.messages
            for msg in reversed(history[-4:]):  # Últimas 2 interações
                if isinstance(msg, AIMessage) and isinstance(msg.content, str):
                    if "criar o contrato" in msg.content.lower() or "preciso que informe" in msg.content.lower():
                        logger.info("[CONTRATO FLOW] Detectado pelo histórico recente")
                        return True
        except Exception:
            pass
        
        return False

    def _get_contrato_agent(self):
        """Retorna agente leve só com a ADA tool (cria sob demanda)"""
        if self._contrato_agent is None:
            self._contrato_agent = create_react_agent(
                model=self.llm,
                tools=[self._ada_tool]
            )
            logger.info("[CONTRATO FLOW] Agente leve de contrato criado (1 tool)")
        return self._contrato_agent

    def _setup_memory(self) -> RedisChatMessageHistory:
        """Configura memória de conversação com Redis"""
        message_history = RedisChatMessageHistory(
            session_id=f"{self.session_id}_memory_comexim",
            url=settings.redis_url,
            ttl=settings.redis_memory_ttl
        )
        return message_history

    async def _load_user_preferences(self):
        """Carrega preferências do usuário do Supabase"""
        if not settings.enable_preference_learning:
            return

        try:
            self.user_preferences = await supabase_client.get_or_create_user_preferences(
                telefone=self.session_id,
                nome=self.user.nome,
                email=self.user.email
            )
            logger.info(f"Preferências carregadas: {self.user_preferences.get_summary()}")
        except Exception as e:
            logger.error(f"Erro ao carregar preferências: {e}")
            self.user_preferences = None

    async def _create_agent(self):
        """Cria agente LangGraph com tools e memória"""
        # Carrega preferências do usuário
        await self._load_user_preferences()

        # System prompt base
        current_date = get_current_date_info()
        base_prompt = get_system_prompt(
            user_name=self.user.nome,
            user_email=self.user.email,
            current_date=current_date
        )

        # Injeta instruções personalizadas de preferências
        if self.user_preferences:
            custom_instructions = self.user_preferences.get_custom_instructions()
            system_prompt = f"""{base_prompt}

# INSTRUÇÕES PERSONALIZADAS DO USUÁRIO

{custom_instructions}

IMPORTANTE: Siga RIGOROSAMENTE as instruções personalizadas acima ao formatar suas respostas."""
        else:
            system_prompt = base_prompt

        # Cria agente LangGraph com ReAct pattern
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools
        )

        # Salva system prompt para usar nas mensagens
        self.system_prompt = system_prompt

        return self.agent

    def _should_force_vendas_market_query(self, message: str) -> bool:
        """Evita resposta de memória para vendas de mercado interno/externo."""
        text = _normalize_query_text(message)
        mentions_sales = any(term in text for term in ("venda", "vendas", "vendemos", "vendeu", "venderam"))
        mentions_market = any(term in text for term in ("mercado interno", "mercado nacional", "mercado externo", "mercado internacional"))
        return mentions_sales and mentions_market

    def _extract_sales_period_from_message(self, message: str) -> Optional[str]:
        """Extrai período simples para pesquisa_vendas em rotas forçadas."""
        text = _normalize_query_text(message)

        year_match = re.search(r"\b(20\d{2})\b", text)
        if year_match:
            return year_match.group(1)

        for expression in (
            "este ano",
            "esse ano",
            "ano atual",
            "este mes",
            "esse mes",
            "mes atual",
            "ultimos 7 dias",
            "ultimos sete dias",
            "hoje",
            "ontem",
        ):
            if expression in text:
                return expression

        return None

    async def process_message(self, message: str) -> str:
        """
        Processa mensagem do usuário

        Args:
            message: Mensagem do usuário

        Returns:
            Resposta do agente
        """
        try:
            normalized_user_message = _normalize_query_text(message)
            new_fixacao_request = re.search(
                r'\b(?:cadastrar|inserir|registrar|lancar|fixar|adicionar)\b.*\bvalor\b.*\bcontrato\b',
                normalized_user_message,
            )
            if new_fixacao_request:
                from app.agents.fixacao_tools import FixacaoTools
                logger.info("[FIXACAO FLOW] Novo cadastro detectado; limpando operacao pendente anterior")
                FixacaoTools(self.session_id or "default").clear_pending()

            # Confirmacao de fixacao e deterministica: nao depende de o LLM
            # preencher confirmar_envio=True ao chamar a ferramenta.
            confirmation_text = _normalize_query_text(message).strip().rstrip(".! ")
            confirmation_phrases = {
                "sim", "s", "ok", "confirmo", "confirmar", "sim, confirmo", "sim confirmo",
                "pode enviar", "pode mandar", "envie", "manda", "esta correto", "correto", "certo",
            }
            if confirmation_text in confirmation_phrases:
                import asyncio
                from app.agents.fixacao_tools import FixacaoTools

                fixacao = FixacaoTools(self.session_id or "default")
                awaiting_fixacao = fixacao.is_awaiting_confirmation()
                logger.info(
                    "[FIXACAO FLOW] Mensagem de confirmacao detectada; aguardando_confirmacao=%s",
                    awaiting_fixacao,
                )
                if awaiting_fixacao:
                    logger.info("[FIXACAO FLOW] Confirmacao explicita detectada; enviando para API CMX")
                    result = await asyncio.to_thread(
                        fixacao.cadastrar_valor_contrato,
                        confirmar_envio=True,
                    )
                    if result.startswith("FIXACAO_CADASTRADA_SUCESSO:"):
                        output = "Valor do contrato cadastrado com sucesso."
                    elif result.startswith("ERRO_API:"):
                        output = result.replace("ERRO_API:", "Não foi possível concluir o cadastro:", 1).strip()
                    else:
                        output = result
                    self.message_history.add_user_message(message)
                    self.message_history.add_ai_message(output)
                    return output

            # Atualizacoes opcionais de uma fixacao pendente sao processadas
            # diretamente, sem permitir chamada da API neste mesmo turno.
            from app.agents.fixacao_tools import FixacaoTools
            fixacao_pending = FixacaoTools(self.session_id or "default")
            if fixacao_pending.is_awaiting_confirmation():
                normalized_message = _normalize_query_text(message)
                optional_updates = {}

                diferencial_match = re.search(
                    r'diferencial(?:\s+(?:de|como|e))?\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)',
                    normalized_message,
                )
                if diferencial_match:
                    optional_updates["diferencial"] = float(diferencial_match.group(1).replace(",", "."))

                if "fixador" in normalized_message and "preco" in normalized_message:
                    if re.search(r'\bimportador\b|\bcomo\s+i\b|\bfixador(?:\s+do|\s+de)?\s+preco\s*[:=]?\s*i\b', normalized_message):
                        optional_updates["fixador_preco"] = "I"
                    elif re.search(r'\bexportador\b|\bcomo\s+e\b|\bfixador(?:\s+do|\s+de)?\s+preco\s*[:=]?\s*e\b', normalized_message):
                        optional_updates["fixador_preco"] = "E"
                    elif re.search(r'\bcomo\s+f\b|\bfixador(?:\s+do|\s+de)?\s+preco\s*[:=]?\s*f\b', normalized_message):
                        optional_updates["fixador_preco"] = "F"

                if "tipo de valor" in normalized_message or "tipo do valor" in normalized_message:
                    # A tool normaliza a frase completa e envia somente C/K/5/6/T.
                    optional_updates["tipo_valor"] = message

                if optional_updates:
                    import asyncio
                    logger.info("[FIXACAO FLOW] Atualizando campos opcionais sem envio: %s", list(optional_updates))
                    result = await asyncio.to_thread(
                        fixacao_pending.cadastrar_valor_contrato,
                        **optional_updates,
                    )
                    if result.startswith("VALOR_INVALIDO:"):
                        output = result.replace("VALOR_INVALIDO:", "Não foi possível atualizar:", 1).strip()
                    else:
                        output = fixacao_pending.format_pending_summary()
                    self.message_history.add_user_message(message)
                    self.message_history.add_ai_message(output)
                    return output

            # ═══ FLUXO LEVE: Criação de contrato (só ADA tool) ═══
            if self._is_contrato_flow(message):
                logger.info(f"[CONTRATO FLOW] Usando agente leve para: {message[:80]}")
                return await self._process_contrato_message(message)

            # ═══ FLUXO NORMAL: Todas as tools ═══
            # Armazena mensagem do usuário nas tools SQL para extração de cliente
            sql_tools = SQLTools(self.user, self.session_id)

            # CONTEXTO INTELIGENTE: Se mensagem curta, concatena com última pergunta do usuário
            contextualized_query = message
            logger.info(f"[CONTEXTO] Tamanho da mensagem: {len(message)} chars: '{message}'")

            if len(message) < 40:  # Aumentado para 40 para pegar respostas curtas
                # Recupera histórico
                history_messages = self.message_history.messages
                # Procura última pergunta do usuário (HumanMessage) que não seja essa
                for msg in reversed(history_messages):
                    if isinstance(msg, HumanMessage) and len(msg.content) > 40:
                        # Encontrou pergunta anterior completa
                        contextualized_query = f"{msg.content} {message}"
                        logger.info(f"[CONTEXTO] Mensagem curta detectada! Contextualizando com pergunta anterior...")
                        logger.info(f"[CONTEXTO] Resultado: '{contextualized_query[:200]}'")
                        break

            sql_tools.user_query = contextualized_query
            sql_tools.user_query_original = message  # Query SEM contexto para filtros
            self.tools = sql_tools.get_all_tools()

            logger.info(f"Processando mensagem do usuário {self.user.nome}: {message[:100]}...")

            if self._should_force_vendas_market_query(message):
                periodo_forcado = self._extract_sales_period_from_message(message)
                if not periodo_forcado:
                    output = "De qual período você gostaria de consultar as vendas por mercado?"
                    self.message_history.add_user_message(message)
                    self.message_history.add_ai_message(output)
                    return output
                logger.info(
                    f"[FORCE TOOL] Pergunta de vendas por mercado detectada. "
                    f"Chamando pesquisa_vendas(periodo={periodo_forcado!r})"
                )
                output = sql_tools._pesquisa_vendas(periodo=periodo_forcado)
                self.message_history.add_user_message(message)
                self.message_history.add_ai_message(output)
                logger.info(f"Resposta gerada via tool forçada: {output[:100]}...")
                return output

            # 1. Detecta e aplica feedback sobre preferências
            feedbacks_detected = []
            preferences_changed = False

            if settings.enable_preference_learning:
                feedbacks_detected, preferences_changed = await preference_learning.process_user_message(
                    user_message=message,
                    telefone=self.session_id
                )

                # Se preferências mudaram, recria agente com novo prompt
                if preferences_changed:
                    logger.info(f"Preferências atualizadas, recriando agente...")
                    self.agent = await self._create_agent()

            # 2. Cria agente se ainda não existe (primeira mensagem)
            if self.agent is None:
                self.agent = await self._create_agent()

            # 3. Recupera histórico de mensagens do Redis
            history_messages = self.message_history.messages

            # Limita histórico para últimos N mensagens (janela deslizante)
            max_history = settings.redis_memory_window * 2  # user + assistant = 2 messages
            if len(history_messages) > max_history:
                history_messages = history_messages[-max_history:]

            # 4. Prepara mensagens para o agente
            messages = []
            # Adiciona system prompt como primeira mensagem
            messages.append(SystemMessage(content=self.system_prompt))
            for msg in history_messages:
                messages.append(msg)
            messages.append(HumanMessage(content=message))

            # 5. Invoca agente
            config = {"configurable": {"thread_id": self.session_id}}
            response = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )

            # 6. Extrai resposta
            output_messages = response.get("messages", [])
            logger.info(f"[DEBUG] Total de mensagens retornadas: {len(output_messages)}")

            for idx, msg in enumerate(output_messages):
                msg_type = type(msg).__name__
                content_preview = str(msg.content)[:200] if hasattr(msg, 'content') else str(msg)[:200]
                logger.info(f"[DEBUG] Mensagem {idx}: Tipo={msg_type}, Content={content_preview}")

            if output_messages:
                last_message = output_messages[-1]
                if isinstance(last_message, AIMessage):
                    output = last_message.content
                else:
                    output = last_message.content
            else:
                output = "Desculpe, não consegui gerar uma resposta."

            # Garante que output é sempre string
            if isinstance(output, list):
                # Se for lista, pega apenas content type "text"
                text_parts = []
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                    else:
                        text_parts.append(str(item))
                output = "\n\n".join(p for p in text_parts if p)
                if not output:
                    output = "Desculpe, não consegui gerar uma resposta."
            elif not isinstance(output, str):
                # Converte qualquer outro tipo para string
                output = str(output) if output else "Desculpe, não consegui gerar uma resposta."

            output = _ensure_fixacao_optional_hint(output)

            # 7. Salva mensagens no histórico do Redis
            self.message_history.add_user_message(message)
            self.message_history.add_ai_message(output)

            # Remove prefixos internos de controle das respostas
            for prefix in ("PRECISA_PERGUNTAR:", "CONTRATO_CRIADO_SUCESSO:", "ERRO_CRIACAO:", "DADOS JÁ COLETADOS:"):
                if prefix in output:
                    output = output.replace(prefix, "").strip()

            # 8. Se detectou feedback de alta confiança, confirma aprendizado
            if feedbacks_detected and any(f.deve_aplicar for f in feedbacks_detected):
                confirmations = []
                for fb in feedbacks_detected:
                    if fb.deve_aplicar:
                        confirmations.append(f"{fb.tipo} → {fb.valor}")

                if confirmations:
                    logger.info(f"[PREFERÊNCIA] Atualizada internamente: {', '.join(confirmations)}")

            logger.info(f"Resposta gerada: {output[:100]}...")
            logger.info(f"[DEBUG] Retornando output com {len(output)} caracteres")
            return output

        except Exception as e:
            from openai import RateLimitError
            if isinstance(e, RateLimitError):
                logger.warning(f"Rate limit atingido, aguardando 10s antes de retentar...")
                import asyncio
                await asyncio.sleep(10)
                try:
                    response = await self.agent.ainvoke(
                        {"messages": messages},
                        config=config
                    )
                    output_messages = response.get("messages", [])
                    if output_messages:
                        last_message = output_messages[-1]
                        output = last_message.content if hasattr(last_message, "content") else str(last_message)
                        if isinstance(output, list):
                            output = " ".join(p.get("text", "") for p in output if isinstance(p, dict) and p.get("type") == "text")
                        self.message_history.add_user_message(message)
                        self.message_history.add_ai_message(output)
                        return output
                except Exception as retry_e:
                    logger.error(f"Erro após retry de rate limit: {retry_e}")
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)
            logger.error(f"[DEBUG] Exception type: {type(e).__name__}")
            logger.error(f"[DEBUG] Exception args: {e.args}")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."

    async def clear_memory(self):
        """Limpa memória da conversação"""
        self.message_history.clear()
        logger.info(f"Memória limpa para sessão {self.session_id}")

    async def _process_contrato_message(self, message: str) -> str:
        """
        Processa mensagem no fluxo leve de criação de contrato.
        Usa agente com APENAS a ADA tool + system prompt enxuto = muito menos tokens.
        """
        import asyncio
        from openai import RateLimitError
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                agent = self._get_contrato_agent()

                # Histórico limitado: só últimas 2 interações (4 mensagens)
                history_messages = self.message_history.messages
                recent = history_messages[-4:] if len(history_messages) > 4 else history_messages

                # Monta mensagens: system prompt leve + histórico curto + mensagem atual
                messages = [SystemMessage(content=_CONTRATO_SYSTEM_PROMPT)]
                for msg in recent:
                    messages.append(msg)
                messages.append(HumanMessage(content=message))

                # Invoca agente leve
                config = {"configurable": {"thread_id": f"{self.session_id}_contrato"}}
                response = await agent.ainvoke(
                    {"messages": messages},
                    config=config
                )

                # Extrai resposta
                output_messages = response.get("messages", [])
                output = "Desculpe, não consegui gerar uma resposta."

                if output_messages:
                    last_message = output_messages[-1]
                    output = last_message.content if hasattr(last_message, 'content') else str(last_message)

                # Garante string
                if isinstance(output, list):
                    text_parts = []
                    for item in output:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                        elif isinstance(item, str):
                            text_parts.append(item)
                    output = "\n\n".join(p for p in text_parts if p) or "Desculpe, não consegui gerar uma resposta."
                elif not isinstance(output, str):
                    output = str(output) if output else "Desculpe, não consegui gerar uma resposta."

                # Salva no histórico do Redis
                self.message_history.add_user_message(message)
                self.message_history.add_ai_message(output)

                # Remove prefixos internos
                for prefix in ("PRECISA_PERGUNTAR:", "CONTRATO_CRIADO_SUCESSO:", "ERRO_CRIACAO:", "DADOS JÁ COLETADOS:", "AGUARDANDO_CONFIRMACAO:"):
                    if prefix in output:
                        output = output.replace(prefix, "").strip()

                logger.info(f"[CONTRATO FLOW] Resposta: {output[:100]}...")
                return output

            except RateLimitError as e:
                logger.warning(f"[CONTRATO FLOW] Rate limit atingido (tentativa {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    # Espera 2 segundos antes de tentar novamente
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error(f"[CONTRATO FLOW] Erro após {max_retries} tentativas: {e}")
                    return "Desculpe, o sistema está temporariamente sobrecarregado. Por favor, aguarde alguns segundos e tente novamente."
            except Exception as e:
                logger.error(f"[CONTRATO FLOW] Erro: {e}", exc_info=True)
                return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
