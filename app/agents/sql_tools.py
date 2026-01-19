"""
Tools LangChain para consultas SQL
"""
import json
import logging
import re
import unicodedata
from decimal import Decimal
from typing import Optional, Dict, Any
from langchain_core.tools import Tool, StructuredTool
from app.core.database import sql_client
from app.utils.sql_validator import sql_validator
from app.utils.date_parser import date_parser
from app.models.user import UserPermissions

logger = logging.getLogger(__name__)


class SQLTools:
    """Ferramentas de consulta SQL para o agente"""

    def __init__(self, user: UserPermissions):
        self.user = user
        self.user_query = ""  # Armazena última pergunta do usuário

    def _remove_accents(self, text: str) -> str:
        """Remove acentos de uma string usando normalização Unicode"""
        # Normaliza para NFD (decompõe caracteres com acentos)
        nfd = unicodedata.normalize('NFD', text)
        # Remove combining marks (acentos)
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

    def _extract_client_name(self, query: str) -> Optional[str]:
        """
        Extrai nome do cliente da pergunta do usuário

        Args:
            query: Pergunta do usuário

        Returns:
            Nome do cliente ou None
        """
        # Remove caracteres especiais e normaliza
        query_lower = query.lower().strip()

        # Padrões comuns para identificar nome de cliente
        patterns = [
            # Cliente explícito: "para o cliente NOME"
            r'(?:para|do|da)\s+(?:o\s+|a\s+)?cliente\s+([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+temos|\s+tem|\s+para|\s+no|\s+em|\s+na|\s+do|\s+da|\?)',
            # Cliente implícito: "para a starbucks"
            r'para\s+(?:a\s+|o\s+)([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+temos|\s+tem|\s+para|\s+no|\s+em)',
            r'da\s+([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+em|\s+no|\s+para)',
            r'do\s+([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+em|\s+no|\s+para)',
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                client_name = match.group(1).strip()
                # Remove palavras muito curtas (< 3 chars) que podem ser artigos
                if len(client_name) >= 3:
                    logger.info(f"Cliente identificado na pergunta: '{client_name}'")
                    return client_name

        return None

    def _aggregate_by_client(self, results: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Agrega resultados por cliente com TODAS as informações relevantes:
        - Totais: contratos, sacas, valor
        - Médias: diferencial, preços, peneiras
        - Listas: certificados, qualidades, países, fixadores

        Args:
            results: Lista de resultados SQL

        Returns:
            Lista agregada por cliente com informações completas
        """
        from collections import defaultdict

        aggregated = defaultdict(lambda: {
            "total_contratos": 0,
            "total_sacas": 0,
            "total_valor": 0,
            "contratos": [],
            # Campos para calcular médias
            "diferencial_values": [],
            "valorUnitario_values": [],
            "valorFixado_values": [],
            "peneiraMTGB_values": [],
            "peneiraGrauda_values": [],
            "peneiraGrinder_values": [],
            # Listas de valores distintos
            "certificados": set(),
            "qualidades": set(),
            "paises": set(),
            "fixadores": set(),
            "linhas": set(),
            "mesEmbarque": set(),
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            data = aggregated[cliente]

            # Contadores e totais
            data["total_contratos"] += 1
            data["total_sacas"] += row.get("sacas", 0) or 0
            data["total_valor"] += row.get("valorTotal", 0) or 0
            data["contratos"].append(row.get("contrato", ""))

            # Valores para médias
            if row.get("diferencial"):
                data["diferencial_values"].append(float(row["diferencial"]))
            if row.get("valorUnitario"):
                data["valorUnitario_values"].append(float(row["valorUnitario"]))
            if row.get("valorFixado"):
                data["valorFixado_values"].append(float(row["valorFixado"]))
            if row.get("peneiraMTGB"):
                data["peneiraMTGB_values"].append(float(row["peneiraMTGB"]))
            if row.get("peneiraGrauda"):
                data["peneiraGrauda_values"].append(float(row["peneiraGrauda"]))
            if row.get("peneiraGrinder"):
                data["peneiraGrinder_values"].append(float(row["peneiraGrinder"]))

            # Valores distintos
            if row.get("certificado") and str(row["certificado"]).strip():
                data["certificados"].add(str(row["certificado"]).strip())
            if row.get("descricaoQualidade") and str(row["descricaoQualidade"]).strip():
                data["qualidades"].add(str(row["descricaoQualidade"]).strip())
            if row.get("pais") and str(row["pais"]).strip():
                data["paises"].add(str(row["pais"]).strip())
            if row.get("fixador") and str(row["fixador"]).strip():
                data["fixadores"].add(str(row["fixador"]).strip())
            if row.get("linha") and str(row["linha"]).strip():
                data["linhas"].add(str(row["linha"]).strip())
            if row.get("mesEmbarque") and str(row["mesEmbarque"]).strip():
                data["mesEmbarque"].add(str(row["mesEmbarque"]).strip())

        # Converte para lista com cálculos finais
        result_list = []
        for cliente, data in aggregated.items():
            # Calcula médias
            def safe_avg(values):
                return round(sum(values) / len(values), 2) if values else None

            result_list.append({
                "cliente": cliente,
                "total_contratos": data["total_contratos"],
                "total_sacas": round(data["total_sacas"], 2),
                "total_valor": round(data["total_valor"], 2),
                "valor_unitario_medio": safe_avg(data["valorUnitario_values"]),
                "valor_fixado_medio": safe_avg(data["valorFixado_values"]),
                "diferencial_medio": safe_avg(data["diferencial_values"]),
                "peneira_mtgb_media": safe_avg(data["peneiraMTGB_values"]),
                "peneira_grauda_media": safe_avg(data["peneiraGrauda_values"]),
                "peneira_grinder_media": safe_avg(data["peneiraGrinder_values"]),
                "certificados": sorted(list(data["certificados"])) if data["certificados"] else [],
                "qualidades": sorted(list(data["qualidades"])) if data["qualidades"] else [],
                "paises": sorted(list(data["paises"])) if data["paises"] else [],
                "fixadores": sorted(list(data["fixadores"])) if data["fixadores"] else [],
                "linhas": sorted(list(data["linhas"])) if data["linhas"] else [],
                "meses_embarque": sorted(list(data["mesEmbarque"])) if data["mesEmbarque"] else [],
                "contratos": ", ".join(data["contratos"][:10])  # Primeiros 10 contratos
            })

        # Ordena por valor total (maior primeiro)
        result_list.sort(key=lambda x: x["total_valor"], reverse=True)

        logger.info(f"Agregados {len(results)} registros em {len(result_list)} clientes (com detalhes completos)")
        return result_list

    def _filter_by_client(self, results: list[Dict[str, Any]], client_name: str) -> list[Dict[str, Any]]:
        """
        Filtra resultados por nome do cliente (case insensitive, busca parcial)

        Args:
            results: Lista de resultados SQL
            client_name: Nome do cliente para filtrar

        Returns:
            Lista filtrada
        """
        filtered = []
        # Normaliza: remove acentos, pontuação, espaços extras e converte para lowercase
        client_name_normalized = self._remove_accents(client_name.lower())
        # CRÍTICO: substituir pontuação por espaço ANTES de remover (para não juntar palavras como CIA.SA → CIASA)
        client_name_normalized = re.sub(r'[^\w\s]', ' ', client_name_normalized)  # substitui por espaço
        client_name_normalized = re.sub(r'\s+', ' ', client_name_normalized).strip()

        for row in results:
            cliente_row = str(row.get("cliente", ""))
            # Normaliza da mesma forma
            cliente_normalized = self._remove_accents(cliente_row.lower())
            # CRÍTICO: substituir pontuação por espaço ANTES de remover
            cliente_normalized = re.sub(r'[^\w\s]', ' ', cliente_normalized)  # substitui por espaço
            cliente_normalized = re.sub(r'\s+', ' ', cliente_normalized).strip()

            # Busca parcial e flexível
            if client_name_normalized in cliente_normalized or cliente_normalized in client_name_normalized:
                filtered.append(row)

        logger.info(f"Filtrados {len(filtered)} registros de {len(results)} para cliente '{client_name}' (normalizado: '{client_name_normalized}')")
        return filtered

    def _format_results(self, results: list[Dict[str, Any]], function_name: str, client_filter: Optional[str] = None) -> str:
        """
        Formata resultados SQL para apresentação ao usuário

        ESTRATÉGIA INTELIGENTE:
        1. Se cliente identificado na pergunta → filtra em Python
        2. Se >50 registros e sem cliente específico → agrega por cliente
        3. Se <50 registros → envia completo

        Args:
            results: Lista de dicionários com resultados
            function_name: Nome da função executada
            client_filter: Nome do cliente para filtrar (opcional)

        Returns:
            String formatada para o LLM
        """
        if not results:
            return "Nenhum resultado encontrado para esta consulta."

        total_records = len(results)
        original_count = total_records

        # ESTRATÉGIA 1: Se cliente específico foi identificado, filtra
        if client_filter:
            results = self._filter_by_client(results, client_filter)

            if not results:
                return f"Nenhum contrato encontrado para o cliente '{client_filter}' no período consultado."

            logger.info(f"[FILTRO CLIENTE] {len(results)} registros após filtrar por '{client_filter}'")
            total_records = len(results)

        # ESTRATÉGIA 2: Se muitos registros (>50) e sem filtro específico, agrega
        if len(results) > 50 and not client_filter:
            logger.info(f"[AGREGAÇÃO] {len(results)} registros, agregando por cliente...")
            aggregated = self._aggregate_by_client(results)

            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            formatted = json.dumps(aggregated, ensure_ascii=False, indent=2, default=convert_decimals)

            return f"""Resultados da consulta {function_name} (AGREGADOS POR CLIENTE):

Total de registros SQL: {original_count}
Total de clientes: {len(aggregated)}

Dados agregados:
{formatted}

Instruções: Os dados acima estão AGREGADOS por cliente. Cada linha mostra:

TOTAIS:
- total_contratos: quantidade de contratos daquele cliente
- total_sacas: soma de sacas de todos os contratos
- total_valor: soma do valor total de todos os contratos (em R$)

MÉDIAS:
- valor_unitario_medio: preço unitário médio (R$/saca)
- valor_fixado_medio: preço fixado médio (R$/saca)
- diferencial_medio: diferencial médio dos contratos
- peneira_mtgb_media: média da peneira MTGB
- peneira_grauda_media: média da peneira Grauda
- peneira_grinder_media: média da peneira Grinder

LISTAS DE VALORES DISTINTOS:
- certificados: lista de todos os certificados únicos
- qualidades: lista de todas as descrições de qualidade únicas
- paises: lista de todos os países de destino únicos
- fixadores: lista de todos os fixadores únicos
- linhas: lista de todas as linhas únicas
- meses_embarque: lista de todos os meses de embarque únicos
- contratos: primeiros 10 números de contrato

IMPORTANTE: Você pode responder sobre QUALQUER campo listado acima. Por exemplo:
- "Qual o diferencial médio?" → Use o campo diferencial_medio
- "Quais certificados?" → Use o campo certificados
- "Qual o preço médio?" → Use valor_unitario_medio ou valor_fixado_medio
- "Quais qualidades de café?" → Use o campo qualidades
- "Para quais países?" → Use o campo paises"""

        # ESTRATÉGIA 3: Poucos registros (<= 50), envia completo
        warning = ""
        if len(results) > 50:
            results = results[:50]
            warning = f"\n\nAtenção: Foram encontrados {total_records} registros. Exibindo apenas os primeiros 50."

        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        formatted = json.dumps(results, ensure_ascii=False, indent=2, default=convert_decimals)

        return f"""Resultados da consulta {function_name}:

Total de registros retornados pelo SQL: {original_count}
Registros nesta resposta: {len(results)}

Dados:
{formatted}{warning}

Instruções: Analise TODOS os {len(results)} registros acima. Se o usuário perguntou sobre um cliente específico, procure pelo nome no campo "cliente" em TODOS os registros e conte quantos há."""

    def _validate_and_execute(
        self,
        function_name: str,
        filters: Optional[Dict[str, Any]] = None,
        client_filter: Optional[str] = None
    ) -> str:
        """
        Valida permissões e filtros antes de executar query

        Args:
            function_name: Nome da função SQL
            filters: Filtros opcionais
            client_filter: Nome do cliente para filtrar resultados (opcional)

        Returns:
            Resultado formatado ou mensagem de erro
        """
        # Valida permissão
        has_permission, error_msg = sql_validator.validate_permission(self.user, function_name)
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: {function_name}")
            return error_msg

        # Valida filtros obrigatórios
        is_valid, error_msg, needs_clarification = sql_validator.validate_filters(function_name, filters)
        if not is_valid:
            if needs_clarification:
                logger.info(f"Filtros faltando para {function_name}: {error_msg}")
                return f"PRECISA_PERGUNTAR: {error_msg}"
            logger.error(f"Erro de validação em {function_name}: {error_msg}")
            return error_msg

        # Executa query
        try:
            logger.info(f"Executando {function_name} com filtros: {filters}, client_filter: {client_filter}")
            results = sql_client.execute_function(function_name, filters)
            return self._format_results(results, function_name, client_filter)
        except Exception as e:
            logger.error(f"Erro ao executar {function_name}: {e}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _pesquisa_vendas(self, periodo: Optional[str] = None) -> str:
        """
        Consulta dados de vendas e embarques da empresa.

        Args:
            periodo: Período desejado (ex: "dezembro 2025", "hoje", "sexta-feira passada")
                    Aceita mês/ano ou datas específicas

        Returns:
            Dados de vendas formatados
        """
        logger.info(f"[DEBUG] _pesquisa_vendas chamado com periodo={periodo}")

        # Extrai nome do cliente da pergunta original do usuário
        client_filter = None
        if self.user_query:
            client_filter = self._extract_client_name(self.user_query)
            if client_filter:
                logger.info(f"[FILTRO CLIENTE] Detectado '{client_filter}' na pergunta: {self.user_query}")

        filters = None
        if periodo:
            parsed = date_parser.parse_natural_date(periodo)
            logger.info(f"[DEBUG] date_parser retornou: {parsed}")

            if parsed:
                # PRIORIDADE 1: Se a pergunta menciona "embarcado" ou "embarque", usa mesEmbarque
                if "mes_embarque" in parsed and ("embarcad" in self.user_query.lower() or "embarque" in self.user_query.lower()):
                    filters = {"mesEmbarque": parsed["mes_embarque"]}
                    logger.info(f"[DEBUG] Palavra-chave 'embarcado/embarque' detectada - Usando filtro mesEmbarque: {filters}")
                # PRIORIDADE 2: Se tem mes_embarque mas NÃO mencionou embarque, usa mesEmbarque (para consultas de mês)
                elif "mes_embarque" in parsed:
                    filters = {"mesEmbarque": parsed["mes_embarque"]}
                    logger.info(f"[DEBUG] Usando filtro mesEmbarque: {filters}")
                # PRIORIDADE 3: Se tem data específica (dia), usa campo 'emissao'
                elif "data_inicio" in parsed:
                    filters = {"emissao": parsed["data_inicio"]}
                    # CRÍTICO: Adiciona data_fim para limitar o período
                    if "data_fim" in parsed:
                        filters["emissao_fim"] = parsed["data_fim"]
                    logger.info(f"[DEBUG] Usando filtro emissao: {filters}")
        else:
            # FALLBACK: Se o LLM não passou período, retorna mensagem pedindo
            logger.warning("[DEBUG] LLM não passou período!")
            return "PRECISA_PERGUNTAR: De qual período você gostaria de consultar? (Ex: dezembro de 2025, hoje, sexta-feira passada)"

        return self._validate_and_execute("IA_Vendas", filters, client_filter)

    def _pesquisa_compras(self, data_inicio: Optional[str] = None) -> str:
        """
        Consulta dados de compras e aquisições.

        Args:
            data_inicio: Data inicial (ex: "últimos 7 dias", "05/12/2025")

        Returns:
            Dados de compras formatados
        """
        filters = None
        if data_inicio:
            parsed = date_parser.parse_natural_date(data_inicio)
            if parsed and "data_inicio" in parsed:
                filters = {"emissao": parsed["data_inicio"]}

        return self._validate_and_execute("IA_Compras", filters)

    def _pesquisa_contas_pagas(self, data_inicio: Optional[str] = None) -> str:
        """
        Consulta contas já pagas pela empresa.

        Args:
            data_inicio: Data inicial (ex: "este mês", "últimos 30 dias")

        Returns:
            Dados de contas pagas
        """
        filters = None
        if data_inicio:
            parsed = date_parser.parse_natural_date(data_inicio)
            if parsed and "data_inicio" in parsed:
                filters = {"emissao": parsed["data_inicio"]}

        return self._validate_and_execute("IA_ContasPagas", filters)

    def _pesquisa_contas_a_pagar(self, data_vencimento: Optional[str] = None) -> str:
        """
        Consulta contas a pagar (vencimentos futuros).

        Args:
            data_vencimento: Data de vencimento (ex: "hoje", "próximos 7 dias")

        Returns:
            Dados de contas a pagar
        """
        filters = None
        if data_vencimento:
            parsed = date_parser.parse_natural_date(data_vencimento)
            if parsed and "data_inicio" in parsed:
                filters = {"vencimento": parsed["data_inicio"]}

        return self._validate_and_execute("IA_ContasAPagar", filters)

    def _pesquisa_saldo_bancario(self) -> str:
        """
        Consulta saldo bancário atual da empresa.
        NÃO requer filtros de data (retorna snapshot atual).

        Returns:
            Saldo bancário de todas as contas
        """
        return self._validate_and_execute("IA_SaldoBancario")

    def _pesquisa_estoque(self) -> str:
        """
        Consulta estoque de produtos.
        NÃO requer filtros de data (retorna snapshot atual).

        Returns:
            Dados do estoque atual
        """
        return self._validate_and_execute("IA_Estoque")

    def _pesquisa_orcamento(self, periodo: Optional[str] = None) -> str:
        """
        Consulta orçamento vs realizado.

        Args:
            periodo: Período desejado (ex: "dezembro 2025", "2025/12")

        Returns:
            Dados de orçamento
        """
        filters = None
        if periodo:
            parsed = date_parser.parse_natural_date(periodo)
            if parsed and "ano" in parsed and "mes" in parsed:
                filters = {
                    "ano": parsed["ano"],
                    "mes": parsed["mes"]
                }

        return self._validate_and_execute("IA_Orcamento", filters)

    def _pesquisa_cotacao(self) -> str:
        """
        Consulta cotação da bolsa.
        NÃO requer filtros de data (retorna dados atuais).

        Returns:
            Dados de cotação da bolsa
        """
        return self._validate_and_execute("IA_Cotacao")

    def _pesquisa_despesa_venda(self, contrato: Optional[str] = None) -> str:
        """
        Consulta despesas de venda por contrato.

        Args:
            contrato: Número do contrato (ex: "235/25")

        Returns:
            Dados de despesas de venda
        """
        filters = None
        if contrato:
            filters = {"contrato": contrato}

        return self._validate_and_execute("IA_DespesaVenda", filters)

    def _pesquisa_contas_a_receber(self, data_vencimento: Optional[str] = None) -> str:
        """
        Consulta contas a receber (recebimentos futuros).

        Args:
            data_vencimento: Data de vencimento (ex: "hoje", "próximos 7 dias")

        Returns:
            Dados de contas a receber
        """
        filters = None
        if data_vencimento:
            parsed = date_parser.parse_natural_date(data_vencimento)
            if parsed and "data_inicio" in parsed:
                filters = {"vencimentoReal": parsed["data_inicio"]}

        return self._validate_and_execute("IA_ContasAReceber", filters)

    def get_all_tools(self) -> list:
        """Retorna lista de todas as tools"""
        return [
            Tool(
                name="pesquisa_vendas",
                func=lambda periodo=None: self._pesquisa_vendas(periodo),
                description="Consulta dados de vendas e embarques da empresa. OBRIGATÓRIO passar o argumento 'periodo'. Aceita datas específicas (hoje, ontem, sexta-feira passada) ou períodos mensais (dezembro 2025, 2025/12). Exemplos: 'sexta-feira passada', 'hoje', 'últimos 7 dias', 'dezembro 2025'"
            ),
            Tool(
                name="pesquisa_compras",
                func=lambda data_inicio=None: self._pesquisa_compras(data_inicio),
                description="Consulta dados de compras e aquisições. Argumentos: data_inicio (opcional, ex: 'últimos 7 dias')"
            ),
            Tool(
                name="pesquisa_contas_pagas",
                func=lambda data_inicio=None: self._pesquisa_contas_pagas(data_inicio),
                description="Consulta contas já pagas pela empresa. Argumentos: data_inicio (opcional, ex: 'este mês')"
            ),
            Tool(
                name="pesquisa_contas_a_pagar",
                func=lambda data_vencimento=None: self._pesquisa_contas_a_pagar(data_vencimento),
                description="Consulta contas a pagar (vencimentos futuros). Argumentos: data_vencimento (opcional, ex: 'próximos 7 dias')"
            ),
            Tool(
                name="pesquisa_contas_a_receber",
                func=lambda data_vencimento=None: self._pesquisa_contas_a_receber(data_vencimento),
                description="Consulta contas a receber (recebimentos futuros). Argumentos: data_vencimento (opcional, ex: 'próximos 7 dias')"
            ),
            StructuredTool.from_function(
                func=self._pesquisa_saldo_bancario,
                name="pesquisa_saldo_bancario",
                description="Consulta saldo bancário atual da empresa. NÃO requer argumentos."
            ),
            StructuredTool.from_function(
                func=self._pesquisa_estoque,
                name="pesquisa_estoque",
                description="Consulta estoque de produtos. NÃO requer argumentos."
            ),
            Tool(
                name="pesquisa_orcamento",
                func=lambda periodo=None: self._pesquisa_orcamento(periodo),
                description="Consulta orçamento vs realizado. Argumentos: periodo (opcional, ex: 'dezembro 2025')"
            ),
            StructuredTool.from_function(
                func=self._pesquisa_cotacao,
                name="pesquisa_cotacao",
                description="Consulta cotação da bolsa. NÃO requer argumentos."
            ),
            Tool(
                name="pesquisa_despesa_venda",
                func=lambda contrato=None: self._pesquisa_despesa_venda(contrato),
                description="Consulta despesas de venda por contrato. Argumentos: contrato (opcional, ex: '235/25')"
            ),
        ]
