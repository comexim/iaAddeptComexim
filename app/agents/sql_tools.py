"""
Tools LangChain para consultas SQL
"""
import json
import logging
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from langchain_core.tools import Tool, StructuredTool
from app.core.database import sql_client
from app.utils.sql_validator import sql_validator
from app.utils.date_parser import date_parser
from app.models.user import UserPermissions
from app.core.redis_client import redis_client
from app.services.commercial_metrics import (
    aggregate_purchases,
    aggregate_purchases_by_quality,
    aggregate_sales_by_branch,
    aggregate_sales_totals,
    build_monthly_commercial_series,
    detect_sales_branch_from_query,
    filter_sales_by_branch,
    filter_sales_by_market,
    format_pt_br,
    month_keys_between,
    parse_last_weekday_date,
    reconcile_monthly_commercial_series,
    sales_branch_name,
)
from app.services.accounts_payable_metrics import (
    deduplicate_payables,
    payable_decimal,
    reconcile_payables,
)
from app.services.financial_position_scope import (
    CURRENT_OPEN_PAST_NOTICE,
    append_scope_notice,
    build_receivables_current_open_query,
    compact_financial_date,
    current_open_scope_notice,
)
from app.services.financial_period_context import (
    append_period_context,
    build_financial_period_context,
    filter_financial_rows_by_calendar,
    resolve_business_day_range,
    uses_business_days,
)
from app.services.financial_record_display import (
    format_zero_value_records,
    prepare_financial_record,
    split_zero_value_records,
    supplier_display,
    zero_value_classification,
)
from app.services.query_trace import log_query_processing
from app.services.stock_metrics import (
    build_longshort_snapshot,
    build_stock_snapshot,
    certificate_matches,
    detect_certificate_from_query,
    format_longshort_snapshot,
    normalize_certificate,
    snapshot_fingerprint,
)

logger = logging.getLogger(__name__)


class SQLTools:
    """Ferramentas de consulta SQL para o agente"""

    def __init__(self, user: UserPermissions, session_id: Optional[str] = None):
        self.user = user
        self.session_id = session_id
        self.user_query = ""  # Armazena última pergunta do usuário (CONTEXTUALIZADA para IA)
        self.user_query_original = ""  # Armazena pergunta ORIGINAL (sem contexto) para filtros
        self.ultimo_contrato_consultado = None  # Armazena último contrato consultado (para contexto)
        self._series_expected_months = []
        self._series_date_fields = None
        self._series_query_context = {}

        # Carrega último contrato do Redis (se disponível)
        if self.session_id:
            try:
                # Tenta carregar do Redis de forma síncrona
                import asyncio
                try:
                    # Se já existe um loop rodando, não tenta criar outro
                    loop = asyncio.get_running_loop()
                    # Não podemos usar run_until_complete em loop já rodando
                    logger.info(f"[CONTEXTO REDIS] Loop já rodando, pulando carregamento inicial")
                except RuntimeError:
                    # Não há loop rodando, podemos criar um
                    contrato_redis = asyncio.run(self._carregar_contrato_redis())
                    if contrato_redis:
                        self.ultimo_contrato_consultado = contrato_redis
                        logger.info(f"[CONTEXTO REDIS] Contrato carregado: {contrato_redis}")
            except Exception as e:
                logger.debug(f"[CONTEXTO REDIS] Não foi possível carregar contrato: {e}")

    @staticmethod
    def _log_financial_field_anomalies(rows: list[Dict[str, Any]], source: str) -> None:
        """Registra a origem dos campos sem alterar a linha devolvida pelo banco."""
        for index, row in enumerate(rows, 1):
            supplier = str(row.get("fornecedor") or "").strip()
            nature = str(row.get("natureza") or "").strip()
            description = str(row.get("descricao") or row.get("descrição") or "").strip()
            if not supplier:
                logger.info(
                    "[%s][CAMPO VAZIO] registro=%s fornecedor_original=%r natureza=%r descricao=%r valor=%r",
                    source, index, row.get("fornecedor"), nature, description, row.get("valor"),
                )
            elif nature and supplier.casefold() == nature.casefold():
                logger.info(
                    "[%s][ORIGEM BANCO] registro=%s fornecedor e natureza vieram iguais: %r; valor=%r",
                    source, index, supplier, row.get("valor"),
                )

    def _run_coroutine(self, coro):
        """Executa coroutine de forma segura independente do estado do event loop."""
        import asyncio
        import concurrent.futures
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def _salvar_resultado_scheduler(self, results: list) -> None:
        """Salva resultado bruto no Redis para uso como anexo xlsx no scheduler."""
        if not self.session_id or not results:
            return
        try:
            import json
            from decimal import Decimal

            def _serialize(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return str(obj)

            from redis import Redis
            from app.core.config import settings

            key = f"scheduler_result:{self.session_id}"
            payload = json.dumps(results, default=_serialize, ensure_ascii=False)
            client = Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            try:
                client.set(key, payload, ex=900)  # TTL 15 min
                logger.info(
                    "[SCHEDULER_RESULT] %s registro(s) salvos para geração do anexo",
                    len(results),
                )
            finally:
                client.close()
        except Exception as e:
            logger.warning(f"[SCHEDULER_RESULT] Erro ao salvar resultado para o anexo: {e}")

    def _remove_accents(self, text: str) -> str:
        """Remove acentos de uma string usando normalização Unicode"""
        # Normaliza para NFD (decompõe caracteres com acentos)
        nfd = unicodedata.normalize('NFD', text)
        # Remove combining marks (acentos)
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

    async def _salvar_contrato_redis(self, contrato: str):
        """
        Salva último contrato consultado no Redis

        Args:
            contrato: Número do contrato (ex: "228/25")
        """
        if not self.session_id:
            return

        try:
            key = f"contrato_ctx:{self.session_id}"
            await redis_client.set(key, contrato, ttl=7200)  # TTL: 2 horas
            logger.info(f"[CONTEXTO REDIS] Contrato salvo: {contrato} (sessão: {self.session_id})")
        except Exception as e:
            logger.error(f"[CONTEXTO REDIS] Erro ao salvar contrato: {e}")

    async def _carregar_contrato_redis(self) -> Optional[str]:
        """
        Carrega último contrato consultado do Redis

        Returns:
            Número do contrato ou None
        """
        if not self.session_id:
            return None

        try:
            key = f"contrato_ctx:{self.session_id}"
            contrato = await redis_client.get(key)
            if contrato:
                logger.info(f"[CONTEXTO REDIS] Contrato carregado: {contrato} (sessão: {self.session_id})")
            return contrato
        except Exception as e:
            logger.error(f"[CONTEXTO REDIS] Erro ao carregar contrato: {e}")
            return None

    def _normalizar_contrato(self, contrato: str) -> str:
        """
        Normaliza número de contrato removendo zeros à esquerda.

        Args:
            contrato: Número do contrato (ex: "031/25", "000256/25R")

        Returns:
            Contrato normalizado (ex: "31/25", "256/25R")

        Examples:
            "031/25" -> "31/25"
            "000256/25R" -> "256/25R"
            "087/25A" -> "87/25A"
        """
        if not contrato:
            return ""

        contrato = str(contrato).upper().strip()

        # Remove zeros à esquerda da parte antes da barra
        if "/" in contrato:
            partes = contrato.split("/")
            partes[0] = partes[0].lstrip("0") or "0"  # Mantém pelo menos um "0"
            return "/".join(partes)

        return contrato.lstrip("0") or "0"

    def _extract_safra_code(self, query: Optional[str]) -> Optional[str]:
        """Extrai codigo de safra em perguntas como 'safra 25/26'."""
        if not query:
            return None
        texto = unicodedata.normalize("NFKD", str(query).lower()).encode("ascii", "ignore").decode("ascii")
        match = re.search(r'\bsafra\s+(\d{2,4})\s*[/-]\s*(\d{2,4})\b', texto)
        if not match:
            return None

        inicio, fim = match.group(1), match.group(2)
        return f"{inicio[-2:]}/{fim[-2:]}"

    def _row_matches_safra(self, row: Dict[str, Any], safra_code: str) -> bool:
        """Compara safra da linha aceitando formatos 25/26, 2025/2026, 25-26."""
        valor = row.get("SAFRA")
        if valor is None:
            valor = row.get("safra")
        if valor is None:
            valor = row.get("Safra")
        if valor is None:
            return False

        texto = unicodedata.normalize("NFKD", str(valor).lower()).encode("ascii", "ignore").decode("ascii")
        numeros = re.findall(r'\d+', texto)
        if len(numeros) >= 2:
            linha_code = f"{numeros[0][-2:]}/{numeros[1][-2:]}"
            return linha_code == safra_code

        somente_digitos = re.sub(r'\D', '', texto)
        return somente_digitos.endswith(safra_code.replace("/", ""))

    def _filter_purchases_by_safra(self, rows: list[Dict[str, Any]], safra_code: str) -> list[Dict[str, Any]]:
        return [row for row in rows if self._row_matches_safra(row, safra_code)]

    def _format_purchase_total_summary(self, rows: list[Dict[str, Any]], safra_code: Optional[str] = None) -> str:
        metrics = aggregate_purchases(rows)
        if not metrics["totais_por_moeda"]:
            return "Nenhum resultado encontrado para esta consulta."

        linhas = []
        for total in metrics["totais_por_moeda"]:
            currency = total["moeda"]
            currency_label = currency
            media = total["media_ponderada"]
            media_label = format_pt_br(media) if media is not None else "N/A"
            linhas.extend([
                f"Valor total ({currency_label}): {format_pt_br(total['valor_total'])}",
                f"Média ponderada ({currency_label}): {media_label} por saca",
            ])

        prefixo = f"Volume total da safra {safra_code}" if safra_code else "Volume total de compras"
        query = self._remove_accents((self.user_query_original or self.user_query or "").lower())
        include_suppliers = any(term in query for term in ("fornecedor", "fornecedores", "quem vendeu", "de quem"))
        fornecedores = []
        suppliers_to_show = metrics["fornecedores"][:20] if include_suppliers else []
        for item in suppliers_to_show:
            fornecedores.append(
                f"- {item['fornecedor']}: {format_pt_br(item['quantidade'])} sacas | "
                f"{format_pt_br(item['peso_kg'])} kg | {item['contratos']} pedido(s)"
            )
        relacao = metrics.get("kg_por_saca_real")
        relacao_texto = format_pt_br(relacao) if relacao is not None else "N/A"
        supplier_section = ""
        if fornecedores:
            supplier_section = "\n\nPrincipais fornecedores:\n" + "\n".join(fornecedores)
            omitted = len(metrics["fornecedores"]) - len(suppliers_to_show)
            if omitted > 0:
                supplier_section += f"\n\nOutros {omitted} fornecedor(es) não foram exibidos neste resumo."

        return (
            "Resumo de compras\n\n"
            f"{prefixo}: {metrics['total_contratos']} pedido(s).\n"
            f"Total de sacas: {format_pt_br(sum(item['quantidade_total'] for item in metrics['totais_por_moeda']))} sacas\n"
            f"Peso total: {format_pt_br(metrics['peso_total_kg'])} kg\n"
            f"Peso médio por saca: {relacao_texto} kg/saca\n"
            + "\n".join(linhas)
            + supplier_section
        )

    def _is_purchase_total_query(self) -> bool:
        query = self._remove_accents((self.user_query_original or self.user_query or "").lower())
        return any(term in query for term in (
            "quanto compr", "quantas sacas", "volume total", "total de compras",
            "peso total", "quanto cafe", "compramos de cafe",
        ))

    def _is_purchase_quality_query(self) -> bool:
        """Detecta pedidos em que qualidade significa o campo SQL ``linha``."""
        query = self._remove_accents(
            (self.user_query_original or self.user_query or "").lower()
        )
        return bool(re.search(r'\b(?:qualidade|qualidades|linha|linhas)\b', query))

    def _format_purchase_quality_summary(self, rows: list[Dict[str, Any]]) -> str:
        """Formata linha/qualidade sem permitir inferência por posição ordinal."""
        groups = aggregate_purchases_by_quality(rows)
        if not groups:
            return "Não foram encontrados registros para esse período."

        query = self._remove_accents(
            (self.user_query_original or self.user_query or "").lower()
        )
        asks_only_for_line = bool(re.search(
            r'\b(?:qual|informe|mostre|diga).{0,20}\blinha\b|\blinha\s+dessa\s+compra\b',
            query,
        )) and not self._is_purchase_total_query()

        if asks_only_for_line:
            details = []
            for row in rows:
                identifier = str(
                    row.get("numero") or row.get("solicitacao") or row.get("contrato") or ""
                ).strip()
                quality = str(row.get("linha") or "NÃO INFORMADA").strip() or "NÃO INFORMADA"
                label = f"Compra {identifier}" if identifier else "Compra"
                details.append(f"- {label}: linha/qualidade {quality}")
            return (
                "Resumo de compras — campo linha/qualidade\n\n"
                + "\n".join(details)
                + "\n\nOs valores acima foram lidos diretamente do campo linha retornado pela procedure."
            )

        lines = []
        for item in groups:
            weighted_differential = (
                format_pt_br(item["diferencial_medio_ponderado"])
                if item["diferencial_medio_ponderado"] is not None
                else "NÃO CALCULÁVEL"
            )
            lines.extend([
                f"{item['linha']} - diferencial médio ponderado: {weighted_differential}",
                (
                    f"Total da linha: {format_pt_br(item['sacas'])} sacas | "
                    f"{format_pt_br(item['peso_kg'])} kg | {item['pedidos']} pedido(s)"
                ),
            ])
            for contract in item["contratos"]:
                differential = (
                    format_pt_br(contract["diferencial"])
                    if contract["diferencial"] is not None
                    else "NÃO INFORMADO"
                )
                supplier = (
                    f" | {contract['fornecedor']}" if contract["fornecedor"] else ""
                )
                lines.append(
                    f"- Pedido {contract['identificador']}{supplier}: "
                    f"diferencial {differential} | "
                    f"{format_pt_br(contract['sacas'])} sacas"
                )
            lines.append("")

        return (
            "Resumo de compras por qualidade (campo linha)\n\n"
            + "\n".join(lines).rstrip()
            + "\n\nO diferencial médio de cada linha foi ponderado pelas sacas dos pedidos listados."
        )

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

        # NÃO tenta extrair cliente se a query menciona MÚLTIPLOS clientes
        # Ex: "Nestlé ou Starbucks", "Nestlé, Starbucks", "entre Nestlé e Starbucks"
        # Nesses casos, deve retornar TODOS os dados e a IA faz a comparação
        if re.search(r'\bou\b.*\b(em|no|na|para)', query_lower) or re.search(r',.*\b(em|no|na|para)', query_lower):
            logger.info(f"[PROTEÇÃO] Query comparativa com múltiplos clientes detectada - NÃO vai extrair cliente específico")
            return None

        # NÃO tenta extrair cliente se a query é sobre agregações
        # (grupo, vendedor, filial, fixador, linha, etc.)
        if re.search(r'\b(por\s+grupo|vendedor|filial|fixad[oa]|importador|exportador|linha|cada\s+(grupo|vendedor|filial|linha))', query_lower):
            return None

        # NÃO tenta extrair cliente se a query menciona TERMOS TÉCNICOS do sistema
        # (módulos, funcionalidades, conceitos) que NÃO são nomes de clientes
        termos_tecnicos = [
            r'\bmercado\s+interno\b',  # filtro por pais = BRASIL, não é cliente
            r'\bmercado\s+nacional\b',  # filtro por pais = BRASIL, não é cliente
            r'\bmercado\s+externo\b',  # filtro por pais != BRASIL, não é cliente
            r'\bmercado\s+internacional\b',  # filtro por pais != BRASIL, não é cliente
            r'\bcontas\s+a\s+receber',  # "contas a receber"
            r'\bcontas\s+a\s+pagar',  # "contas a pagar"
            r'\bcontas\s+pagas',  # "contas pagas"
            r'\bsaldo\s+bancário',  # "saldo bancário"
            r'\borçamento',  # "orçamento"
            r'\bcotação',  # "cotação"
            r'\bdespesa\s+de\s+venda',  # "despesa de venda"
            # REMOVIDO: r'\bcompras' e r'\bvendas' — bloqueavam extração de cliente em
            # queries como "vendas do cliente NESTRADE" e "compras do fornecedor X"
            r'\bestoque',  # "estoque"
            r'\bmês\s+de\s+(embarque|emissão|emissao|fixação|fixacao)',  # "mês de embarque", "mês de emissão"
            r'\b(?:primeiro|segundo|1[ºo°]?|2[ºo°]?)\s+semestre\b',
            r'\bsemestre\s+(?:de\s+)?20\d{2}\b',
            r'\b(?:primeiro|segundo|terceiro|quarto|[1-4][ºo°]?)\s+trimestre\b',
            r'\b(?:mes\s+a\s+mes|mes\s+por\s+mes|por\s+mes)\b',
        ]

        for termo in termos_tecnicos:
            if re.search(termo, query_lower):
                logger.info(f"[PROTEÇÃO] Query menciona termo técnico do sistema - NÃO vai extrair cliente")
                return None

        # NÃO tenta extrair cliente se a query menciona operações financeiras/logísticas
        # que podem ser confundidas com nomes (ex: "não foram baixados", "foram embarcados")
        palavras_operacao = [
            r'\bnão\s+foram\s+baixad',  # "não foram baixados"
            r'\bforam\s+baixad',  # "foram baixados"
            r'\bja\s+foram\s+baixad',  # "já foram baixados"
            r'\bforam\s+embarcad',  # "foram embarcados"
            r'\bforam\s+pagos',  # "foram pagos"
            r'\bforam\s+quitad',  # "foram quitados"
            r'\bainda\s+não',  # "ainda não"
            r'\bsem\s+bl',  # "sem bl"
            r'\bsem\s+valor\s+fixado',  # "sem valor fixado"
            r'\btemos\s+par',  # "temos para embarcar" (não extrair "temos par" como cliente)
            r'\bvamos\s+',  # "vamos embarcar"
            r'\bqueremos\s+',  # "queremos embarcar"
            r'\bprecisamos\s+',  # "precisamos embarcar"
        ]

        for padrao in palavras_operacao:
            if re.search(padrao, query_lower):
                logger.info(f"[PROTEÇÃO] Query menciona operação financeira/logística - NÃO vai extrair cliente")
                return None

        # Padrões comuns para identificar nome de cliente
        # Terminadores: palavras que encerram o nome do cliente
        if re.search(r'\bcompar(e|ar|ativo|aÃ§Ã£o|acao)?\b', query_lower) and re.search(r'\b(comprad[oa]|vendid[oa]|vendas?|compras?)\b', query_lower):
            logger.info("[PROTEÃ‡ÃƒO] Query comparativa de compra/venda - NÃƒO vai extrair cliente")
            return None

        _T = r'(?:\s+temos|\s+tem|\s+para|\s+no|\s+em|\s+na|\s+do|\s+da|\s+de\b|\?|$)'
        _NOME = r'([a-záàâãéèêíïóôõöúçñ\s&\.\-/]+?)'

        patterns = [
            # Cliente explícito: "para o cliente NOME" / "do cliente NOME de 2025"
            rf'(?:para|do|da)\s+(?:o\s+|a\s+)?cliente\s+{_NOME}{_T}',
            # Cliente implícito: "para a starbucks"
            rf'para\s+(?:a\s+|o\s+){_NOME}{_T}',
            rf'da\s+{_NOME}(?:\s+em|\s+no|\s+para|\s+de\b|$)',
            rf'do\s+{_NOME}(?:\s+em|\s+no|\s+para|\s+de\b|$)',
        ]

        termos_metricas = [
            r'\bm[eé]dia\b',
            r'\bmedia\b',
            r'\bpor\s+saca\b',
            r'\bsacas?\b',
            r'\bvalor\s+total\b',
            r'\bvolume\b',
            r'\bvolume\s+(comprado|vendido)\b',
            r'\bcomprad[oa]\b',
            r'\bvendid[oa]\b',
            r'\bcom\s+o\s+volume\b',
            r'\bcompar(e|ar|ativo|aÃ§Ã£o|acao)?\b',
            r'\bmoeda\b',
            r'\bcontratos?\b',
            r'\bdividid[oa]\s+por\b',
            r'\btotal\s+de\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                client_name = match.group(1).strip()
                # Remove palavras muito curtas (< 3 chars) que podem ser artigos
                if len(client_name) >= 3 and not any(re.search(padrao, client_name) for padrao in termos_metricas):
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
            # Campos logísticos e administrativos (sets para evitar duplicatas por contrato)
            "contratos_com_bl": set(),
            "contratos_embarcados": set(),
            "contratos_com_corretor": [],  # contratos com refCorretor preenchido
            "contratos_amostra_enviada": [],
            "contratos_amostra_aprovada": [],
            "contratos_amostra_pendente": [],  # enviada mas NÃO aprovada
            "contratos_baixados": [],
            "contratos_baixados_por_mes": defaultdict(list),  # agrupa por YYYYMM
            "vendedores": set(),
            "filiais": set(),
            "grupos_venda": set(),
            "refCliente": None,  # Código/referência do cliente
        })

        for row in results:
            cliente = row.get("cliente", "SEM CLIENTE")
            data = aggregated[cliente]

            # Captura refCliente (só precisa uma vez por cliente)
            if not data["refCliente"] and row.get("refCliente"):
                data["refCliente"] = str(row["refCliente"]).strip()

            # Contadores e totais
            data["total_contratos"] += 1
            data["total_sacas"] += row.get("sacas", 0) or 0
            data["total_valor"] += row.get("valorTotal", 0) or 0
            data["contratos"].append(row.get("contrato", ""))

            # Valores para médias
            # IMPORTANTE: Usar "is not None" ao invés de truthy check para incluir valores 0.0
            if row.get("diferencial") is not None:
                data["diferencial_values"].append(float(row["diferencial"]))
            if row.get("valorUnitario") is not None:
                data["valorUnitario_values"].append(float(row["valorUnitario"]))
            if row.get("valorFixado") is not None:
                data["valorFixado_values"].append(float(row["valorFixado"]))
            if row.get("peneiraMTGB") is not None:
                data["peneiraMTGB_values"].append(float(row["peneiraMTGB"]))
            if row.get("peneiraGrauda") is not None:
                data["peneiraGrauda_values"].append(float(row["peneiraGrauda"]))
            if row.get("peneiraGrinder") is not None:
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

            # Campos logísticos e administrativos
            contrato = row.get("contrato", "")

            # Contratos com BL (usa set para evitar duplicatas de contrato)
            if row.get("numeroBL") and str(row["numeroBL"]).strip():
                data["contratos_com_bl"].add(contrato)

            # Contratos embarcados (com data de saída do navio)
            if row.get("saidaNavio") and str(row["saidaNavio"]).strip():
                data["contratos_embarcados"].add(contrato)

            # Contratos com referência de corretor
            if row.get("refCorretor") and str(row["refCorretor"]).strip():
                data["contratos_com_corretor"].append(contrato)

            # Contratos com amostra enviada
            enviou_amostra = row.get("envioAmostra") and str(row["envioAmostra"]).strip()
            aprovou_amostra = row.get("aprovAmostra") and str(row["aprovAmostra"]).strip()

            if enviou_amostra:
                data["contratos_amostra_enviada"].append(contrato)

            if aprovou_amostra:
                data["contratos_amostra_aprovada"].append(contrato)

            # Contratos com amostra enviada mas NÃO aprovada (pendente)
            if enviou_amostra and not aprovou_amostra:
                data["contratos_amostra_pendente"].append(contrato)

            # Contratos baixados financeiramente (com data)
            baixa_receber = row.get("baixaReceber")
            if baixa_receber and str(baixa_receber).strip():
                data_baixa = str(baixa_receber).strip()
                # Formato: "contrato (YYYYMMDD)"
                data["contratos_baixados"].append(f"{contrato} ({data_baixa})")

                # Agrupa por mês (YYYYMM) para facilitar queries
                if len(data_baixa) >= 6:
                    ano_mes = data_baixa[:6]  # Exemplo: "202601" de "20260115"
                    data["contratos_baixados_por_mes"][ano_mes].append(contrato)

            # Vendedores únicos
            if row.get("vendedor") and str(row["vendedor"]).strip():
                data["vendedores"].add(str(row["vendedor"]).strip())

            # Filiais únicas
            if row.get("filial") and str(row["filial"]).strip():
                data["filiais"].add(str(row["filial"]).strip())

            # Grupos de venda únicos
            if row.get("grupoVenda") and str(row["grupoVenda"]).strip():
                data["grupos_venda"].add(str(row["grupoVenda"]).strip())

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
                "contratos": ", ".join(data["contratos"][:10]),  # Primeiros 10 contratos
                # Campos logísticos e administrativos
                "contratos_com_bl": ", ".join(sorted(data["contratos_com_bl"])[:20]) if data["contratos_com_bl"] else "",
                "total_contratos_com_bl": len(data["contratos_com_bl"]),
                "contratos_embarcados": ", ".join(sorted(data["contratos_embarcados"])[:20]) if data["contratos_embarcados"] else "",
                "total_contratos_embarcados": len(data["contratos_embarcados"]),
                "contratos_com_corretor": ", ".join(data["contratos_com_corretor"][:20]) if data["contratos_com_corretor"] else "",
                "total_contratos_com_corretor": len(data["contratos_com_corretor"]),
                "contratos_amostra_enviada": ", ".join(data["contratos_amostra_enviada"][:20]) if data["contratos_amostra_enviada"] else "",
                "total_contratos_amostra_enviada": len(data["contratos_amostra_enviada"]),
                "contratos_amostra_aprovada": ", ".join(data["contratos_amostra_aprovada"][:20]) if data["contratos_amostra_aprovada"] else "",
                "total_contratos_amostra_aprovada": len(data["contratos_amostra_aprovada"]),
                "contratos_amostra_pendente": ", ".join(data["contratos_amostra_pendente"][:20]) if data["contratos_amostra_pendente"] else "",
                "total_contratos_amostra_pendente": len(data["contratos_amostra_pendente"]),
                "contratos_baixados": ", ".join(data["contratos_baixados"][:100]) if data["contratos_baixados"] else "",
                "total_contratos_baixados": len(data["contratos_baixados"]),
                # Contratos baixados por mês específico (para facilitar queries)
                "contratos_baixados_jan2026": ", ".join(data["contratos_baixados_por_mes"].get("202601", [])[:100]),
                "total_baixados_jan2026": len(data["contratos_baixados_por_mes"].get("202601", [])),
                "contratos_baixados_dez2025": ", ".join(data["contratos_baixados_por_mes"].get("202512", [])[:100]),
                "total_baixados_dez2025": len(data["contratos_baixados_por_mes"].get("202512", [])),
                "contratos_baixados_nov2025": ", ".join(data["contratos_baixados_por_mes"].get("202511", [])[:100]),
                "total_baixados_nov2025": len(data["contratos_baixados_por_mes"].get("202511", [])),
                "vendedores": sorted(list(data["vendedores"])) if data["vendedores"] else [],
                "filiais": sorted(list(data["filiais"])) if data["filiais"] else [],
                "grupos_venda": sorted(list(data["grupos_venda"])) if data["grupos_venda"] else [],
                "refCliente": data["refCliente"] if data["refCliente"] else "",
            })

        # OTIMIZAÇÃO ESPECIAL -1: Query sobre intersecção "embarcados E baixados"
        # DESABILITADA: estava hardcoded para janeiro 2026 e causando bugs em outras datas
        # TODO: Reimplementar de forma dinâmica se necessário
        if False and self.user_query and re.search(r'embarc(ad[oa]s?|aram|ou|am).*baix(ad[oa]s?|aram|ou|am)|baix(ad[oa]s?|aram|ou|am).*embarc(ad[oa]s?|aram|ou|am)', self.user_query.lower()):
            logger.info(f"[OTIMIZAÇÃO EMBARCADOS+BAIXADOS] Detectado query sobre intersecção")
            # Coleta todos os contratos embarcados e baixados
            embarcados_set = set()
            baixados_jan_set = set()
            contrato_cliente_map = {}  # mapeia contrato -> cliente

            for r in result_list:
                cliente = r["cliente"].strip()

                # Contratos embarcados
                embarcados_str = r.get("contratos_embarcados", "")
                if embarcados_str:
                    for c in embarcados_str.split(','):
                        c = c.strip()
                        if c:
                            embarcados_set.add(c)
                            contrato_cliente_map[c] = cliente

                # Contratos baixados em janeiro 2026
                baixados_str = r.get("contratos_baixados_jan2026", "")
                if baixados_str:
                    for c in baixados_str.split(','):
                        c = c.strip()
                        if c:
                            baixados_jan_set.add(c)
                            if c not in contrato_cliente_map:
                                contrato_cliente_map[c] = cliente

            # Intersecção: contratos que estão em AMBOS os conjuntos
            embarcados_e_baixados = embarcados_set.intersection(baixados_jan_set)

            # Formata resultado
            result = f"⚠️ RESPOSTA DIRETA (não altere): Dos {len(embarcados_set)} contratos que embarcaram em janeiro 2026, {len(embarcados_e_baixados)} foram baixados no contas a receber.\n\n"

            if len(embarcados_e_baixados) > 0:
                result += "Contratos embarcados E baixados:\n"
                for i, contrato in enumerate(sorted(list(embarcados_e_baixados)), 1):
                    cliente = contrato_cliente_map.get(contrato, "Cliente não identificado")
                    result += f"{i}. {contrato} ({cliente})\n"
            else:
                result += "Nenhum contrato embarcado foi baixado em janeiro 2026.\n"

            logger.info(f"[OTIMIZAÇÃO EMBARCADOS+BAIXADOS] {len(embarcados_set)} embarcados, {len(baixados_jan_set)} baixados, {len(embarcados_e_baixados)} intersecção")
            return result

        # OTIMIZAÇÃO ESPECIAL 0: Query sobre "corretor" ou "referência de corretor"
        if self.user_query_original and re.search(r'\bcorret[oa]r|referência.*corretor', self.user_query_original.lower()):
            # Filtra apenas clientes com contratos que têm corretor
            filtered_list = [
                r for r in result_list
                if r.get("total_contratos_com_corretor", 0) > 0
            ]

            # Cria lista de strings formatadas (um contrato por linha)
            # Formato: "272/25 (ECOM AGROINDUSTRIAL)"
            contratos_list = []
            total_contratos = 0

            for r in filtered_list:
                contratos_str = r["contratos_com_corretor"]
                if contratos_str:
                    contratos = [c.strip() for c in contratos_str.split(',')]
                    cliente = r["cliente"].strip()
                    for contrato in contratos:
                        contratos_list.append(f"{contrato} ({cliente})")
                        total_contratos += 1

            # Retorna string formatada com a lista completa
            result = f"⚠️ INSTRUÇÃO: Liste TODOS os {total_contratos} contratos abaixo. NÃO resuma, NÃO agrupe, NÃO omita nenhum contrato.\n\n"
            result += f"Contratos com referência de corretor em janeiro 2026:\n\n"
            result += "TOTAL: " + str(total_contratos) + " contratos\n\n"
            result += "Lista completa (TODOS devem ser mostrados ao usuário):\n"
            for i, contrato_info in enumerate(contratos_list, 1):
                result += f"{i}. {contrato_info}\n"

            logger.info(f"[OTIMIZAÇÃO CORRETOR] Retornando {total_contratos} contratos com corretor de {len(filtered_list)} clientes")
            return result

        # OTIMIZAÇÃO ESPECIAL 0.4: Query sobre "clientes sem referência/código"
        if self.user_query_original and re.search(r'(clientes?|quais).*\b(sem|não\s+t[eê]m?)\s+(código|codigo|referência|referencia)', self.user_query_original.lower()):
            # Filtra clientes sem refCliente
            clientes_sem_ref = []
            clientes_com_ref = []

            for r in result_list:
                cliente = r["cliente"].strip()
                ref = r.get("refCliente", "")

                if ref and ref.strip():
                    clientes_com_ref.append(cliente)
                else:
                    clientes_sem_ref.append(cliente)

            total_clientes = len(result_list)
            total_sem_ref = len(clientes_sem_ref)
            total_com_ref = len(clientes_com_ref)

            # Retorna string formatada
            result = f"⚠️ RESPOSTA DIRETA: Dos {total_clientes} clientes, {total_sem_ref} não têm código de referência cadastrado (e {total_com_ref} têm).\n\n"

            if total_sem_ref > 0:
                result += f"Clientes sem código de referência:\n\n"
                for i, cliente in enumerate(clientes_sem_ref, 1):
                    result += f"{i}. {cliente}\n"

            logger.info(f"[OTIMIZAÇÃO SEM REFERÊNCIA] {total_clientes} clientes, {total_com_ref} com ref, {total_sem_ref} sem ref")
            return result

        # OTIMIZAÇÃO ESPECIAL 0.5: Query sobre "contratos sem BL" ou "não têm BL"
        # MAS NÃO aplica se a pergunta menciona país específico (deixa a IA filtrar)
        menciona_pais = False
        if self.user_query:
            paises_comuns = ['alemanha', 'argentina', 'brasil', 'eua', 'estados unidos', 'china', 'japao', 'japão',
                           'holanda', 'belgica', 'bélgica', 'suica', 'suíça', 'russia', 'rússia', 'coreia', 'australia',
                           'austrália', 'austria', 'áustria', 'dinamarca', 'emirados', 'arabia', 'arábia']
            query_lower = self.user_query.lower()
            for pais in paises_comuns:
                if pais in query_lower:
                    menciona_pais = True
                    logger.info(f"[OTIMIZAÇÃO SEM BL] Pergunta menciona país '{pais}', NÃO vai aplicar otimização")
                    break

        if self.user_query_original and re.search(r'(sem|não\s+t[eê]m?|ainda\s+não|falta[m]?)\s+(número\s+de\s+)?bl\b', self.user_query_original.lower()) and not menciona_pais:
            # Calcula totais
            total_contratos = sum(r.get("total_contratos", 0) for r in result_list)
            total_com_bl = sum(r.get("total_contratos_com_bl", 0) for r in result_list)
            total_sem_bl = total_contratos - total_com_bl

            # Coleta contratos sem BL por cliente
            clientes_sem_bl = []
            for r in result_list:
                contratos = r.get("total_contratos", 0)
                com_bl = r.get("total_contratos_com_bl", 0)
                sem_bl = contratos - com_bl

                if sem_bl > 0:
                    clientes_sem_bl.append({
                        "cliente": r["cliente"].strip(),
                        "total_contratos": contratos,
                        "com_bl": com_bl,
                        "sem_bl": sem_bl
                    })

            # Retorna string formatada
            result = f"⚠️ RESPOSTA DIRETA: Dos {total_contratos} contratos, {total_sem_bl} ainda não têm número de BL (e {total_com_bl} já têm BL).\n\n"

            if len(clientes_sem_bl) > 0:
                result += f"Detalhamento por cliente ({len(clientes_sem_bl)} clientes com contratos sem BL):\n\n"
                # Ordena por número de contratos sem BL
                clientes_sem_bl.sort(key=lambda x: x["sem_bl"], reverse=True)
                for i, c in enumerate(clientes_sem_bl[:10], 1):  # Mostra top 10
                    result += f"{i}. {c['cliente']}: {c['sem_bl']} sem BL (de {c['total_contratos']} contratos)\n"

                if len(clientes_sem_bl) > 10:
                    result += f"\n... e mais {len(clientes_sem_bl) - 10} clientes\n"

            logger.info(f"[OTIMIZAÇÃO SEM BL] {total_contratos} contratos, {total_com_bl} com BL, {total_sem_bl} sem BL")
            return result

        # OTIMIZAÇÃO ESPECIAL 0.6: Query sobre "contratos sem amostra" ou "não enviaram amostra"
        # MAS NÃO aplica se a pergunta menciona país específico
        if self.user_query_original and re.search(r'(sem\s+amostra|não\s+(enviaram|enviou|mandaram|mandou|tiraram|tirou)\s+amostra|ainda\s+não.*amostra|falta[m]?\s+amostra)', self.user_query_original.lower()) and not menciona_pais:
            # Calcula totais
            total_contratos = sum(r.get("total_contratos", 0) for r in result_list)
            total_com_amostra = sum(r.get("total_contratos_amostra_enviada", 0) for r in result_list)

            # Coleta contratos sem amostra por cliente
            clientes_sem_amostra = []
            total_sem_amostra_listados = 0  # Conta os contratos realmente listados

            for r in result_list:
                contratos_str = r.get("contratos", "")
                amostra_str = r.get("contratos_amostra_enviada", "")

                if contratos_str:
                    # Lista de todos os contratos do cliente (limitado a 10 no campo "contratos")
                    todos_contratos = set(c.strip() for c in contratos_str.split(',') if c.strip())
                    # Lista de contratos com amostra enviada
                    com_amostra = set(c.strip() for c in amostra_str.split(',') if c.strip())
                    # Contratos sem amostra = todos - com amostra
                    sem_amostra = todos_contratos - com_amostra

                    if sem_amostra:
                        clientes_sem_amostra.append({
                            "cliente": r["cliente"].strip(),
                            "contratos": sorted(list(sem_amostra))
                        })
                        total_sem_amostra_listados += len(sem_amostra)

            # Usa o total calculado dos campos, não o total listado (que pode estar incompleto)
            total_sem_amostra = total_contratos - total_com_amostra

            # Retorna string formatada
            result = f"⚠️ RESPOSTA DIRETA: Dos {total_contratos} contratos, {total_sem_amostra} ainda não enviaram amostra (e {total_com_amostra} já enviaram).\n\n"

            if len(clientes_sem_amostra) > 0:
                # Avisa se a lista está incompleta
                if total_sem_amostra_listados < total_sem_amostra:
                    result += f"Lista de contratos sem amostra (mostrando {total_sem_amostra_listados} de {total_sem_amostra}):\n\n"
                else:
                    result += f"Lista completa de contratos sem amostra:\n\n"

                contador = 0
                for cliente_data in clientes_sem_amostra:
                    cliente = cliente_data["cliente"]
                    for contrato in cliente_data["contratos"]:
                        contador += 1
                        result += f"{contador}. {contrato} ({cliente})\n"

            logger.info(f"[OTIMIZAÇÃO SEM AMOSTRA] {total_contratos} contratos, {total_com_amostra} com amostra, {total_sem_amostra} sem amostra ({total_sem_amostra_listados} listados)")
            return result

        # OTIMIZAÇÃO ESPECIAL 0.7: Query pergunta "quais contratos" (lista individual de contratos)
        if self.user_query_original and re.search(r'(quais?|que)\s+contratos?\s+(foram|foi|est[aã]o|de)', self.user_query_original.lower()):
            logger.info(f"[OTIMIZAÇÃO LISTA CONTRATOS] Detectado query sobre 'quais contratos' - retornando lista individual")

            contratos_list = []
            for r in result_list:
                cliente = r["cliente"].strip()
                contratos_str = r.get("contratos", "")

                if contratos_str:
                    for c in contratos_str.split(','):
                        c = c.strip()
                        if c:
                            contratos_list.append({
                                "numero_contrato": c,
                                "cliente": cliente
                            })

            logger.info(f"[OTIMIZAÇÃO LISTA CONTRATOS] Retornando {len(contratos_list)} contratos individuais de {len(result_list)} clientes")
            return contratos_list

        # OTIMIZAÇÃO ESPECIAL 1: Query sobre "baixados EM [mês]" ou "EM [mês]... baixados"
        query_sobre_baixados_em_mes = False
        if self.user_query:
            query_lower = self.user_query.lower()
            # Detecta: "baixados EM" OU "EM [mês]... baixados/pagos/quitados"
            if re.search(r'baixad[oa]s?\s+(no\s+contas\s+a\s+receber\s+)?em\s+', query_lower):
                query_sobre_baixados_em_mes = True
            elif re.search(r'em\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)', query_lower) and \
                 re.search(r'(já\s+foram\s+)?(baixad[oa]s?|pagos?|quitad[oa]s?)\s+(financeiramente|no\s+contas)', query_lower):
                query_sobre_baixados_em_mes = True

        if query_sobre_baixados_em_mes:
            # Filtra apenas clientes com baixados em jan/2026, dez/2025 ou nov/2025
            filtered_list = [
                r for r in result_list
                if r.get("total_baixados_jan2026", 0) > 0
                or r.get("total_baixados_dez2025", 0) > 0
                or r.get("total_baixados_nov2025", 0) > 0
            ]

            # Retorna APENAS campos essenciais do mês (reduz de ~9000 chars/cliente para ~200 chars/cliente)
            minimal_list = []
            for r in filtered_list:
                minimal_list.append({
                    "cliente": r["cliente"],
                    "contratos_baixados_jan2026": r["contratos_baixados_jan2026"],
                    "total_baixados_jan2026": r["total_baixados_jan2026"],
                    "contratos_baixados_dez2025": r["contratos_baixados_dez2025"],
                    "total_baixados_dez2025": r["total_baixados_dez2025"],
                    "contratos_baixados_nov2025": r["contratos_baixados_nov2025"],
                    "total_baixados_nov2025": r["total_baixados_nov2025"],
                })

            logger.info(f"[OTIMIZAÇÃO BAIXADOS] Retornando {len(minimal_list)} clientes com campos mínimos (jan2026/dez2025/nov2025)")
            return minimal_list

        # OTIMIZAÇÃO ESPECIAL 2: Query sobre período específico (ex: "em janeiro", "por grupo em 2026")
        # Detecta queries com menção a mês/ano e retorna campos resumidos
        if self.user_query_original and re.search(r'\b(em|no|de)\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b', self.user_query_original.lower()):

            # OTIMIZAÇÃO ESPECIAL 2.1: Se a query menciona "por grupo", agregar por grupo de venda
            if re.search(r'\bpor\s+grupo', self.user_query_original.lower()):
                from collections import defaultdict

                por_grupo = defaultdict(lambda: {"valor": 0, "sacas": 0, "clientes": 0})

                for r in result_list:
                    grupos = r["grupos_venda"]
                    valor = r["total_valor"]
                    sacas = r["total_sacas"]

                    # Se não tem grupo, categoriza como "SEM GRUPO"
                    if not grupos or len(grupos) == 0:
                        grupos = ["SEM GRUPO"]

                    # Cada cliente pode estar em múltiplos grupos
                    for grupo in grupos:
                        por_grupo[grupo]["valor"] += valor
                        por_grupo[grupo]["sacas"] += sacas
                        por_grupo[grupo]["clientes"] += 1

                # Converte para lista ordenada por valor
                grupos_list = []
                for grupo, totais in sorted(por_grupo.items(), key=lambda x: x[1]["valor"], reverse=True):
                    grupos_list.append({
                        "grupo": grupo,
                        "valor_total": round(totais["valor"], 2),
                        "sacas_total": round(totais["sacas"], 2),
                        "numero_clientes": totais["clientes"]
                    })

                logger.info(f"[AGREGAÇÃO POR GRUPO] Retornando {len(grupos_list)} grupos de venda agregados")
                return grupos_list

            # OTIMIZAÇÃO ESPECIAL 2.2: Se a query menciona "fixado" ou "importador/exportador", agregar por fixador
            if re.search(r'\bfixad[oa]s?|importador|exportador', self.user_query_original.lower()):
                from collections import defaultdict

                por_fixador = defaultdict(lambda: {"valor": 0, "sacas": 0, "contratos": 0})

                for r in result_list:
                    fixadores = r.get("fixadores", [])
                    valor = r["total_valor"]
                    sacas = r["total_sacas"]
                    num_contratos = r["total_contratos"]

                    # Se não tem fixador, categoriza como "NÃO INFORMADO"
                    if not fixadores or len(fixadores) == 0:
                        fixadores = ["NÃO INFORMADO"]

                    # Cada cliente pode ter contratos com diferentes fixadores
                    for fixador in fixadores:
                        por_fixador[fixador]["valor"] += valor
                        por_fixador[fixador]["sacas"] += sacas
                        por_fixador[fixador]["contratos"] += num_contratos

                # Converte para lista ordenada por número de contratos
                fixadores_list = []
                for fixador, totais in sorted(por_fixador.items(), key=lambda x: x[1]["contratos"], reverse=True):
                    fixadores_list.append({
                        "fixador": fixador,
                        "numero_contratos": totais["contratos"],
                        "valor_total": round(totais["valor"], 2),
                        "sacas_total": round(totais["sacas"], 2)
                    })

                logger.info(f"[AGREGAÇÃO POR FIXADOR] Retornando {len(fixadores_list)} fixadores agregados")
                return fixadores_list

            # OTIMIZAÇÃO ESPECIAL 2.3: Se a query menciona "vendedor", agregar por vendedor
            if re.search(r'\bvendedor[ea]?s?', self.user_query_original.lower()):
                from collections import defaultdict

                por_vendedor = defaultdict(lambda: {
                    "valor": 0,
                    "sacas": 0,
                    "contratos": 0,
                    "clientes": set(),
                    "paises": set(),
                    "certificados": set(),
                    "qualidades": set(),
                    "linhas": set(),
                    "grupos_venda": set()
                })

                for r in result_list:
                    vendedores = r.get("vendedores", [])
                    valor = r["total_valor"]
                    sacas = r["total_sacas"]
                    num_contratos = r["total_contratos"]
                    cliente = r["cliente"]
                    paises = r.get("paises", [])
                    certificados = r.get("certificados", [])
                    qualidades = r.get("qualidades", [])
                    linhas = r.get("linhas", [])
                    grupos = r.get("grupos_venda", [])

                    # Se não tem vendedor, categoriza como "SEM VENDEDOR"
                    if not vendedores or len(vendedores) == 0:
                        vendedores = ["SEM VENDEDOR"]

                    # Cada cliente pode ter múltiplos vendedores
                    for vendedor in vendedores:
                        por_vendedor[vendedor]["valor"] += valor
                        por_vendedor[vendedor]["sacas"] += sacas
                        por_vendedor[vendedor]["contratos"] += num_contratos
                        por_vendedor[vendedor]["clientes"].add(cliente)
                        # Adiciona países, certificados, qualidades, linhas e grupos
                        for pais in paises:
                            por_vendedor[vendedor]["paises"].add(pais)
                        for cert in certificados:
                            por_vendedor[vendedor]["certificados"].add(cert)
                        for qual in qualidades:
                            por_vendedor[vendedor]["qualidades"].add(qual)
                        for linha in linhas:
                            por_vendedor[vendedor]["linhas"].add(linha)
                        for grupo in grupos:
                            por_vendedor[vendedor]["grupos_venda"].add(grupo)

                # Converte para lista ordenada por sacas
                vendedores_list = []
                for vendedor, totais in sorted(por_vendedor.items(), key=lambda x: x[1]["sacas"], reverse=True):
                    vendedores_list.append({
                        "vendedor": vendedor,
                        "sacas_total": round(totais["sacas"], 2),
                        "valor_total": round(totais["valor"], 2),
                        "numero_contratos": totais["contratos"],
                        "numero_clientes": len(totais["clientes"]),
                        "paises": sorted(list(totais["paises"])),
                        "certificados": sorted(list(totais["certificados"])),
                        "qualidades": sorted(list(totais["qualidades"])),
                        "linhas": sorted(list(totais["linhas"])),
                        "grupos_venda": sorted(list(totais["grupos_venda"]))
                    })

                logger.info(f"[AGREGAÇÃO POR VENDEDOR] Retornando {len(vendedores_list)} vendedores agregados")
                return vendedores_list

            # OTIMIZAÇÃO ESPECIAL 2.4: Se a query menciona "filial", agregar por filial
            if re.search(r'\bfiliai?s?', self.user_query_original.lower()):
                from collections import defaultdict

                por_filial = defaultdict(lambda: {"valor": 0, "sacas": 0, "contratos": 0, "clientes": set()})

                for r in result_list:
                    filiais = r.get("filiais", [])
                    valor = r["total_valor"]
                    sacas = r["total_sacas"]
                    num_contratos = r["total_contratos"]
                    cliente = r["cliente"]

                    # Se não tem filial, categoriza como "SEM FILIAL"
                    if not filiais or len(filiais) == 0:
                        filiais = ["SEM FILIAL"]

                    # Cada cliente pode ter contratos em múltiplas filiais
                    for filial in filiais:
                        por_filial[filial]["valor"] += valor
                        por_filial[filial]["sacas"] += sacas
                        por_filial[filial]["contratos"] += num_contratos
                        por_filial[filial]["clientes"].add(cliente)

                # Converte para lista ordenada por número de contratos
                filiais_list = []
                for filial, totais in sorted(por_filial.items(), key=lambda x: x[1]["contratos"], reverse=True):
                    filiais_list.append({
                        "filial": filial,
                        "numero_contratos": totais["contratos"],
                        "sacas_total": round(totais["sacas"], 2),
                        "valor_total": round(totais["valor"], 2),
                        "numero_clientes": len(totais["clientes"])
                    })

                logger.info(f"[AGREGAÇÃO POR FILIAL] Retornando {len(filiais_list)} filiais agregadas")
                return filiais_list

            # OTIMIZAÇÃO ESPECIAL 2.5: Se a query menciona "linha", agregar por linha de café
            if re.search(r'\blinha[s]?(\s+de\s+caf[eé])?', self.user_query_original.lower()):
                from collections import defaultdict

                por_linha = defaultdict(lambda: {"valor": 0, "sacas": 0, "contratos": 0, "clientes": set()})

                for r in result_list:
                    linhas = r.get("linhas", [])
                    valor = r["total_valor"]
                    sacas = r["total_sacas"]
                    num_contratos = r["total_contratos"]
                    cliente = r["cliente"]

                    # Se não tem linha, categoriza como "SEM LINHA"
                    if not linhas or len(linhas) == 0:
                        linhas = ["SEM LINHA"]

                    # Cada cliente pode ter contratos em múltiplas linhas
                    for linha in linhas:
                        por_linha[linha]["valor"] += valor
                        por_linha[linha]["sacas"] += sacas
                        por_linha[linha]["contratos"] += num_contratos
                        por_linha[linha]["clientes"].add(cliente)

                # Converte para lista ordenada por valor (para mostrar média por saca)
                linhas_list = []
                for linha, totais in sorted(por_linha.items(), key=lambda x: x[1]["valor"], reverse=True):
                    # Converte para float para evitar erro de tipo com Decimal
                    media_por_saca = float(totais["valor"]) / float(totais["sacas"]) if totais["sacas"] > 0 else 0
                    linhas_list.append({
                        "linha": linha,
                        "valor_total": round(totais["valor"], 2),
                        "sacas_total": round(totais["sacas"], 2),
                        "media_por_saca": round(media_por_saca, 2),
                        "numero_contratos": totais["contratos"],
                        "numero_clientes": len(totais["clientes"])
                    })

                logger.info(f"[AGREGAÇÃO POR LINHA] Retornando {len(linhas_list)} linhas agregadas")
                return linhas_list

            # Se não menciona "por grupo" nem "fixado" nem "vendedor" nem "filial" nem "linha", retorna por cliente
            # EXCETO se menciona "embarcad" ou "bl" ou "amostra" ou "referência/código" - nesse caso precisa dos campos completos
            if not re.search(r'embarc(ad[oa]s?|aram|ou|am)|\bbl\b|bill\s+of\s+lading|amostra|referência|referencia|código|codigo', self.user_query_original.lower()):
                # Retorna apenas campos essenciais (permite retornar TODOS os clientes sem rate limit)
                minimal_list = []
                for r in result_list:
                    minimal_list.append({
                        "cliente": r["cliente"],
                        "total_valor": r["total_valor"],
                        "total_sacas": r["total_sacas"],
                        "grupos_venda": r["grupos_venda"],
                    })

                logger.info(f"[OTIMIZAÇÃO PERÍODO] Retornando {len(minimal_list)} clientes com campos essenciais (valor, sacas, grupos)")
                return minimal_list

            # Se menciona "embarcad/bl/amostra/referência/código", não otimiza - retorna dados completos
            logger.info(f"[PERÍODO+CAMPOS COMPLETOS] Query menciona campos logísticos/administrativos - retornando dados completos")
            # Não retorna aqui - continua para o fluxo normal que retorna dados completos

        # Ordena por valor total (maior primeiro)
        result_list.sort(key=lambda x: x["total_valor"], reverse=True)

        # PROTEÇÃO GERAL: Limita a 50 clientes para evitar rate limit (30k tokens)
        # Com 35 campos por cliente, 50 clientes = ~22k tokens (seguro)
        if len(result_list) > 50:
            logger.warning(f"[LIMITE GERAL] Reduzindo de {len(result_list)} para 50 clientes (top 50 por valor)")
            result_list = result_list[:50]

        logger.info(f"Agregados {len(results)} registros em {len(result_list)} clientes (com detalhes completos)")
        return result_list

    def _aggregate_orcamento(self, results: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Agrega resultados de orçamento por grupo/categoria

        Campos disponíveis em IA_Orcamento():
        - ano: ano do orçamento (ex: "2025")
        - mes: mês (ex: "12")
        - grupo: código do grupo (ex: "CTRME", "COMB", "DEFUM")
        - descricao: descrição legível da categoria (ex: "COMBUSTIVEL", "DESP COM FUMIGACAO")
        - periodo: "Anual" ou "Mensal"
        - orcado: valor orçado (float)
        - realizado: valor realizado (float)
        - saldo: diferença orcado - realizado (float)

        Args:
            results: Lista de resultados SQL de IA_Orcamento()

        Returns:
            Lista agregada por grupo com orcado, realizado, saldo e metadados
        """
        from collections import defaultdict

        aggregated = defaultdict(lambda: {
            "orcado": 0,
            "realizado": 0,
            "saldo": 0,
            "registros": 0,
            "grupo": None,  # Código do grupo
            "periodos": set(),  # Anual ou Mensal
            "meses": set(),  # Meses incluídos (YYYY/MM)
            "anos": set(),  # Anos incluídos
        })

        for row in results:
            grupo = row.get("grupo", "SEM GRUPO").strip()
            descricao = row.get("descricao", "").strip()
            periodo = row.get("periodo", "").strip()
            ano = row.get("ano", "").strip()
            mes = row.get("mes", "").strip()

            # Usa descrição como chave (mais legível que código)
            key = descricao if descricao else grupo

            aggregated[key]["orcado"] += row.get("orcado", 0) or 0
            aggregated[key]["realizado"] += row.get("realizado", 0) or 0
            aggregated[key]["saldo"] += row.get("saldo", 0) or 0
            aggregated[key]["registros"] += 1

            # Metadados
            if not aggregated[key]["grupo"]:
                aggregated[key]["grupo"] = grupo
            if periodo:
                aggregated[key]["periodos"].add(periodo)
            if ano:
                aggregated[key]["anos"].add(ano)
            if ano and mes:
                aggregated[key]["meses"].add(f"{ano}/{mes.zfill(2)}")

        # Converte para lista
        result_list = []
        for categoria, data in aggregated.items():
            # Calcula percentual realizado
            percentual = 0
            if data["orcado"] > 0:
                percentual = round((data["realizado"] / data["orcado"]) * 100, 2)

            # Formata período
            periodos_str = ", ".join(sorted(data["periodos"])) if data["periodos"] else "N/A"

            # Formata anos
            anos_str = ", ".join(sorted(data["anos"])) if data["anos"] else "N/A"

            # Formata meses (primeiros 12)
            meses_list = sorted(list(data["meses"]))
            meses_str = ", ".join(meses_list[:12])
            if len(meses_list) > 12:
                meses_str += f" (e mais {len(meses_list) - 12})"

            result_list.append({
                "categoria": categoria,
                "grupo": data["grupo"],
                "orcado": round(data["orcado"], 2),
                "realizado": round(data["realizado"], 2),
                "saldo": round(data["saldo"], 2),
                "percentual_realizado": percentual,
                "periodo": periodos_str,  # Anual ou Mensal
                "anos": anos_str,  # Anos incluídos
                "meses": meses_str,  # Meses incluídos (YYYY/MM)
                "qtd_registros": data["registros"]  # Quantidade de registros agregados
            })

        # DETECÇÃO: Se a pergunta menciona "estouro", ordena por ESTOURO (realizado - orçado)
        # Caso contrário, ordena por valor orçado
        ordenar_por_estouro = False
        if hasattr(self, 'user_query') and self.user_query:
            query_lower = self.user_query.lower()
            # Detecta palavras relacionadas a estouro
            if any(termo in query_lower for termo in ["estouro", "estourou", "estouraram", "estourar", "mais gastou", "excedeu"]):
                ordenar_por_estouro = True
                logger.info(f"[ORDENAÇÃO] Pergunta menciona 'estouro' - ordenando por VALOR DO ESTOURO (realizado - orçado)")

        if ordenar_por_estouro:
            # Ordena por ESTOURO (realizado - orçado), maior primeiro
            # Estouro positivo = gastou MAIS que o orçado
            result_list.sort(key=lambda x: (x["realizado"] - x["orcado"]), reverse=True)
        else:
            # Ordena por valor orçado (maior primeiro) - padrão
            result_list.sort(key=lambda x: x["orcado"], reverse=True)

        logger.info(f"Agregados {len(results)} registros de orçamento em {len(result_list)} categorias (ordenado por: {'ESTOURO' if ordenar_por_estouro else 'ORÇADO'})")
        return result_list

    def _aggregate_estoque(self, results: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Agrega resultados de estoque por linha ou certificado

        Campos disponíveis em IA_Estoque():
        - filial: localização do estoque
        - lote: código do lote
        - loteFonecedor: código do fornecedor (pode ser vazio)
        - linha: tipo de café (PVA, GRD, LN1, LN2, LN3, etc.)
        - impureza, quebra, pva, grinder, peneiraGrauda, peneiraMTGB, fundo: métricas de qualidade (%)
        - certificado: tipo de certificação (RF, 4C, GC, CP, GT)
        - peso: peso em kg
        - armazem: nome do armazém
        - pais: país de origem
        - sacas: total de sacas
        - sacasConsumo: sacas para consumo interno
        - sacasExportacao: sacas para exportação

        Args:
            results: Lista de resultados SQL de IA_Estoque()

        Returns:
            Lista agregada por linha ou certificado
        """
        from collections import defaultdict

        # Decide critério de agregação: linha ou certificado
        # Se query menciona certificado, agrega por certificado; caso contrário, por linha
        agregar_por = "linha"  # default
        if hasattr(self, 'user_query_original') and self.user_query_original:
            query_lower = self.user_query_original.lower()
            if (
                any(termo in query_lower for termo in ["certificado", "certificação", "rainforest", "4c"])
                or detect_certificate_from_query(self.user_query_original)
            ):
                agregar_por = "certificado"
                logger.info(f"[AGREGAÇÃO ESTOQUE] Detectado menção a certificado - agregando por certificado")

        aggregated = defaultdict(lambda: {
            "sacas_total": 0,
            "sacas_consumo": 0,
            "sacas_exportacao": 0,
            "peso_total": 0,
            "lotes": set(),
            "filiais": set(),
            "armazens": set(),
            "certificados": set() if agregar_por == "linha" else None,
            "linhas": set() if agregar_por == "certificado" else None,
            "registros": 0,
        })

        for row in results:
            # Define chave de agregação
            if agregar_por == "linha":
                key = row.get("linha", "SEM LINHA").strip() or "SEM LINHA"
            else:
                key = normalize_certificate(row.get("certificado"))

            # Agrega valores
            aggregated[key]["sacas_total"] += row.get("sacas", 0) or 0
            aggregated[key]["sacas_consumo"] += row.get("sacasConsumo", 0) or 0
            aggregated[key]["sacas_exportacao"] += row.get("sacasExportacao", 0) or 0
            aggregated[key]["peso_total"] += row.get("peso", 0) or 0
            aggregated[key]["registros"] += 1

            # Metadados
            lote = row.get("lote", "").strip()
            if lote:
                aggregated[key]["lotes"].add(lote)

            filial = row.get("filial", "").strip()
            if filial:
                aggregated[key]["filiais"].add(filial)

            armazem = row.get("armazem", "").strip()
            if armazem:
                aggregated[key]["armazens"].add(armazem)

            # Adiciona informações cruzadas
            if agregar_por == "linha":
                certificado = row.get("certificado", "").strip()
                if certificado:
                    aggregated[key]["certificados"].add(certificado)
            else:
                linha = row.get("linha", "").strip()
                if linha:
                    aggregated[key]["linhas"].add(linha)

        # Converte para lista
        result_list = []
        for grupo, data in aggregated.items():
            item = {
                agregar_por: grupo,
                "sacas_total": round(data["sacas_total"], 2),
                "sacas_consumo": round(data["sacas_consumo"], 2),
                "sacas_exportacao": round(data["sacas_exportacao"], 2),
                "peso_kg": round(data["peso_total"], 2),
                "qtd_lotes": len(data["lotes"]),
                "qtd_registros": data["registros"],
                "filiais": ", ".join(sorted(data["filiais"])) if data["filiais"] else "N/A",
                "armazens": ", ".join(sorted(data["armazens"])) if data["armazens"] else "N/A",
            }

            # Adiciona informações cruzadas
            if agregar_por == "linha":
                item["certificados"] = ", ".join(sorted(data["certificados"])) if data["certificados"] else "N/A"
            else:
                item["linhas"] = ", ".join(sorted(data["linhas"])) if data["linhas"] else "N/A"

            result_list.append(item)

        # Ordena por sacas total (maior primeiro)
        result_list.sort(key=lambda x: x["sacas_total"], reverse=True)

        logger.info(f"Agregados {len(results)} registros de estoque em {len(result_list)} grupos (por {agregar_por})")
        return result_list

    def _format_stock_snapshot(self, results: list[Dict[str, Any]]) -> str:
        """Formata o estoque no código, sem delegar cálculos ao modelo."""
        query = self.user_query_original or self.user_query or ""
        group_by = (
            "certificado"
            if detect_certificate_from_query(query)
            or any(term in query.lower() for term in ("certificado", "certificação", "rainforest"))
            else "linha"
        )
        snapshot = build_stock_snapshot(results, group_by=group_by)
        weight = snapshot["composicao_peso"]
        context = getattr(self, "_stock_execution_context", {})
        logger.info(
            "[ESTOQUE RESPOSTA][%s] pergunta=%r agrupamento=%s linhas_filtradas=%s "
            "fingerprint_filtrado=%s duplicatas_exatas=%s repetições_chave_lote=%s "
            "totais={sacas:%s,consumo:%s,exportação:%s,peso:%s,lotes:%s}",
            context.get("execution_id", "sem-id"),
            query,
            group_by,
            len(results),
            snapshot_fingerprint(results),
            snapshot["duplicatas_exatas"],
            snapshot["repeticoes_chave_lote"],
            snapshot["total_sacas"],
            snapshot["sacas_consumo"],
            snapshot["sacas_exportacao"],
            snapshot["peso_kg"],
            snapshot["total_lotes"],
        )
        group_lines = []
        for item in snapshot["grupos"]:
            group_lines.append(
                f"- {item[group_by]}: {format_pt_br(item['sacas_total'])} sacas | "
                f"consumo {format_pt_br(item['sacas_consumo'])} | "
                f"exportação {format_pt_br(item['sacas_exportacao'])} | "
                f"{item['qtd_lotes']} lote(s) | filiais {item['filiais']} | "
                f"armazéns {item['armazens']}"
            )

        weight_lines = []
        for item in weight["itens"]:
            weight_lines.append(
                f"- {item['tipo']}: {item['registros']} registro(s) | "
                f"{format_pt_br(item['sacas'])} sacas | "
                f"{format_pt_br(item['peso_kg'])} kg de peso real"
            )
        if weight["fator_efetivo_kg_por_saca"] is not None:
            conversion_explanation = (
                "Relação efetiva do snapshot: "
                f"{format_pt_br(weight['fator_efetivo_kg_por_saca'])} kg por saca, "
                "calculada por peso real ÷ sacas. Nenhum fator padrão foi aplicado "
                "a esses registros."
            )
        else:
            conversion_explanation = "Não há peso real suficiente para calcular a relação kg por saca."
        if weight["sacas_sem_peso_real"] > 0:
            conversion_explanation += (
                f" Para {format_pt_br(weight['sacas_sem_peso_real'])} sacas sem peso real, "
                f"a estimativa é {format_pt_br(weight['peso_estimado_kg'])} kg usando "
                f"explicitamente o fator padrão de "
                f"{format_pt_br(weight['fator_padrao_kg_por_saca'], 0)} kg por saca."
            )
        if weight["registros_sem_peso_real"] == 0:
            weight_total_lines = f"Peso Total (campo real): {format_pt_br(weight['peso_real_kg'])} kg"
        elif weight["registros_com_peso_real"] == 0:
            weight_total_lines = (
                f"Peso Total estimado: {format_pt_br(weight['peso_estimado_kg'])} kg "
                f"(fator padrão informado: "
                f"{format_pt_br(weight['fator_padrao_kg_por_saca'], 0)} kg/saca)"
            )
        else:
            combined_weight = weight["peso_real_kg"] + weight["peso_estimado_kg"]
            weight_total_lines = (
                f"Peso Real conhecido: {format_pt_br(weight['peso_real_kg'])} kg\n"
                f"Peso estimado para registros sem peso: "
                f"{format_pt_br(weight['peso_estimado_kg'])} kg "
                f"({format_pt_br(weight['fator_padrao_kg_por_saca'], 0)} kg/saca)\n"
                f"Peso combinado real + estimado: {format_pt_br(combined_weight)} kg"
            )

        return (
            "Claro! Segue a posição atual do estoque físico:\n\n"
            f"Total de Sacas: {format_pt_br(snapshot['total_sacas'])} sacas\n"
            f"Sacas para Consumo: {format_pt_br(snapshot['sacas_consumo'])} sacas\n"
            f"Sacas para Exportação: {format_pt_br(snapshot['sacas_exportacao'])} sacas\n"
            f"{weight_total_lines}\n"
            f"Total de Lotes: {snapshot['total_lotes']}\n\n"
            f"Origem e conversão do peso:\n{conversion_explanation}\n"
            + ("\nComposição:\n" + "\n".join(weight_lines) if weight_lines else "")
            + "\n\n"
            + f"Detalhamento por {group_by}:\n"
            + ("\n".join(group_lines) if group_lines else "Não há grupos para detalhar.")
            + "\n\nSe quiser, posso detalhar um tipo, certificado, filial ou armazém específico."
        )

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

    def _is_monthly_series_request(self) -> bool:
        query = self._remove_accents(
            (self.user_query_original or self.user_query or "").lower()
        )
        return bool(re.search(
            r'\b(?:mes\s+a\s+mes|mes\s+por\s+mes|por\s+mes|'
            r'(?:quebra|quebre|detalhe|separad[oa]s?)\s+(?:mensal|por\s+mes)|'
            r'decomposicao\s+(?:mensal|por\s+mes)|serie\s+mensal|tendencia\s+mensal|'
            r'evolucao\s+mensal|mensalmente)\b',
            query,
        ))

    def _format_monthly_commercial_series(
        self,
        results: list[Dict[str, Any]],
        function_name: str,
    ) -> Optional[str]:
        if not self._is_monthly_series_request():
            return None
        if function_name not in ("IA_Vendas", "IA_Compras", "IA_ComprasPar"):
            return (
                "Não foi possível montar esta série mensal de forma determinística "
                "com os dados retornados. Para evitar estimativas, nenhum mês ou "
                "valor foi completado."
            )

        kind = "sales" if function_name == "IA_Vendas" else "purchases"
        expected = getattr(self, "_series_expected_months", [])
        date_fields = getattr(self, "_series_date_fields", None)
        series = build_monthly_commercial_series(
            results,
            kind,
            expected_months=expected,
            date_fields=date_fields,
        )
        present = series["meses_com_dados"]
        missing = series["meses_sem_registros"]
        if not present:
            return "Não foram encontrados registros para esse período."

        reconciliation = reconcile_monthly_commercial_series(results, kind, series)
        if not reconciliation["valido"]:
            logger.error(
                "[RECONCILIAÇÃO MENSAL] Inconsistência detectada. contexto=%s "
                "agregado=%s soma_meses=%s diferencas=%s violacoes=%s",
                getattr(self, "_series_query_context", {}),
                reconciliation["agregado"],
                reconciliation["soma_meses"],
                reconciliation["diferencas"],
                reconciliation["violacoes"],
            )
            if kind == "sales":
                aggregate = reconciliation["agregado"]
                monthly = reconciliation["soma_meses"]
                difference = reconciliation["diferencas"]
                return (
                    "Foi encontrada uma inconsistência na reconciliação mensal. "
                    "Os valores divergentes não serão apresentados como corretos.\n\n"
                    f"Total agregado: {aggregate['contratos']} contrato(s) | "
                    f"{format_pt_br(aggregate['sacas'])} sacas | "
                    f"USD {format_pt_br(aggregate['valor_usd'])}\n"
                    f"Soma dos meses: {monthly['contratos']} contrato(s) | "
                    f"{format_pt_br(monthly['sacas'])} sacas | "
                    f"USD {format_pt_br(monthly['valor_usd'])}\n"
                    f"Diferença: {difference['contratos']} contrato(s) | "
                    f"{format_pt_br(difference['sacas'])} sacas | "
                    f"USD {format_pt_br(difference['valor_usd'])}"
                )

            return (
                "Foi encontrada uma inconsistência na reconciliação mensal de compras. "
                "Os valores divergentes não serão apresentados como corretos. "
                f"Diferença na quantidade de contratos: "
                f"{reconciliation['diferencas']['contratos']}. "
                "As diferenças por moeda foram registradas no log técnico."
            )

        lines = [
            "Vendas por mês:" if kind == "sales" else "Compras por mês:",
            "",
        ]
        if kind == "sales":
            for item in present:
                lines.append(
                    f"- {item['mes']}: {item['contratos']} contrato(s) | "
                    f"{format_pt_br(item['sacas'])} sacas | "
                    f"USD {format_pt_br(item['valor_usd'])}"
                )
        else:
            for item in present:
                currency_parts = [
                    f"{total['moeda']} {format_pt_br(total['valor_total'])} / "
                    f"{format_pt_br(total['quantidade_total'])} sacas"
                    for total in item["totais_por_moeda"]
                ]
                lines.append(
                    f"- {item['mes']}: {item['total_contratos']} contrato(s) | "
                    + " | ".join(currency_parts)
                )

        if missing:
            lines.extend([
                "",
                "Meses sem registros: " + ", ".join(missing) + ".",
            ])
        return "\n".join(lines)

    def _format_results(self, results: list[Dict[str, Any]], function_name: str, client_filter: Optional[str] = None, pagina: int = 1) -> str:
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
            return "Não foram encontrados registros para esse período."

        total_records = len(results)
        original_count = total_records
        trace_filters: Dict[str, Any] = {}

        # ESTRATÉGIA 1: Se cliente específico foi identificado, filtra
        if client_filter:
            results = self._filter_by_client(results, client_filter)
            trace_filters["cliente"] = client_filter

            if not results:
                return f"Nenhum contrato encontrado para o cliente '{client_filter}' no período consultado."

            logger.info(f"[FILTRO CLIENTE] {len(results)} registros após filtrar por '{client_filter}'")
            total_records = len(results)

        # ESTRATÉGIA 1.5: Detecta e aplica filtros específicos mencionados na pergunta
        # USA user_query_original (sem contexto) para evitar falsos positivos
        if self.user_query_original:
            query_lower = self.user_query_original.lower()
            filtros_aplicados = []

            if function_name in ("IA_Compras", "IA_ComprasPar"):
                safra_detectada = self._extract_safra_code(self.user_query_original)
                if safra_detectada:
                    results_antes = len(results)
                    results = self._filter_purchases_by_safra(results, safra_detectada)
                    filtros_aplicados.append(f"safra {safra_detectada} ({results_antes} â†’ {len(results)})")
                    logger.info(
                        f"[FILTRO AUTOMÃTICO] Aplicado filtro safra "
                        f"{safra_detectada}: {results_antes} â†’ {len(results)}"
                    )

            # FILTROS PARA VENDAS
            if function_name == "IA_Vendas":
                filial_detectada = detect_sales_branch_from_query(self.user_query_original)
                if filial_detectada:
                    results_antes = len(results)
                    results = filter_sales_by_branch(results, filial_detectada)
                    filtros_aplicados.append(
                        f"filial {filial_detectada}/{sales_branch_name(filial_detectada)} "
                        f"({results_antes} → {len(results)})"
                    )
                    logger.info(
                        f"[FILTRO AUTOMÁTICO] Aplicado filtro filial "
                        f"{filial_detectada}/{sales_branch_name(filial_detectada)}: "
                        f"{results_antes} → {len(results)}"
                    )

                if any(term in query_lower for term in ["mercado interno", "mercado nacional"]):
                    results_antes = len(results)
                    results = filter_sales_by_market(results, "interno")
                    filtros_aplicados.append(f"mercado interno/MERCADO=INTERNO ({results_antes} → {len(results)})")
                    logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro mercado interno: {results_antes} → {len(results)}")

                if any(term in query_lower for term in ["mercado externo", "mercado internacional"]):
                    results_antes = len(results)
                    results = filter_sales_by_market(results, "externo")
                    filtros_aplicados.append(f"mercado externo/MERCADO=EXTERNO ({results_antes} → {len(results)})")
                    logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro mercado externo: {results_antes} → {len(results)}")

                # Filtro: sem valor fixado / preço a fixar
                # IMPORTANTE: "preço a fixar" significa que valorFixado = 0 ou null (preço ainda não foi fixado)
                if any(term in query_lower for term in ["sem valor fixado", "não tem valor fixado", "não fixado", "não fixados", "valor fixado null", "sem fixação", "preço a fixar", "preco a fixar", "a fixar"]):
                    results_antes = len(results)
                    contagem_fixacao = {"nao_fixados": 0, "fixados": 0, "invalidos": 0}

                    def normalizar_valor_fixado(valor):
                        if valor is None or str(valor).strip() == "":
                            return 0.0
                        if isinstance(valor, str):
                            texto = valor.strip().replace(" ", "")
                            # Aceita tanto 1.234,56 quanto 1234.56.
                            if "," in texto:
                                texto = texto.replace(".", "").replace(",", ".")
                            valor = texto
                        return float(valor)

                    def valor_nao_fixado(row):
                        try:
                            nao_fixado = normalizar_valor_fixado(row.get("valorFixado")) <= 0
                            contagem_fixacao["nao_fixados" if nao_fixado else "fixados"] += 1
                            return nao_fixado
                        except (TypeError, ValueError):
                            contagem_fixacao["invalidos"] += 1
                            return False

                    results = [r for r in results if valor_nao_fixado(r)]
                    logger.info(
                        "[FIXAÇÃO valorFixado] não fixados=%s, fixados=%s, inválidos=%s, total=%s",
                        contagem_fixacao["nao_fixados"],
                        contagem_fixacao["fixados"],
                        contagem_fixacao["invalidos"],
                        results_antes,
                    )
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"sem valor fixado ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'sem valor fixado': {results_antes} → {len(results)}")

                # Filtro: contratos já fixados. O único critério válido é valorFixado > 0.
                elif any(term in query_lower for term in ["contratos fixados", "contratos já fixados", "vendas fixadas"]):
                    results_antes = len(results)
                    def valor_ja_fixado(row):
                        try:
                            return float(row.get("valorFixado") or 0) > 0
                        except (TypeError, ValueError):
                            return False

                    results = [r for r in results if valor_ja_fixado(r)]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"com valor fixado ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'já fixados': {results_antes} → {len(results)}")

                # Filtro: sem BL
                if any(term in query_lower for term in ["sem bl", "sem numero de bl", "não tem bl", "não têm bl", "nao tem bl", "nao têm bl", "bl null"]):
                    results_antes = len(results)
                    results = [r for r in results if not r.get("numeroBL") or str(r.get("numeroBL")).strip() == ""]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"sem BL ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'sem BL': {results_antes} → {len(results)}")

                # Filtro: embarcados (com data de saída do navio)
                # IMPORTANTE: Só aplica se a query menciona explicitamente "embarcados"
                # E NÃO menciona "não embarcados" ou "sem embarque"
                if any(term in query_lower for term in ["já foram embarcados", "foram embarcados", "que embarcaram", "contratos embarcados"]) and \
                   not any(term in query_lower for term in ["não embarcados", "não foram embarcados", "sem embarque", "não embarcaram"]):
                    results_antes = len(results)
                    results = [r for r in results if r.get("saidaNavio") and str(r.get("saidaNavio")).strip() != ""]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"embarcados (com saidaNavio) ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados': {results_antes} → {len(results)}")

                # Filtro: NÃO embarcados (sem data de saída do navio)
                # Aplica quando query menciona explicitamente "não embarcados" ou "não foram embarcados"
                if any(term in query_lower for term in ["não embarcados", "não foram embarcados", "sem embarque", "não embarcaram", "ainda não embarcaram"]):
                    results_antes = len(results)
                    results = [r for r in results if not r.get("saidaNavio") or str(r.get("saidaNavio")).strip() == ""]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"não embarcados (sem saidaNavio) ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'não embarcados': {results_antes} → {len(results)}")

            # FILTROS PARA ORÇAMENTO
            elif function_name in ("IA_Orcamento", "IA_OrcamentoPar"):
                # Filtro: categoria específica mencionada
                # Categorias comuns: combustível, fumigação, manutenção, etc.
                categorias_conhecidas = [
                    ("combustivel", ["combustivel", "combustível", "gasolina", "diesel"]),
                    ("fumigacao", ["fumigacao", "fumigação"]),
                    ("manutencao", ["manutenção", "manutencao", "manutenções", "manutencoes"]),
                    ("depreciacao", ["depreciação", "depreciacao"]),
                    ("viagem", ["viagem", "viagens"]),
                ]

                for nome_filtro, termos in categorias_conhecidas:
                    if any(termo in query_lower for termo in termos):
                        results_antes = len(results)
                        # Filtra por descrição ou grupo que contém o termo
                        results = [
                            r for r in results
                            if any(termo in str(r.get("descricao", "")).lower() or termo in str(r.get("grupo", "")).lower() for termo in termos)
                        ]
                        if len(results) < results_antes and len(results) > 0:
                            filtros_aplicados.append(f"categoria '{nome_filtro}' ({results_antes} → {len(results)})")
                            logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro categoria '{nome_filtro}': {results_antes} → {len(results)}")
                            break  # Aplica apenas o primeiro filtro encontrado

            # FILTROS PARA ESTOQUE
            elif function_name == "IA_Estoque":
                # Filtro: linha específica (PVA, GRD, LN1, LN2, LN3, etc.)
                # 🚨 DETECÇÃO DE QUERIES COMPLEXAS (NÃO aplicar filtros automáticos de linha/certificado)
                # Problema: Filtros sequenciais destroem queries com múltiplas opções ou negações
                # Exemplos problemáticos:
                # - "Rainforest, 4C ou GC?" → filtra só Rainforest, perde 4C e GC
                # - "PVA sem Rainforest" → filtra COM Rainforest (ignora negação)
                # - "GRD brasileiro ou LN2 europeu" → aplica filtros sequencialmente, zera dados

                skip_filtros_especificos = False

                # Detectar múltiplas opções separadas por vírgula + "ou"
                # Ex: "A, B ou C?", "X ou Y?", "entre A e B?"
                import re
                tem_multiplas_opcoes = bool(re.search(r',.*\bou\b', query_lower))  # "A, B ou C"
                tem_ou = ' ou ' in query_lower and ('?' in query_lower or ':' in query_lower)  # "A ou B?"
                tem_virgula_lista = query_lower.count(',') >= 1 and ('?' in query_lower or ':' in query_lower)  # "A, B, C?"

                # Detectar negações
                palavras_negacao = [" sem ", "que não", "exceto", "não tem", "não há", "não possui", "não contem", "não contém", "fora", "além de"]
                tem_negacao = any(palavra in query_lower for palavra in palavras_negacao)

                if tem_multiplas_opcoes or tem_ou or tem_virgula_lista or tem_negacao:
                    skip_filtros_especificos = True
                    razoes = []
                    if tem_multiplas_opcoes or tem_ou or tem_virgula_lista:
                        razoes.append("múltiplas opções detectadas")
                    if tem_negacao:
                        razoes.append("negação detectada")
                    logger.warning(f"[FILTRO AUTOMÁTICO] Query complexa detectada ({', '.join(razoes)}) - DESABILITANDO filtros de linha/certificado para evitar perda de dados")
                    logger.warning(f"[FILTRO AUTOMÁTICO] IA fará agregação manual dos dados completos")

                # Filtros de linha e certificado (SÓ aplicar se NÃO for query complexa)
                if not skip_filtros_especificos:
                    linhas_conhecidas = [
                        ("pva", ["pva"]),
                        ("grd", ["grd", "grinder"]),
                        ("ln1", ["ln1", "linha 1"]),
                        ("ln2", ["ln2", "linha 2"]),
                        ("ln3", ["ln3", "linha 3"]),
                        ("cd", ["cd"]),
                        ("fundi", ["fundi", "fundo"]),
                    ]

                    for nome_filtro, termos in linhas_conhecidas:
                        if any(termo in query_lower for termo in termos):
                            results_antes = len(results)
                            results = [
                                r for r in results
                                if any(termo in str(r.get("linha", "")).lower() for termo in termos)
                            ]
                            if len(results) < results_antes and len(results) > 0:
                                filtros_aplicados.append(f"linha '{nome_filtro.upper()}' ({results_antes} → {len(results)})")
                                logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro linha '{nome_filtro.upper()}': {results_antes} → {len(results)}")
                                break

                    # Filtro: certificado específico. Usa igualdade normalizada, nunca substring.
                    # Ex.: pedido "RF" deve casar apenas certificado RF, não qualquer texto contendo "rf".
                    certificado_solicitado = detect_certificate_from_query(self.user_query_original or "")
                    if certificado_solicitado:
                        results_antes = len(results)
                        results = [
                            r for r in results
                            if certificate_matches(r.get("certificado"), certificado_solicitado)
                        ]
                        if len(results) < results_antes and len(results) > 0:
                            filtros_aplicados.append(
                                f"certificado '{certificado_solicitado}' ({results_antes} → {len(results)})"
                            )
                            logger.info(
                                f"[FILTRO AUTOMÁTICO] Aplicado filtro certificado "
                                f"'{certificado_solicitado}': {results_antes} → {len(results)}"
                            )

                # Detectar se é uma query COMPARATIVA (não aplicar filtros específicos)
                palavras_comparativas = ["mais", "menos", " ou ", " vs ", " versus ", "comparar", "comparação", "comparacao", "diferença", "diferenca"]
                is_comparativa = any(palavra in query_lower for palavra in palavras_comparativas)

                # Filtro: sacas para exportação (NÃO aplicar em queries comparativas)
                if not is_comparativa and any(term in query_lower for term in ["para exportação", "para exportacao", "exportação", "exportacao", "sacas de exportação"]):
                    results_antes = len(results)
                    results = [r for r in results if r.get("sacasExportacao", 0) > 0]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"sacas para exportação ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'sacas para exportação': {results_antes} → {len(results)}")
                elif is_comparativa:
                    logger.info(f"[FILTRO AUTOMÁTICO] Query comparativa detectada - NÃO aplicando filtro de exportação/consumo")

                # Filtro: sacas para consumo (NÃO aplicar em queries comparativas)
                if not is_comparativa and any(term in query_lower for term in ["para consumo", "consumo interno", "mercado interno", "sacas de consumo"]):
                    results_antes = len(results)
                    results = [r for r in results if r.get("sacasConsumo", 0) > 0]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"sacas para consumo ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'sacas para consumo': {results_antes} → {len(results)}")

                # Filtro: impureza baixa (< 10%)
                if any(term in query_lower for term in ["baixa impureza", "pouca impureza", "impureza baixa", "menos de 10% de impureza", "impureza menor"]):
                    results_antes = len(results)
                    results = [r for r in results if r.get("impureza", 100) < 10]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"impureza < 10% ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro 'impureza < 10%': {results_antes} → {len(results)}")

                # Filtro: café brasileiro (país = BRASIL) - NÃO aplicar em queries complexas
                if not skip_filtros_especificos and any(term in query_lower for term in ["brasileiro", "brasileira", "do brasil", "brasil", "nacional"]):
                    results_antes = len(results)
                    results = [r for r in results if str(r.get("pais", "")).strip().upper() == "BRASIL"]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"país 'BRASIL' ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro país 'BRASIL': {results_antes} → {len(results)}")

                # Filtro: café europeu (país = EUROPA) - NÃO aplicar em queries complexas
                if not skip_filtros_especificos and any(term in query_lower for term in ["europeu", "europeia", "da europa", "europa"]):
                    results_antes = len(results)
                    results = [r for r in results if str(r.get("pais", "")).strip().upper() == "EUROPA"]
                    if len(results) < results_antes:
                        filtros_aplicados.append(f"país 'EUROPA' ({results_antes} → {len(results)})")
                        logger.info(f"[FILTRO AUTOMÁTICO] Aplicado filtro país 'EUROPA': {results_antes} → {len(results)}")

            # Atualiza total de registros após filtros
            if filtros_aplicados:
                total_records = len(results)
                trace_filters["filtros_automaticos"] = list(filtros_aplicados)
                logger.info(f"[FILTROS APLICADOS] {', '.join(filtros_aplicados)}")
                if not results:
                    return "Não foram encontrados registros para esse período."

            if (
                function_name == "IA_Vendas"
                and not self._is_monthly_series_request()
                and any(term in query_lower for term in ["mercado interno", "mercado nacional", "mercado externo", "mercado internacional"])
            ):
                market_label = "mercado interno" if any(term in query_lower for term in ["mercado interno", "mercado nacional"]) else "mercado externo"
                totals = aggregate_sales_totals(results)
                log_query_processing(
                    source_name=function_name,
                    original_count=original_count,
                    final_count=len(results),
                    post_filters={"mercado": market_label},
                    calculated_totals=totals,
                    unit="sacas",
                    currency="USD",
                )
                return (
                    f"No período consultado, vendemos no {market_label} "
                    f"{format_pt_br(totals['sacas'])} sacas, no valor total de "
                    f"USD {format_pt_br(totals['valor_usd'])}, em "
                    f"{totals['contratos']} contrato(s)."
                )

            if function_name in ("IA_Compras", "IA_ComprasPar"):
                safra_detectada = self._extract_safra_code(self.user_query_original)
                if (
                    safra_detectada
                    and not self._is_monthly_series_request()
                    and any(term in query_lower for term in ["volume total", "total da safra", "quanto compr", "quantas sacas"])
                ):
                    purchase_metrics = aggregate_purchases(results)
                    log_query_processing(
                        source_name=function_name,
                        original_count=original_count,
                        final_count=len(results),
                        post_filters={"safra": safra_detectada},
                        calculated_totals=purchase_metrics,
                        unit="sacas/kg",
                        currency=",".join(
                            item["moeda"] for item in purchase_metrics["totais_por_moeda"]
                        ) or "N/I",
                    )
                    return self._format_purchase_total_summary(results, safra_detectada)

        trace_totals: Dict[str, Any] = {}
        trace_unit = None
        trace_currency = None
        if function_name in ("IA_Compras", "IA_ComprasPar"):
            purchase_metrics = aggregate_purchases(results)
            trace_totals = {
                "pedidos": purchase_metrics["total_contratos"],
                "peso_kg": purchase_metrics["peso_total_kg"],
                "por_moeda": purchase_metrics["totais_por_moeda"],
            }
            trace_unit = "sacas/kg"
            currencies = [item["moeda"] for item in purchase_metrics["totais_por_moeda"]]
            trace_currency = ",".join(currencies) if currencies else "N/I"
        elif function_name == "IA_Vendas":
            sales_metrics = aggregate_sales_totals(results)
            trace_totals = sales_metrics
            trace_unit = "sacas"
            trace_currency = "USD"
        elif function_name == "IA_Estoque":
            stock_metrics = build_stock_snapshot(results)
            trace_totals = {
                "total_sacas": stock_metrics["total_sacas"],
                "sacas_consumo": stock_metrics["sacas_consumo"],
                "sacas_exportacao": stock_metrics["sacas_exportacao"],
                "peso_kg": stock_metrics["peso_kg"],
                "total_lotes": stock_metrics["total_lotes"],
            }
            trace_filters["duplicatas_exatas_removidas"] = stock_metrics["duplicatas_exatas"]
            trace_unit = "sacas/kg"

        log_query_processing(
            source_name=function_name,
            original_count=original_count,
            final_count=len(results),
            post_filters=trace_filters,
            calculated_totals=trace_totals,
            unit=trace_unit,
            currency=trace_currency,
        )

        # Séries mensais são montadas somente depois dos filtros determinísticos
        # (cliente, filial, mercado, fixação etc.) terem sido aplicados.
        monthly_series = self._format_monthly_commercial_series(results, function_name)
        if monthly_series is not None:
            return monthly_series

        # Em compras, "qualidade" significa exclusivamente o campo ``linha``
        # retornado pela procedure. Esta saída determinística impede que o LLM
        # trate linha como a posição 1, 2, 3... do resultado.
        if (
            function_name in ("IA_Compras", "IA_ComprasPar")
            and self._is_purchase_quality_query()
        ):
            return self._format_purchase_quality_summary(results)

        # Totais de compras são sempre calculados no código, mesmo quando a
        # procedure retorna 50 registros ou menos. O modelo não soma linhas.
        if function_name in ("IA_Compras", "IA_ComprasPar") and self._is_purchase_total_query():
            return self._format_purchase_total_summary(results)

        # Estoque é sempre calculado e formatado deterministicamente, qualquer
        # que seja a quantidade de linhas. Isso elimina a antiga bifurcação em
        # que retornos com até 50 registros podiam ser somados pelo modelo.
        if function_name == "IA_Estoque":
            return self._format_stock_snapshot(results)

        # ESTRATÉGIA 2: Se muitos registros (>50) e sem filtro específico, agrega
        # MAS: Se mencionou número de contrato específico (XXX/YY), NÃO agrega
        # MAS: Se pergunta menciona critério específico que resulta em poucos registros (<= 10), NÃO agrega
        # MAS: Se pergunta menciona categoria específica de orçamento e resultou em poucos registros, NÃO agrega
        import re
        menciona_contrato = False
        menciona_criterio_especifico = False
        menciona_categoria_orcamento = False

        if self.user_query_original:
            query_lower = self.user_query_original.lower()

            # Padrão: número/ano (ex: 488/25, 453/25A, 513/25)
            # Não aceite outra barra após o ano curto: isso impede interpretar
            # datas como 12/08/2026 como se fossem o contrato 12/08.
            if re.search(r'(?<![\d/])\d{2,4}/\d{2}(?![\d/])[A-Z]?', self.user_query_original) and not self._extract_safra_code(self.user_query_original):
                menciona_contrato = True
                logger.info(f"[DETECÇÃO] Pergunta menciona contrato específico, NÃO vai agregar")

            # Critérios que geralmente resultam em poucos registros (VENDAS)
            criterios_especificos = [
                "sem valor fixado", "não tem valor fixado", "não fixado", "não fixados", "valor fixado null",
                "contratos fixados", "contratos já fixados", "vendas fixadas",
                "sem bl", "sem numero de bl", "não embarcado",
                "amostra pendente", "amostra não aprovada",
                "desse contrato", "deste contrato", "esse contrato", "este contrato",  # referência anafórica
            ]

            for criterio in criterios_especificos:
                if criterio in query_lower:
                    menciona_criterio_especifico = True
                    logger.info(f"[DETECÇÃO] Pergunta menciona critério específico '{criterio}', NÃO vai agregar se <= 10 resultados")
                    break

            # Categorias de orçamento (NÃO agrega se mencionar categoria específica)
            if function_name in ("IA_Orcamento", "IA_OrcamentoPar"):
                categorias_termos = ["combustivel", "combustível", "fumigacao", "fumigação", "manutenção", "manutencao", "depreciação", "depreciacao", "viagem"]
                for termo in categorias_termos:
                    if termo in query_lower:
                        menciona_categoria_orcamento = True
                        logger.info(f"[DETECÇÃO] Pergunta menciona categoria de orçamento '{termo}', NÃO vai agregar se <= 10 resultados")
                        break

        # Se menciona critério específico ou categoria e tem <= 10 resultados, não agrega
        nao_agregar_por_criterio = (menciona_criterio_especifico or menciona_categoria_orcamento) and len(results) <= 10

        # FORÇA agregação se a pergunta é sobre "baixados EM [mês]" ou "EM [mês]... baixados"
        # OU se menciona "embarcados" E "baixados" simultaneamente (precisa dos campos contratos_baixados_*)
        # USA user_query_original (sem contexto) para evitar falsos positivos
        forcar_agregacao_baixados = False
        if self.user_query_original:
            query_lower = self.user_query_original.lower()
            # Detecta: "baixados EM" OU "EM [mês]... baixados/pagos/quitados"
            if re.search(r'baixad[oa]s?\s+(no\s+contas\s+a\s+receber\s+)?em\s+', query_lower):
                forcar_agregacao_baixados = True
                logger.info(f"[AGREGAÇÃO FORÇADA] Padrão 'baixados EM' detectado")
            elif re.search(r'em\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)', query_lower) and \
                 re.search(r'(já\s+foram\s+)?(baixad[oa]s?|pagos?|quitad[oa]s?)\s+(financeiramente|no\s+contas)', query_lower):
                forcar_agregacao_baixados = True
                logger.info(f"[AGREGAÇÃO FORÇADA] Padrão 'EM [mês]... baixados/pagos' detectado")
            # NOVO: Detecta queries sobre "embarcados" E "não foram baixados" (precisa de agregação para contar corretamente)
            elif re.search(r'embarc(ad[oa]s?|aram|ou)', query_lower) and \
                 re.search(r'(não\s+foram\s+|ainda\s+não\s+)?(baixad[oa]s?|pagos?|quitad[oa]s?)', query_lower):
                forcar_agregacao_baixados = True
                logger.info(f"[AGREGAÇÃO FORÇADA] Padrão 'embarcados... (não) baixados' detectado")

        # Agrega se: muitos registros (>50) OU query sobre baixados
        # MAS não agrega se: menciona contrato específico OU critério específico com <= 10 resultados
        deve_agregar = (len(results) > 50 or forcar_agregacao_baixados) and not menciona_contrato and not nao_agregar_por_criterio

        if deve_agregar:
            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            # ORÇAMENTO: Agrega por categoria/grupo
            if function_name in ("IA_Orcamento", "IA_OrcamentoPar"):
                logger.info(f"[AGREGAÇÃO] {len(results)} registros de orçamento, agregando por categoria...")
                aggregated = self._aggregate_orcamento(results)

                # CALCULA TOTAIS (não deixa a IA somar manualmente para evitar erros)
                total_orcado = sum(item.get("orcado", 0) for item in aggregated)
                total_realizado = sum(item.get("realizado", 0) for item in aggregated)
                total_saldo = sum(item.get("saldo", 0) for item in aggregated)
                percentual_total = round((total_realizado / total_orcado) * 100, 2) if total_orcado > 0 else 0

                formatted = json.dumps(aggregated, ensure_ascii=False, indent=2, default=convert_decimals)

                return f"""Resultados da consulta {function_name} (AGREGADOS POR CATEGORIA):

Total de registros SQL: {original_count}
Total de categorias: {len(aggregated)}

TOTAIS GERAIS (PRÉ-CALCULADOS):
- Total Orçado: R$ {total_orcado:,.2f}
- Total Realizado: R$ {total_realizado:,.2f}
- Total Saldo: R$ {total_saldo:,.2f}
- Percentual Realizado: {percentual_total}%

Dados por categoria:
{formatted}

Instruções: Os dados acima são de ORÇAMENTO (budget vs realizado).

CAMPOS DISPONÍVEIS POR CATEGORIA:
- categoria: nome da categoria/grupo orçamentário (ex: "COMBUSTIVEL", "DESP COM FUMIGACAO")
- grupo: código do grupo (ex: "COMB", "DEFUM", "CTRME")
- orcado: valor orçado desta categoria (R$)
- realizado: valor realizado desta categoria (R$)
- saldo: saldo desta categoria (orcado - realizado, em R$)
- percentual_realizado: percentual realizado desta categoria (%)
- periodo: "Anual" ou "Mensal" (ou ambos se houver registros mistos)
- anos: anos incluídos nesta agregação (ex: "2025")
- meses: meses incluídos no formato YYYY/MM (ex: "2025/12, 2025/11")
- qtd_registros: quantidade de registros SQL agregados nesta categoria

IMPORTANTE - REGRAS CRÍTICAS:
1. ⚠️ SEMPRE USE OS "TOTAIS GERAIS (PRÉ-CALCULADOS)" PARA PERGUNTAS SOBRE TOTAIS!
   - "Qual o orçado total?" → Use "Total Orçado" dos TOTAIS GERAIS
   - "Quanto foi realizado?" → Use "Total Realizado" dos TOTAIS GERAIS
   - "Qual o percentual?" → Use "Percentual Realizado" dos TOTAIS GERAIS
   - NÃO some manualmente as categorias! Os TOTAIS GERAIS já estão corretos!

2. Orçamento NÃO tem contratos, sacas ou clientes. É uma previsão financeira (budget).

3. Para perguntas sobre CATEGORIAS ESPECÍFICAS:
   - "Quanto gastamos com combustível?" → Procure categoria "COMBUSTIVEL"
   - "Quanto foi orçado para fumigação?" → Procure categoria contendo "FUMIGACAO"
   - Use os campos "orcado", "realizado", "saldo" da categoria específica

4. Para perguntas sobre PERÍODOS:
   - Verifique o campo "meses" para saber quais meses estão incluídos
   - Verifique o campo "periodo" para saber se é "Anual" ou "Mensal"
   - Se pergunta é sobre um mês específico e os dados incluem múltiplos meses, AVISE o usuário

5. INTERPRETAÇÃO DOS VALORES:
   - saldo POSITIVO = gastamos MENOS que o orçado (sobrou)
   - saldo NEGATIVO = gastamos MAIS que o orçado (estourou)
   - percentual > 100% = gastamos MAIS que o orçado
   - percentual < 100% = gastamos MENOS que o orçado

Exemplos corretos:
- "Qual o orçado total?" → Use "Total Orçado" dos TOTAIS GERAIS
- "Quanto gastamos com combustível?" → Procure categoria "COMBUSTIVEL", use campo "realizado"
- "Estouramos o orçamento?" → Compare Total Realizado vs Total Orçado (se realizado > orçado, estourou)
- "Qual categoria mais estourou?" → Procure categoria com maior saldo NEGATIVO"""

            # ESTOQUE: Agrega por linha ou certificado
            elif function_name == "IA_Estoque":
                logger.info(f"[AGREGAÇÃO] {len(results)} registros de estoque, agregando...")
                aggregated = self._aggregate_estoque(results)

                # CALCULA TOTAIS (não deixa a IA somar manualmente para evitar erros)
                total_sacas = sum(item.get("sacas_total", 0) for item in aggregated)
                total_sacas_consumo = sum(item.get("sacas_consumo", 0) for item in aggregated)
                total_sacas_exportacao = sum(item.get("sacas_exportacao", 0) for item in aggregated)
                total_peso = sum(item.get("peso_kg", 0) for item in aggregated)
                total_lotes = sum(item.get("qtd_lotes", 0) for item in aggregated)

                # Determina critério de agregação
                criterio = "linha" if "linha" in aggregated[0] else "certificado"

                formatted = json.dumps(aggregated, ensure_ascii=False, indent=2, default=convert_decimals)

                return f"""Resultados da consulta {function_name} (AGREGADOS POR {criterio.upper()}):

Total de registros SQL: {original_count}
Total de {criterio}s: {len(aggregated)}

TOTAIS GERAIS (PRÉ-CALCULADOS):
- Total de Sacas: {total_sacas:,.2f} sacas
- Sacas para Consumo: {total_sacas_consumo:,.2f} sacas
- Sacas para Exportação: {total_sacas_exportacao:,.2f} sacas
- Peso Total: {total_peso:,.2f} kg
- Total de Lotes: {total_lotes}

Dados por {criterio}:
{formatted}

Instruções: Os dados acima são de ESTOQUE (snapshot atual).

CAMPOS DISPONÍVEIS POR {criterio.upper()}:
- {criterio}: tipo de {criterio} (ex: "PVA", "GRD" para linha; "RF", "4C" para certificado)
- sacas_total: total de sacas deste {criterio}
- sacas_consumo: sacas para consumo interno/mercado interno
- sacas_exportacao: sacas para exportação
- peso_kg: peso total em quilogramas
- qtd_lotes: quantidade de lotes diferentes
- qtd_registros: quantidade de registros SQL agregados
- filiais: filiais onde este estoque está localizado
- armazens: armazéns onde este estoque está localizado
- {'certificados: certificações presentes neste tipo de café' if criterio == 'linha' else 'linhas: linhas/tipos presentes neste certificado'}

IMPORTANTE - REGRAS CRÍTICAS:
1. ⚠️ SEMPRE USE OS "TOTAIS GERAIS (PRÉ-CALCULADOS)" PARA PERGUNTAS SOBRE TOTAIS!
   - "Quantas sacas temos?" → Use "Total de Sacas" dos TOTAIS GERAIS
   - "Quanto café temos?" → Use "Total de Sacas" e "Peso Total" dos TOTAIS GERAIS
   - "Sacas para exportação?" → Use "Sacas para Exportação" dos TOTAIS GERAIS
   - NÃO some manualmente! Os TOTAIS GERAIS já estão corretos!

2. Estoque NÃO tem contratos ou clientes. É um snapshot atual do estoque físico.

3. Para perguntas sobre TIPOS ESPECÍFICOS:
   - "Quanto café PVA temos?" → Procure {criterio} "PVA", use campo "sacas_total"
   - "Café Rainforest?" → Procure certificado "RF", use campo "sacas_total"
   - Use os campos apropriados do tipo específico
   - Ao separar por certificado, mantenha o código exato do grupo retornado (ex: "RF", "4C", "GCP").
   - Não junte certificados parecidos e não renomeie "RF" para "RF (Rainforest)" sem o usuário pedir descrição.

4. PESO E SACAS:
   - O campo peso é o peso real em kg e deve ter prioridade sobre estimativas.
   - Peso e sacas são campos independentes; NÃO faça conversões no modelo.
   - Quando não houver peso real, somente o código pode aplicar o fator padrão de 60 kg/saca e deve informá-lo.
   - Se a relação efetiva do banco for 59 kg/saca ou outro valor, preserve-a e explique que veio de peso real ÷ sacas.

5. INTERPRETAÇÃO DOS VALORES:
   - sacas_total = sacas_consumo + sacas_exportacao (sempre)
   - Se perguntam "para consumo", use sacas_consumo
   - Se perguntam "para exportação", use sacas_exportacao
   - Se perguntam "total", use sacas_total

Exemplos corretos:
- "Quantas sacas temos?" → Use "Total de Sacas" dos TOTAIS GERAIS
- "Quanto café PVA?" → Procure {criterio} "PVA", use campo "sacas_total"
- "Sacas para exportação?" → Use "Sacas para Exportação" dos TOTAIS GERAIS
- "Qual tipo tem mais café?" → Procure {criterio} com maior "sacas_total" """

            # COMPRAS: usa esquema e métricas próprios. Nunca passa compras pela
            # agregação de vendas, que espera cliente/contrato/valorTotal.
            elif function_name in ("IA_Compras", "IA_ComprasPar"):
                logger.info(
                    f"[AGREGAÇÃO COMPRAS] {len(results)} registros, "
                    "agregando por fornecedor e moeda..."
                )
                metrics = aggregate_purchases(results)
                totals_lines = []
                for total in metrics["totais_por_moeda"]:
                    currency = total["moeda"]
                    currency_label = currency
                    average = total["media_ponderada"]
                    average_label = (
                        format_pt_br(average) if average is not None else "N/A"
                    )
                    totals_lines.append(
                        f"- {currency_label}: valor {format_pt_br(total['valor_total'])} | "
                        f"quantidade {format_pt_br(total['quantidade_total'])} | "
                        f"média ponderada {average_label}"
                    )

                suppliers = metrics["fornecedores"][:50]
                suppliers_json = json.dumps(
                    suppliers, ensure_ascii=False, indent=2, default=convert_decimals
                )
                return f"""RESULTADO DETERMINÍSTICO DE COMPRAS

Total de contratos/pedidos únicos: {metrics['total_contratos']}

TOTAIS SEPARADOS POR MOEDA:
{chr(10).join(totals_lines)}

FORNECEDORES (ordenados pelo valor dos registros de compra):
{suppliers_json}

REGRAS OBRIGATÓRIAS:
- Estes dados são exclusivamente de COMPRAS. Não os apresente como vendas.
- Não some valores de moedas diferentes.
- Quando a origem não informar a moeda, os valores de compras devem ser considerados BRL.
- A média oficial é a média ponderada: valor total dividido pela quantidade total.
- Formate números no padrão pt-BR."""

            # VENDAS: Agrega por cliente
            elif function_name == "IA_Vendas":
                logger.info(f"[AGREGAÇÃO] {len(results)} registros, agregando por cliente...")

                # Monta lista completa de todos os identificadores ANTES da agregação
                # Isso evita que o LLM invente registros ao listar (hallucination)
                # Tenta vários campos identificadores: contrato (vendas), numero/solicitacao (compras)
                identificador_campo = None
                for campo_id in ["contrato", "numero", "solicitacao"]:
                    if any(row.get(campo_id) for row in results[:5]):
                        identificador_campo = campo_id
                        break

                todos_contratos_raw = []
                if identificador_campo:
                    # Inclui filial na chave para não perder contratos com mesmo número em filiais diferentes
                    for row in results:
                        c = str(row.get(identificador_campo, "")).strip()
                        if not c:
                            continue
                        filial_r = str(row.get('filial') or '').strip()
                        chave = f"{c} [fil.{filial_r}]" if filial_r else c
                        todos_contratos_raw.append(chave)

                todos_contratos_unicos = sorted(set(c for c in todos_contratos_raw if c))
                lista_completa_contratos_str = ", ".join(todos_contratos_unicos)
                logger.info(f"[LISTA COMPLETA] Campo='{identificador_campo}', {len(todos_contratos_unicos)} registros únicos mapeados")

                # Monta tabela compacta por contrato com dados individuais (evita erro de valor por cliente)
                # Usa identificador_campo detectado (contrato para vendas, numero para compras, etc.)
                tabela_por_contrato = []
                vistos = set()

                def _fmt_decimal(v):
                    if v is None:
                        return "0"
                    if isinstance(v, Decimal):
                        return f"{float(v):,.2f}"
                    if isinstance(v, (int, float)):
                        return f"{v:,.2f}"
                    return str(v)

                for row in results:
                    c = str(row.get(identificador_campo or "contrato", "")).strip()
                    filial_row = str(row.get('filial') or '').strip()
                    chave_dedup = f"{c}_{filial_row}" if filial_row else c
                    if not c or chave_dedup in vistos:
                        continue
                    vistos.add(chave_dedup)
                    # Tenta campos de parte/contraparte em ordem (vendas=cliente, compras=fornecedor)
                    contraparte = str(row.get('cliente') or row.get('fornecedor') or row.get('produtor') or '').strip()
                    # Tenta campos de quantidade (vendas=sacas, compras=quantidade)
                    qtd = row.get('sacas') or row.get('quantidade') or row.get('qtd')
                    # Tenta campos de valor
                    valor = row.get('valorTotal') or row.get('valor') or row.get('valorContrato')
                    # Tenta campo de data/mês
                    data = str(row.get('mesEmbarque') or row.get('dataEmissao') or row.get('data') or '').strip()
                    filial_label = f" [fil.{filial_row}]" if filial_row else ""
                    tabela_por_contrato.append(
                        f"{c}{filial_label} | {contraparte} | "
                        f"{_fmt_decimal(qtd)} sacas | "
                        f"USD {_fmt_decimal(valor)} | "
                        f"{data}"
                    )
                # Até 100 contratos cabem em uma única consulta e são posteriormente
                # divididos pelo serviço do WhatsApp em mensagens menores.
                PAGE_SIZE = 100
                idx_inicio = (pagina - 1) * PAGE_SIZE
                idx_fim = idx_inicio + PAGE_SIZE
                tabela_exibida = tabela_por_contrato[idx_inicio:idx_fim]
                tabela_por_contrato_str = "\n".join(tabela_exibida)
                logger.info(f"[TABELA CONTRATOS] {len(tabela_por_contrato)} contratos total, exibindo página {pagina} ({idx_inicio+1}-{min(idx_fim, len(tabela_por_contrato))})")

                branch_terms_query = self.user_query_original.lower() if self.user_query_original else ""
                pediu_agrupamento_filial = bool(
                    re.search(
                        r'\b(por|separad[ao]s?\s+por|separar\s+por|agrupad[ao]s?\s+por)\s+'
                        r'(filiai?s?|empresa?s?)\b',
                        branch_terms_query
                    )
                )
                if pediu_agrupamento_filial:
                    branch_metrics = aggregate_sales_by_branch(results)
                    total_contratos_filiais = sum(item["contratos"] for item in branch_metrics)
                    total_sacas_filiais = sum(item["sacas"] for item in branch_metrics)
                    total_valor_filiais = sum(item["valor_usd"] for item in branch_metrics)
                    branch_lines = [
                        f"- {item['empresa']} (filial {item['filial']}): "
                        f"{item['contratos']} contrato(s) | "
                        f"{format_pt_br(item['sacas'])} sacas | "
                        f"USD {format_pt_br(item['valor_usd'])} | "
                        f"{item['clientes']} cliente(s)"
                        for item in branch_metrics
                    ]

                    return f"""RESULTADO DETERMINÍSTICO DE VENDAS POR EMPRESA/FILIAL

Total geral: {total_contratos_filiais} contrato(s) | {format_pt_br(total_sacas_filiais)} sacas | USD {format_pt_br(total_valor_filiais)}

TOTAIS POR EMPRESA/FILIAL:
{chr(10).join(branch_lines)}

MAPEAMENTO OBRIGATÓRIO:
- filial 05 = COBRA
- filial 60 = CUSA
- filial 61 = CEU

REGRAS OBRIGATÓRIAS:
- Estes dados são exclusivamente de VENDAS.
- A coluna valorTotal da usp_IA_Vendas está SEMPRE em USD.
- Não apresente valorTotal como R$.
- Se o usuário pedir em real ou comparar com valores em BRL, converta explicitamente com cotação antes.
- Se o usuário pedir uma empresa específica, use apenas a filial correspondente."""

                aggregated = self._aggregate_by_client(results)

                # Se _aggregate_by_client retornou uma STRING (otimização especial), retorna direto
                if isinstance(aggregated, str):
                    logger.info(f"[OTIMIZAÇÃO] Retornando string formatada diretamente")
                    return aggregated

                # CALCULA TOTAIS GERAIS (não deixa a IA somar manualmente para evitar erros)
                total_contratos = sum(item.get("total_contratos", 0) for item in aggregated)
                # Fallback: se agregação retornou 0 contratos (ex: compras usa "numero" não "contrato"),
                # usa a lista completa de identificadores únicos que foi corretamente mapeada
                if total_contratos == 0 and todos_contratos_unicos:
                    total_contratos = len(todos_contratos_unicos)
                    logger.info(f"[TOTAL CONTRATOS] Fallback: usando {total_contratos} de todos_contratos_unicos")
                total_sacas = sum(item.get("total_sacas", 0) for item in aggregated)
                total_valor = sum(item.get("total_valor", 0) for item in aggregated)

                # CALCULA DIFERENCIAL MÉDIO GLOBAL (dedup por contrato+filial)
                dif_values_global = []
                dif_vistos_global = set()
                for row in results:
                    c_dif = str(row.get(identificador_campo or "contrato", "")).strip()
                    f_dif = str(row.get('filial') or '').strip()
                    chave_dif = f"{c_dif}_{f_dif}" if f_dif else c_dif
                    if not c_dif or chave_dif in dif_vistos_global:
                        continue
                    dif_vistos_global.add(chave_dif)
                    d = row.get("diferencial")
                    if d is not None:
                        try:
                            dif_values_global.append(float(d))
                        except (TypeError, ValueError):
                            pass
                diferencial_global = round(sum(dif_values_global) / len(dif_values_global), 4) if dif_values_global else None

                # AGREGA CONTRATOS POR PAÍS (usando dados originais para não perder relação)
                from collections import defaultdict
                contratos_por_pais = defaultdict(lambda: {"contratos": [], "sacas": 0, "clientes": set()})

                for row in results:
                    pais = row.get("pais", "").strip() or "SEM PAÍS"
                    contrato = row.get("contrato", "").strip()
                    cliente = row.get("cliente", "SEM CLIENTE")
                    sacas = row.get("sacas", 0) or 0

                    if contrato and contrato not in contratos_por_pais[pais]["contratos"]:
                        contratos_por_pais[pais]["contratos"].append(contrato)
                    contratos_por_pais[pais]["sacas"] += sacas
                    contratos_por_pais[pais]["clientes"].add(cliente)

                # Formata contratos por país para exibição
                contratos_pais_str = ""
                for pais in sorted(contratos_por_pais.keys()):
                    dados = contratos_por_pais[pais]
                    qtd_contratos = len(dados["contratos"])
                    qtd_clientes = len(dados["clientes"])
                    contratos_list = dados["contratos"][:20]  # Limita a 20 primeiros
                    contratos_str = ", ".join(contratos_list)
                    if len(dados["contratos"]) > 20:
                        contratos_str += f" (e mais {len(dados['contratos']) - 20})"

                    contratos_pais_str += f"\n  • {pais}: {qtd_contratos} contrato(s), {dados['sacas']:,.2f} sacas, {qtd_clientes} cliente(s)\n    Contratos: {contratos_str}"

                vendas_por_filial = aggregate_sales_by_branch(results)
                vendas_filial_str = ""
                for item in vendas_por_filial:
                    vendas_filial_str += (
                        f"\n  • {item['empresa']} (filial {item['filial']}): "
                        f"{item['contratos']} contrato(s), "
                        f"{format_pt_br(item['sacas'])} sacas, "
                        f"USD {format_pt_br(item['valor_usd'])}, "
                        f"{item['clientes']} cliente(s)"
                    )

                formatted = json.dumps(aggregated, ensure_ascii=False, indent=2, default=convert_decimals)

                # SUMÁRIO ESPECIAL: Se query é sobre "embarcados não baixados", calcula explicitamente
                # USA user_query_original (sem contexto) para evitar falsos positivos
                sumario_embarcados_nao_baixados = ""
                if self.user_query_original and re.search(r'embarc(ad[oa]s?|aram|ou)', self.user_query_original.lower()) and \
                   re.search(r'(não\s+foram\s+|ainda\s+não\s+)?(baixad[oa]s?|pagos?|quitad[oa]s?)', self.user_query_original.lower()):
                    # Calcula total de contratos embarcados não baixados
                    total_embarcados_nao_baixados = 0
                    clientes_com_nao_baixados = []

                    for cliente_data in aggregated:
                        # Contratos embarcados
                        embarcados_str = cliente_data.get("contratos_embarcados", "")
                        embarcados_set = set()
                        if embarcados_str:
                            for c in embarcados_str.split(','):
                                c = c.strip()
                                if c:
                                    embarcados_set.add(c)

                        # Contratos baixados (união de todos os meses)
                        baixados_set = set()
                        for campo in ['contratos_baixados_nov2025', 'contratos_baixados_dez2025', 'contratos_baixados_jan2026']:
                            baixados_str = cliente_data.get(campo, "")
                            if baixados_str:
                                for c in baixados_str.split(','):
                                    c = c.strip()
                                    if c:
                                        baixados_set.add(c)

                        # Não baixados = embarcados - baixados
                        nao_baixados_set = embarcados_set - baixados_set
                        if len(nao_baixados_set) > 0:
                            total_embarcados_nao_baixados += len(nao_baixados_set)
                            clientes_com_nao_baixados.append({
                                'cliente': cliente_data.get('cliente', '').strip(),
                                'qtd': len(nao_baixados_set),
                                'contratos': sorted(list(nao_baixados_set))[:5]
                            })

                    # Ordena por quantidade (maior primeiro)
                    clientes_com_nao_baixados.sort(key=lambda x: x['qtd'], reverse=True)

                    # Formata sumário
                    sumario_embarcados_nao_baixados = f"""\n⚠️ SUMÁRIO PARA ESTA QUERY ESPECÍFICA:

🔍 CONTRATOS EMBARCADOS QUE AINDA NÃO FORAM BAIXADOS: {total_embarcados_nao_baixados} contratos

Distribuição por cliente (top 5):"""
                    for i, item in enumerate(clientes_com_nao_baixados[:5], 1):
                        contratos_resumo = ", ".join(item['contratos'])
                        if item['qtd'] > 5:
                            contratos_resumo += f" (e mais {item['qtd'] - 5})"
                        sumario_embarcados_nao_baixados += f"\n  {i}. {item['cliente']}: {item['qtd']} contrato(s) - {contratos_resumo}"

                    sumario_embarcados_nao_baixados += f"\n\n⚠️ IMPORTANTE: Use este número ({total_embarcados_nao_baixados} contratos) para responder ao usuário!\n"
                    logger.info(f"[SUMÁRIO ESPECIAL] Calculado: {total_embarcados_nao_baixados} contratos embarcados não baixados")

                total_paginas = max(1, (len(tabela_por_contrato) + PAGE_SIZE - 1) // PAGE_SIZE)
                ha_mais_paginas = pagina < total_paginas
                aviso_paginacao = ""
                if ha_mais_paginas:
                    aviso_paginacao = f"\n⚠️ HÁ MAIS CONTRATOS: Esta é a página {pagina} de {total_paginas}. Chame pesquisa_vendas(periodo=..., pagina={pagina+1}) para ver os próximos contratos."

                return f"""⚠️ TOTAL_EXATO: {total_contratos} contratos | {total_sacas:,.2f} sacas | USD {total_valor:,.2f}
REGRA OBRIGATÓRIA: Use SEMPRE o número {total_contratos} ao responder sobre quantidade total de contratos.{aviso_paginacao}
REGRA OBRIGATÓRIA DE MOEDA: Em IA_Vendas/usp_IA_Vendas, a coluna valorTotal SEMPRE está em USD. Nunca rotule valorTotal como R$.
Se o usuário pedir em real, ou pedir comparação com valores em BRL, informe que é necessário converter usando uma cotação de câmbio antes de somar ou comparar.

Resultados da consulta {function_name} (AGREGADOS POR CLIENTE):{sumario_embarcados_nao_baixados}

Total de registros SQL: {original_count}
Total de clientes: {len(aggregated)}
Página: {pagina}/{total_paginas} (contratos {(pagina-1)*PAGE_SIZE+1}–{min(pagina*PAGE_SIZE, len(tabela_por_contrato))} de {len(tabela_por_contrato)})

TOTAIS GERAIS (PRÉ-CALCULADOS):
- Total de Contratos: {total_contratos}
- Total de Sacas: {total_sacas:,.2f}
- Valor Total: USD {total_valor:,.2f}
- Diferencial Médio: {f'{diferencial_global:,.4f}' if diferencial_global is not None else 'N/A'}

⚠️ TABELA INDIVIDUAL POR CONTRATO - página {pagina}/{total_paginas} (contrato | cliente | sacas | valorTotal | mesEmbarque):
{tabela_por_contrato_str}

⚠️ CRÍTICO - REGRA ANTI-ALUCINAÇÃO:
- Use SOMENTE os contratos da tabela acima. NUNCA invente contratos inexistentes.
- Para valor de cada contrato, use a coluna "valorTotal" da tabela acima, SEMPRE em USD.
- NUNCA apresente valorTotal de IA_Vendas como R$. Se precisar responder em reais, converta explicitamente com uma cotação informada/disponível.
- NUNCA compare ou some valorTotal de vendas com campos em BRL sem converter primeiro para a mesma moeda.
- NUNCA use o total do cliente para representar o valor de um contrato individual.
- Se um cliente tem 4 contratos com valores diferentes, cada contrato tem seu próprio valor.

CONTRATOS POR PAÍS (use esta seção para perguntas sobre países específicos):{contratos_pais_str}

TOTAIS POR EMPRESA/FILIAL (use esta seção quando o usuário pedir por filial, por empresa, COBRA, CUSA ou CEU):{vendas_filial_str}

MAPEAMENTO DE FILIAIS:
- filial 05 = COBRA
- filial 60 = CUSA
- filial 61 = CEU

Dados agregados:
{formatted}

Instruções: Os dados acima estão AGREGADOS por cliente. Cada linha mostra:

TOTAIS (PRÉ-CALCULADOS):
- total_contratos: quantidade de contratos daquele cliente
- total_sacas: soma de sacas de todos os contratos
- total_valor: soma do valor total de todos os contratos (em USD; vem de valorTotal)

MÉDIAS (PRÉ-CALCULADAS):
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
- vendedores: lista de todos os vendedores únicos
- filiais: lista de todas as filiais únicas
- grupos_venda: lista de todos os grupos de venda únicos

INFORMAÇÕES LOGÍSTICAS E ADMINISTRATIVAS:
- contratos_com_bl: lista de contratos que possuem número de BL (até 20 primeiros)
- total_contratos_com_bl: quantidade total de contratos com BL
- contratos_embarcados: lista de contratos que já embarcaram (até 20 primeiros)
- total_contratos_embarcados: quantidade total de contratos embarcados

  ⚠️ ATENÇÃO - CONTRATOS SEM BL:
  Para calcular contratos SEM BL, use: total_contratos - total_contratos_com_bl
  NÃO confunda com total_contratos_embarcados (são coisas diferentes!)
  Exemplo: Se tem 107 contratos e 52 com BL, então 107 - 52 = 55 SEM BL
- contratos_amostra_enviada: lista de contratos que enviaram amostra (até 20 primeiros)
- total_contratos_amostra_enviada: quantidade de contratos que enviaram amostra
- contratos_amostra_aprovada: lista de contratos com amostra aprovada (até 20 primeiros)
- total_contratos_amostra_aprovada: quantidade de contratos com amostra aprovada
- contratos_amostra_pendente: lista de contratos que ENVIARAM amostra mas NÃO APROVARAM ainda (até 20 primeiros)
- total_contratos_amostra_pendente: quantidade de contratos com amostra pendente de aprovação
- contratos_baixados: lista de contratos baixados financeiramente no formato "CONTRATO (YYYYMMDD)" onde YYYYMMDD é a data de baixa (até 100 primeiros)
- total_contratos_baixados: quantidade de contratos baixados (TODAS as datas)

⚠️⚠️⚠️ ATENÇÃO CRÍTICA - NÃO CONFUNDA MÊS DE EMBARQUE COM MÊS DE BAIXA! ⚠️⚠️⚠️

CONTRATOS BAIXADOS POR MÊS ESPECÍFICO (use estes campos para queries com data de BAIXA):
- contratos_baixados_jan2026: lista de contratos QUE FORAM PAGOS/BAIXADOS EM janeiro/2026 (até 100)
- total_baixados_jan2026: quantidade de contratos QUE FORAM PAGOS/BAIXADOS em janeiro/2026
- contratos_baixados_dez2025: lista de contratos QUE FORAM PAGOS/BAIXADOS EM dezembro/2025 (até 100)
- total_baixados_dez2025: quantidade de contratos QUE FORAM PAGOS/BAIXADOS em dezembro/2025
- contratos_baixados_nov2025: lista de contratos QUE FORAM PAGOS/BAIXADOS EM novembro/2025 (até 100)
- total_baixados_nov2025: quantidade de contratos QUE FORAM PAGOS/BAIXADOS em novembro/2025

  ⚠️⚠️⚠️ REGRA ABSOLUTA - LEIA COM MUITA ATENÇÃO ⚠️⚠️⚠️

  "Contratos EM [mês] [ano]" pode significar DUAS COISAS DIFERENTES:

  1️⃣ "Contratos COM EMBARQUE em nov/dez 2025" → Use o filtro de período (mesEmbarque)
     Exemplo: "Quantos contratos do cliente X em novembro 2025?"
     → Significa contratos que EMBARCARAM em nov/2025
     → Use pesquisa_vendas(periodo="novembro 2025")

  2️⃣ "Contratos QUE FORAM BAIXADOS/PAGOS em nov/dez 2025" → Use os campos contratos_baixados_*
     Exemplo: "Quantos contratos do cliente X foram baixados em novembro 2025?"
     → Significa contratos que foram PAGOS/BAIXADOS em nov/2025 (independente de quando embarcaram)
     → Use contratos_baixados_nov2025 e total_baixados_nov2025

  PALAVRAS-CHAVE que indicam BAIXA (opção 2):
  - "baixados em", "foram baixados", "já foram baixados"
  - "pagos em", "foram pagos", "já foram pagos"
  - "quitados em", "foram quitados"
  - "baixados financeiramente"
  - "baixados no contas a receber"

  Se a pergunta NÃO contém essas palavras-chave → é sobre EMBARQUE (opção 1)

  EXEMPLO REAL:
  ❌ ERRADO: "Contratos do FREY A/S em novembro 2025 já foram baixados?"
     → A IA NÃO deve responder "2 contratos foram baixados em nov/2025"
     → Os contratos embarcaram em nov/2025, mas foram baixados em JAN/2026!

  ✅ CORRETO: Verificar a data REAL de baixa nos campos contratos_baixados_*
     → Se contratos_baixados_nov2025 estiver vazio → responder "0 contratos foram baixados em nov/2025"
     → Verificar contratos_baixados_jan2026 para ver quando foram realmente baixados

  COMO USAR OS CAMPOS:
  - Para "contratos baixados EM janeiro 2026" → use contratos_baixados_jan2026 e total_baixados_jan2026
  - Para "contratos baixados EM dezembro 2025" → use contratos_baixados_dez2025 e total_baixados_dez2025
  - Para "contratos baixados EM novembro 2025" → use contratos_baixados_nov2025 e total_baixados_nov2025
  - NÃO use total_contratos_baixados para queries com data específica (ele conta TODOS os meses)

IMPORTANTE - REGRAS CRÍTICAS:
1. ⚠️ SEMPRE USE OS "TOTAIS GERAIS (PRÉ-CALCULADOS)" ACIMA PARA PERGUNTAS SOBRE TOTAIS!
   - "Quantas sacas?" → Use "Total de Sacas" dos TOTAIS GERAIS
   - "Quantos contratos?" → Use "Total de Contratos" dos TOTAIS GERAIS
   - "Qual o valor total?" → Use "Valor Total" dos TOTAIS GERAIS
   - NÃO SOME manualmente os valores por cliente! Os TOTAIS GERAIS já estão corretos!

2. ⚠️ PARA PERGUNTAS SOBRE PAÍSES ESPECÍFICOS, USE A SEÇÃO "CONTRATOS POR PAÍS"!
   - "Quantas sacas para Argentina?" → Procure Argentina na seção CONTRATOS POR PAÍS
   - "Quais contratos para país X?" → Use a lista de contratos da seção CONTRATOS POR PAÍS
   - NÃO procure país por país nos dados agregados por cliente!
   - A seção CONTRATOS POR PAÍS mostra TODOS os contratos de cada país, mesmo que estejam em clientes diferentes!

3. ⚠️ PARA PERGUNTAS POR FILIAL/EMPRESA, USE A SEÇÃO "TOTAIS POR EMPRESA/FILIAL"!
   - "COBRA" = filial 05
   - "CUSA" = filial 60
   - "CEU" = filial 61
   - Se o usuário pedir uma dessas empresas, responda apenas com a filial correspondente.
   - Os valores dessa seção estão em USD, pois vêm de valorTotal da usp_IA_Vendas.

4. ⚠️ PARA PERGUNTAS SOBRE MERCADO INTERNO/EXTERNO:
   - "Mercado interno" = coluna MERCADO igual a INTERNO.
   - "Mercado externo" = coluna MERCADO igual a EXTERNO.
   - Não use filial nem país para inferir mercado; use apenas a coluna MERCADO.

5. TODAS as médias acima estão PRÉ-CALCULADAS. USE OS VALORES DIRETAMENTE.
6. NÃO tente recalcular médias manualmente.
7. Cada campo de média (ex: diferencial_medio) já considera TODOS os contratos daquele cliente.
8. Para perguntas sobre médias, use SEMPRE os campos _medio/_media fornecidos.
9. PENEIRAS: Use apenas peneira_mtgb_media, peneira_grauda_media, peneira_grinder_media.
   NÃO extraia tamanhos de peneira das descrições de qualidade (ex: "13 UP", "17/18").

Exemplos corretos de uso:
- "Quantas sacas foram exportadas?" → Use "Total de Sacas" dos TOTAIS GERAIS
- "Quantos contratos?" → Use "Total de Contratos" dos TOTAIS GERAIS
- "Qual o valor total?" → Use "Valor Total" dos TOTAIS GERAIS
- "Qual o diferencial médio?" → Use o campo diferencial_medio DIRETAMENTE
- "Quais certificados?" → Use o campo certificados
- "Qual o preço médio?" → Use valor_unitario_medio ou valor_fixado_medio DIRETAMENTE
- "Quais qualidades de café?" → Use o campo qualidades
- "Para quais países?" → Use o campo paises
- "Quais as peneiras?" → Use peneira_mtgb_media/peneira_grauda_media/peneira_grinder_media
- "Quais contratos têm BL?" → Use contratos_com_bl e total_contratos_com_bl
- "Quantos contratos NÃO têm BL?" → Calcule: total_contratos - total_contratos_com_bl
- "Quais contratos já embarcaram?" → Use contratos_embarcados e total_contratos_embarcados
- "Quais contratos enviaram amostra?" → Use contratos_amostra_enviada e total_contratos_amostra_enviada
- "Quais contratos aprovaram amostra?" → Use contratos_amostra_aprovada e total_contratos_amostra_aprovada
- "Quais contratos enviaram mas não aprovaram amostra?" → Use contratos_amostra_pendente e total_contratos_amostra_pendente
- "Quais vendedores?" → Use o campo vendedores
- "Quantos contratos foram baixados?" → Use total_contratos_baixados

{"" if not (self.user_query_original and any(p in self.user_query_original.lower() for p in ["todas", "todos", "liste", "listar", "informe", "mostre", "traga", "quais"])) else f"""
⚠️⚠️⚠️ INSTRUÇÃO OBRIGATÓRIA - O USUÁRIO PEDIU LISTA COMPLETA ⚠️⚠️⚠️

O usuário quer ver TODOS os {len(tabela_por_contrato)} contratos listados na TABELA INDIVIDUAL acima.

✅ VOCÊ DEVE listar TODOS os {len(tabela_por_contrato)} contratos numerados de 1 a {len(tabela_por_contrato)}!
✅ Para cada contrato, use os dados da TABELA INDIVIDUAL (contrato | cliente | sacas | valorTotal | mesEmbarque)
❌ NÃO mostre apenas alguns exemplos e diga "existem mais"!
❌ NÃO agrupe por cliente - liste cada contrato individualmente!
❌ NÃO invente valores - use SOMENTE o valorTotal da TABELA INDIVIDUAL!

Formato: "N. [contrato] ([cliente]) - USD [valorTotal]" para cada um dos {len(tabela_por_contrato)} contratos."""}"""

        # ESTRATÉGIA 3: Poucos registros (<= 50), envia completo
        warning = ""

        # FILTRO POR CONTRATO ESPECÍFICO: Se menciona contrato, filtra ANTES de limitar a 50
        # Isso garante que o contrato solicitado esteja nos resultados mesmo com >50 registros
        if menciona_contrato and self.user_query_original:
            import re
            # Extrai número do contrato da pergunta (ex: "087/25A", "453/25", "512/25B")
            # (?![\d/]) impede capturar o início de datas como 12/08/2026.
            match = re.search(r'(?<![\d/])(\d{2,4}/\d{2}(?![\d/])[A-Z]?)', self.user_query_original, re.IGNORECASE)
            if match:
                contrato_solicitado = match.group(1).upper()
                logger.info(f"[FILTRO CONTRATO] Contrato específico solicitado: {contrato_solicitado}")

                contrato_normalizado = self._normalizar_contrato(contrato_solicitado)
                logger.info(f"[FILTRO CONTRATO] Contrato normalizado: {contrato_normalizado}")

                # Filtra resultados pelo contrato (tenta match exato e normalizado)
                results_filtrados = []
                for r in results:
                    contrato_db = str(r.get("contrato", "")).upper().strip()
                    contrato_db_normalizado = self._normalizar_contrato(contrato_db)

                    # Match se contrato solicitado está no DB (substring) OU versões normalizadas são iguais
                    if (contrato_solicitado in contrato_db or
                        contrato_normalizado in contrato_db_normalizado or
                        contrato_db_normalizado == contrato_normalizado):
                        results_filtrados.append(r)

                if results_filtrados:
                    logger.info(f"[FILTRO CONTRATO] Encontrados {len(results_filtrados)} registros do contrato {contrato_solicitado}")
                    results = results_filtrados
                    total_records = len(results_filtrados)
                else:
                    logger.warning(f"[FILTRO CONTRATO] Contrato {contrato_solicitado} NÃO encontrado nos {len(results)} resultados")

        # DEDUPULICAÇÃO: Remove contratos duplicados (mesmo contrato+filial+cliente)
        # Bug: stored procedure pode retornar mesmo contrato múltiplas vezes
        if function_name == "IA_Vendas":
            contratos_vistos = set()
            results_dedup = []

            for r in results:
                # Chave única: contrato + filial + cliente
                # IMPORTANTE: Incluir cliente porque mesmo contrato pode ter clientes diferentes (raro mas possível)
                contrato = str(r.get('contrato', '')).strip()
                filial = str(r.get('filial', '')).strip()
                cliente = str(r.get('cliente', '')).strip()
                chave = f"{contrato}_{filial}_{cliente}"

                if chave not in contratos_vistos:
                    contratos_vistos.add(chave)
                    results_dedup.append(r)
                else:
                    logger.warning(f"[VENDAS] Contrato duplicado removido: {contrato} - {cliente}")

            if len(results_dedup) < len(results):
                logger.info(f"[VENDAS] Dedupulicação: {len(results)} → {len(results_dedup)} registros ({len(results) - len(results_dedup)} duplicatas removidas)")
                results = results_dedup
                total_records = len(results_dedup)

            branch_terms_query = self.user_query_original.lower() if self.user_query_original else ""
            pediu_agrupamento_filial = bool(
                re.search(
                    r'\b(por|separad[ao]s?\s+por|separar\s+por|agrupad[ao]s?\s+por)\s+'
                    r'(filiai?s?|empresa?s?)\b',
                    branch_terms_query
                )
            )
            if pediu_agrupamento_filial:
                branch_metrics = aggregate_sales_by_branch(results)
                total_contratos_filiais = sum(item["contratos"] for item in branch_metrics)
                total_sacas_filiais = sum(item["sacas"] for item in branch_metrics)
                total_valor_filiais = sum(item["valor_usd"] for item in branch_metrics)
                branch_lines = [
                    f"- {item['empresa']} (filial {item['filial']}): "
                    f"{item['contratos']} contrato(s) | "
                    f"{format_pt_br(item['sacas'])} sacas | "
                    f"USD {format_pt_br(item['valor_usd'])} | "
                    f"{item['clientes']} cliente(s)"
                    for item in branch_metrics
                ]

                return f"""RESULTADO DETERMINÍSTICO DE VENDAS POR EMPRESA/FILIAL

Total geral: {total_contratos_filiais} contrato(s) | {format_pt_br(total_sacas_filiais)} sacas | USD {format_pt_br(total_valor_filiais)}

TOTAIS POR EMPRESA/FILIAL:
{chr(10).join(branch_lines)}

MAPEAMENTO OBRIGATÓRIO:
- filial 05 = COBRA
- filial 60 = CUSA
- filial 61 = CEU

REGRAS OBRIGATÓRIAS:
- Estes dados são exclusivamente de VENDAS.
- A coluna valorTotal da usp_IA_Vendas está SEMPRE em USD.
- Não apresente valorTotal como R$.
- Se o usuário pedir em real ou comparar com valores em BRL, converta explicitamente com cotação antes.
- Se o usuário pedir uma empresa específica, use apenas a filial correspondente."""

        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        formatted = json.dumps(results, ensure_ascii=False, indent=2, default=convert_decimals)

        # Instruções específicas por tipo de função SQL
        FUNCTION_INSTRUCTIONS = {
            "IA_Orcamento": """
COLUNAS DISPONÍVEIS EM ORÇAMENTO:
- ano: ano do orçamento
- mes: mês do orçamento (01-12)
- grupo: código do grupo orçamentário
- descricao: descrição da categoria/grupo
- periodo: tipo de período (Mensal, Anual, etc)
- orcado: valor orçado (R$)
- realizado: valor realizado (R$)
- saldo: diferença entre orçado e realizado (R$)

IMPORTANTE: Orçamento NÃO tem contratos, sacas, clientes ou vendas. É uma previsão financeira (budget).
Para calcular totais, some os campos orcado/realizado/saldo de todos os registros.""",

            "IA_OrcamentoPar": """
COLUNAS DISPONÍVEIS EM ORÇAMENTO:
- ano: ano do orçamento
- mes: mês do orçamento (01-12)
- grupo: código do grupo orçamentário
- descricao: descrição da categoria/grupo
- periodo: tipo de período (Mensal, Anual, etc)
- orcado: valor orçado (R$)
- realizado: valor realizado (R$)
- saldo: diferença entre orçado e realizado (R$)

IMPORTANTE: Orçamento NÃO tem contratos, sacas, clientes ou vendas. É uma previsão financeira (budget).
Para calcular totais, some os campos orcado/realizado/saldo de todos os registros.""",

            "IA_Vendas": """
⚠️ ESTA TOOL É APENAS PARA CONSULTAR VENDAS EXISTENTES! ⚠️
Para CRIAR novos contratos, use a tool: criar_contrato_venda_exportacao

COLUNAS DISPONÍVEIS EM VENDAS (34 campos):

IDENTIFICAÇÃO E CONTROLE:
- filial: código da filial (ex: 61)
- contrato: número do contrato de venda (ex: "021/25")
- idProtheus: ID interno do sistema Protheus (ex: "000131")
- cliente: nome do cliente comprador
- emissao: data de emissão do contrato formato YYYYMMDD (ex: 20250710)

QUANTIDADES E VOLUMES:
- sacas: quantidade total de sacas do contrato
- sacasEntregues: sacas já entregues ao cliente
- sacasSaldo: saldo de sacas ainda não entregues (sacas - sacasEntregues)
- peso: peso total em kg

VALORES FINANCEIROS:
- valorUnitario: preço por saca em R$/saca (ex: 280.5)
- valorTotal: valor total do contrato em USD. Esta coluna SEMPRE vem em dólar na usp_IA_Vendas.
  Se o usuário pedir em R$ ou comparar com valores em BRL, converta explicitamente com cotação antes de somar/comparar.
- valorFixado: preço fixado por saca em R$/saca (ex: 315.5)
- diferencial: diferencial de preço em relação ao mercado (pode ser negativo)

FIXAÇÃO DE PREÇO:
- precoFix: status de fixação do preço (A=Automático, P=Pré-fixado)
- fixador: quem fixou o preço (ex: "Importador", "Exportador")
- mesFixacao: mês da fixação formato YYYYMM (ex: 202509)

QUALIDADE DO CAFÉ:
- certificado: certificação do café (ex: "RF", "4C", "FT", "GCP")
- descricaoQualidade: descrição completa da qualidade (ex: "BRAZIL NATURA ARABICA, GRINDERS 13 UP")
- linha: linha/tipo do café (ex: "GRD", "LN2", "LN3")
- peneiraMTGB: peneira MTGB em % (ex: 100 = 100%)
- peneiraGrauda: peneira Graúda em % (ex: 100 = 100%)
- peneiraGrinder: peneira Grinder em % (ex: 100 = 100%)

LOGÍSTICA E EMBARQUE:
- pais: país de destino (ex: "BELGICA", "ALEMANHA")
- mesEmbarque: mês de embarque formato YYYY/MM (ex: "2025/08")
- saidaNavio: data de saída do navio (pode estar vazio se ainda não embarcou)
- numeroBL: número do Bill of Lading/conhecimento de embarque
- previsaoRecebimento: data prevista de recebimento formato YYYYMMDD (ex: 20250901)

CONTROLE DE QUALIDADE:
- envioAmostra: data de envio da amostra ao cliente
- aprovAmostra: data de aprovação da amostra pelo cliente

FINANCEIRO E VENDAS:
- baixaReceber: data de baixa no contas a receber formato YYYYMMDD (ex: 20250829)
- grupoVenda: grupo/categoria de venda (ex: "CEU")
- vendedor: nome do vendedor responsável

REFERÊNCIAS:
- refCorretor: referência do corretor (se houver)
- refCliente: referência/código do cliente (ex: "P09150")

IMPORTANTE - PENEIRAS:
Quando perguntarem sobre "peneiras", use APENAS os campos estruturados:
- peneiraMTGB, peneiraGrauda, peneiraGrinder (valores numéricos em %)
NÃO confunda com menções de "screen" nas descrições de qualidade!
Exemplo ERRADO: extrair "13", "17/18" de "GRINDERS 13 UP" ou "SCREEN 17/18"
Exemplo CORRETO: usar valores dos campos peneiraMTGB/peneiraGrauda/peneiraGrinder

FORMATOS DE DATA:
- emissao, previsaoRecebimento, baixaReceber: YYYYMMDD (ex: 20250710)
- mesFixacao: YYYYMM (ex: 202509)
- mesEmbarque: YYYY/MM (ex: 2025/08)

Você pode responder sobre QUALQUER um desses 34 campos.""",

            "IA_Compras": """
COLUNAS DISPONÍVEIS EM COMPRAS:
Verifique os campos retornados nos registros acima.
Campos comuns: tipo, solicitacao, numero, peso, fornecedor, sacas, valor, emissao, linha, diferencial, etc.
REGRA OBRIGATÓRIA: em compras, "qualidade" significa o conteúdo do campo linha retornado pela procedure. O campo linha NÃO é a posição ordinal do registro. Nunca responda "linha 1", "linha 01" ou equivalente por haver apenas um resultado; leia exclusivamente registro["linha"].
Analise cada campo e responda com base nos dados reais.""",

            "IA_ComprasPar": """
COLUNAS DISPONÍVEIS EM COMPRAS:
Verifique os campos retornados nos registros acima.
Campos comuns: tipo, solicitacao, numero, peso, fornecedor, sacas, valor, emissao, linha, diferencial, etc.
REGRA OBRIGATÓRIA: em compras, "qualidade" significa o conteúdo do campo linha retornado pela procedure. O campo linha NÃO é a posição ordinal do registro. Nunca responda "linha 1", "linha 01" ou equivalente por haver apenas um resultado; leia exclusivamente registro["linha"].
Analise cada campo e responda com base nos dados reais.""",

            "IA_ContasPagas": """
COLUNAS DISPONÍVEIS EM CONTAS PAGAS:
Verifique os campos retornados nos registros acima.
Campos comuns: fornecedor, emissao, vencimento, valor, banco, etc.""",

            "IA_ContasAPagar": """
COLUNAS DISPONÍVEIS EM CONTAS A PAGAR:
Verifique os campos retornados nos registros acima.
Campos comuns: fornecedor, vencimento, valor, saldo, etc.""",

            "IA_ContasAReceber": """
COLUNAS DISPONÍVEIS EM CONTAS A RECEBER:
Verifique os campos retornados nos registros acima.
Campos comuns: cliente, vencimentoReal, valor, saldo, etc.""",

            "IA_Estoque": """
COLUNAS DISPONÍVEIS EM ESTOQUE (Total: 18 campos):

IDENTIFICAÇÃO E LOCALIZAÇÃO:
- filial: localização do estoque (ex: "OURO FINO")
- armazem: nome do armazém (ex: "ARMAZEM OURO FINO")
- pais: país de origem do café (ex: "BRASIL")
- lote: código do lote (ex: "TR-06043100")
- loteFonecedor: código do fornecedor (pode ser vazio)

CLASSIFICAÇÃO DO CAFÉ:
- linha: tipo de café (ex: "PVA", "GRD", "LN1", "LN2", "LN3", "CD", "FUNDI")
- certificado: código de certificação exatamente como vem no banco (ex: "RF", "4C", "GC", "GT", "CP")

MÉTRICAS DE QUALIDADE (percentuais %):
- impureza: percentual de impureza
- quebra: percentual de grãos quebrados
- pva: percentual PVA (Peneira Acima)
- grinder: percentual tipo grinder
- peneiraGrauda: percentual retido em peneira graúda
- peneiraMTGB: percentual retido em peneira MTGB
- fundo: percentual de fundo/resíduos

QUANTIDADES:
- peso: peso em quilogramas (float)
- sacas: total de sacas (Decimal - campo principal)
- sacasConsumo: sacas para consumo interno/mercado interno (Decimal)
- sacasExportacao: sacas para exportação (Decimal)

IMPORTANTE - REGRAS:
1. sacas = sacasConsumo + sacasExportacao (sempre)
2. O campo peso é real e independente de sacas. Não faça conversões no modelo. Se não houver peso real, o código usa o fator padrão de 60 kg/saca e o informa explicitamente.
3. Para "total de sacas", use campo "sacas"
4. Para "sacas para consumo", use "sacasConsumo"
5. Para "sacas para exportação", use "sacasExportacao"
6. Estoque NÃO tem contratos ou clientes (é snapshot físico)

VALORES COMUNS:
- Linhas mais comuns: PVA, GRD, LN1, LN2, LN3
- Certificados mais comuns: RF, 4C, GC
- Ao responder agrupamentos por certificado, use o código exato do certificado; não acrescente descrições entre parênteses sem o usuário pedir.
- Sacas: valores típicos entre 1,96 a 975,58 sacas por lote
- Peso: valores típicos entre 115 kg a 57.559 kg por lote""",

            "IA_SaldoBancario": """
COLUNAS DISPONÍVEIS EM SALDO BANCÁRIO:
Verifique os campos retornados nos registros acima.
Campos comuns: banco, agencia, conta, saldo, moeda, etc.""",

            "IA_Cotacao": """
COLUNAS DISPONÍVEIS EM COTAÇÃO:
Verifique os campos retornados nos registros acima.
Campos comuns: ativo, codigo, cotacao, variacao, situacao, etc.

⚠️ IMPORTANTE - COTAÇÕES:
- SEMPRE liste TODAS as cotações retornadas, sem omitir nenhuma
- Inclua TODOS os ativos: Café (todas as datas futuras), Dólar (todos os futuros), Switch, Euro, etc.
- NÃO mostre apenas "os principais" - mostre TODOS
- O usuário quer ver a lista completa para tomar decisões de negócio""",

            "IA_DespesaVenda": """
COLUNAS DISPONÍVEIS EM DESPESA DE VENDA:
Verifique os campos retornados nos registros acima.
Campos comuns: contrato, despesa, valor, fornecedor, etc."""
        }

        # Pega instrução específica ou genérica
        specific_instructions = FUNCTION_INSTRUCTIONS.get(function_name,
            "Analise TODOS os campos disponíveis nos registros acima e responda com base nos dados reais.")

        # SUMÁRIO ESPECIAL: Se ambos os filtros foram aplicados (não embarcados + sem BL)
        sumario_nao_embarcados_sem_bl = ""
        if filtros_aplicados and any("não embarcados" in f for f in filtros_aplicados) and any("sem BL" in f for f in filtros_aplicados):
            total_contratos = len(results)
            sumario_nao_embarcados_sem_bl = f"""

⚠️ RESPOSTA DIRETA: {total_contratos} contratos NÃO foram embarcados e não têm BL.

⚠️ IMPORTANTE: Use EXATAMENTE este número ({total_contratos} contratos) para responder ao usuário!
Não conte manualmente - este é o número correto após aplicar os filtros.

"""
            logger.info(f"[SUMÁRIO ESPECIAL] Calculado: {total_contratos} contratos não embarcados sem BL")

        # Instrução especial para listar todos os registros quando <= 50
        # Aplica para TODAS as funções (vendas, compras, cotações, etc.)
        listar_todos_instrucao = ""
        if len(results) <= 50 and self.user_query_original:
            palavras_lista_completa = ["todas", "todos", "liste", "listar", "informe", "mostre", "traga", "quais"]
            quer_lista_completa = any(palavra in self.user_query_original.lower() for palavra in palavras_lista_completa)

            if quer_lista_completa:
                listar_todos_instrucao = f"""

⚠️⚠️⚠️ INSTRUÇÃO OBRIGATÓRIA - O USUÁRIO PEDIU LISTA COMPLETA ⚠️⚠️⚠️

O usuário quer ver TODOS os registros, não apenas alguns exemplos.

✅ VOCÊ **DEVE** LISTAR **TODOS** OS {len(results)} REGISTROS ACIMA!
❌ **NÃO** mostre apenas alguns itens ou diga "existem outros"!
❌ **NÃO** agrupe nem resuma — liste cada registro individualmente!
❌ **NÃO** omita nenhum registro mesmo que o saldo/valor seja pequeno!

**IMPORTANTE**: Liste TODOS os {len(results)} registros, numerados de 1 a {len(results)}!"""
            else:
                listar_todos_instrucao = f"""

Esta consulta retornou {len(results)} registros.
Você pode resumir com totais e mostrar alguns exemplos, a menos que o usuário peça explicitamente para listar todos."""

        return f"""Resultados da consulta {function_name}:{sumario_nao_embarcados_sem_bl}

Total de registros retornados pelo SQL: {original_count}
Registros nesta resposta: {len(results)}

Dados:
{formatted}{warning}

{specific_instructions}{listar_todos_instrucao}

Analise TODOS os {len(results)} registros acima e responda com base nos campos disponíveis."""

    def _validate_and_execute(
        self,
        function_name: str,
        filters: Optional[Dict[str, Any]] = None,
        client_filter: Optional[str] = None,
        pagina: int = 1
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
            execution_id = uuid.uuid4().hex[:12]
            started_at = datetime.now(timezone.utc)
            started_clock = time.perf_counter()
            logger.info(
                "[SQL SNAPSHOT][%s] início=%s fonte=%s parâmetros=%s client_filter=%s",
                execution_id,
                started_at.isoformat(),
                function_name,
                filters or {},
                client_filter,
            )
            results = sql_client.execute_function(function_name, filters)
            if function_name == "IA_Estoque":
                self._stock_execution_context = {
                    "execution_id": execution_id,
                    "source": function_name,
                    "params": filters or {},
                }
                snapshot = build_stock_snapshot(results, group_by="linha")
                logger.info(
                    "[ESTOQUE SNAPSHOT][%s] fim=%s duração_ms=%.2f fonte=%s "
                    "parâmetros=%s linhas=%s linhas_únicas=%s duplicatas_exatas=%s "
                    "repetições_chave_lote=%s "
                    "fingerprint=%s totais={sacas:%s,consumo:%s,exportação:%s,peso:%s,lotes:%s}",
                    execution_id,
                    datetime.now(timezone.utc).isoformat(),
                    (time.perf_counter() - started_clock) * 1000,
                    function_name,
                    filters or {},
                    snapshot["linhas_recebidas"],
                    snapshot["linhas_unicas"],
                    snapshot["duplicatas_exatas"],
                    snapshot["repeticoes_chave_lote"],
                    snapshot_fingerprint(results),
                    snapshot["total_sacas"],
                    snapshot["sacas_consumo"],
                    snapshot["sacas_exportacao"],
                    snapshot["peso_kg"],
                    snapshot["total_lotes"],
                )
            self._salvar_resultado_scheduler(results)
            return self._format_results(results, function_name, client_filter, pagina=pagina)
        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar {function_name}: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    @staticmethod
    def _parse_mes_fixacao_vendas(texto_original: str, exigir_contexto: bool = True) -> Optional[Dict[str, str]]:
        """Converte índices/meses de fixação para o formato YYYY/MM da procedure."""
        texto = unicodedata.normalize("NFKD", str(texto_original or "").lower())
        texto = "".join(char for char in texto if not unicodedata.combining(char))

        meses_indices = {"h": "03", "k": "05", "n": "07", "u": "09", "z": "12"}
        meses_nomes = {
            "marco": "03", "mar": "03",
            "maio": "05", "mai": "05",
            "julho": "07", "jul": "07",
            "setembro": "09", "set": "09",
            "dezembro": "12", "dez": "12",
        }

        def ano_completo(valor: str) -> int:
            ano = int(valor)
            return ano if len(valor) == 4 else 2000 + ano

        encontrados = []

        # Índices de bolsa são inequívocos e independem de palavras de contexto.
        for match in re.finditer(r"\b([hknuz])\s*[-/]?\s*(\d{2}|\d{4})\b", texto):
            encontrados.append((match.start(), ano_completo(match.group(2)), meses_indices[match.group(1)]))

        tem_contexto_fixacao = any(
            termo in texto
            for termo in ("fixacao", "fixado", "fixados", "fixar", "bolsa", "mes fix")
        )
        if tem_contexto_fixacao or not exigir_contexto:
            nomes_regex = "|".join(sorted(meses_nomes, key=len, reverse=True))
            for match in re.finditer(
                rf"\b({nomes_regex})\b\s*(?:/|-|de\s+)?\s*(\d{{2}}|\d{{4}})\b",
                texto,
            ):
                encontrados.append((match.start(), ano_completo(match.group(2)), meses_nomes[match.group(1)]))

            for match in re.finditer(r"\b(03|05|07|09|12)\s*/\s*(\d{2}|\d{4})\b", texto):
                encontrados.append((match.start(), ano_completo(match.group(2)), match.group(1)))

        if not encontrados:
            return None

        periodos = sorted({(ano, mes) for _, ano, mes in encontrados})
        ano_inicio, mes_inicio = periodos[0]
        ano_fim, mes_fim = periodos[-1]
        return {
            "mes_inicio": f"{ano_inicio:04d}/{mes_inicio}",
            "mes_fim": f"{ano_fim:04d}/{mes_fim}",
        }

    def _parse_periodo_vendas(self, periodo: str) -> Optional[Dict[str, str]]:
        """Converte periodos de vendas para meses no formato YYYY/MM."""
        from dateutil.relativedelta import relativedelta

        texto = unicodedata.normalize("NFKD", str(periodo).lower().strip()).encode("ascii", "ignore").decode("ascii")
        agora = date_parser.get_current_date()
        meses_nomeados = {
            "janeiro": "01", "jan": "01",
            "fevereiro": "02", "fev": "02",
            "marco": "03", "mar": "03",
            "abril": "04", "abr": "04",
            "maio": "05", "mai": "05",
            "junho": "06", "jun": "06",
            "julho": "07", "jul": "07",
            "agosto": "08", "ago": "08",
            "setembro": "09", "set": "09",
            "outubro": "10", "out": "10",
            "novembro": "11", "nov": "11",
            "dezembro": "12", "dez": "12",
        }
        numeros = {
            "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
            "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
            "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
        }

        nomes_meses_regex = "|".join(sorted(meses_nomeados, key=len, reverse=True))
        match_intervalo_meses = re.search(
            rf"\b({nomes_meses_regex})\b\s+(?:a|ate|at[eé]|para|-)\s+\b({nomes_meses_regex})\b(?:\s+(?:de|do|em))?\s+(\d{{4}})",
            texto,
        )
        if match_intervalo_meses:
            mes_inicio = meses_nomeados[match_intervalo_meses.group(1)]
            mes_fim = meses_nomeados[match_intervalo_meses.group(2)]
            ano = match_intervalo_meses.group(3)
            return {
                "mes_inicio": f"{ano}/{mes_inicio}",
                "mes_fim": f"{ano}/{mes_fim}",
            }

        if any(expressao in texto for expressao in ("este ano", "esse ano", "ano atual")):
            return {
                "mes_inicio": f"{agora.year}/01",
                "mes_fim": f"{agora.year}/12",
            }

        match_ultimos_meses = re.search(r"ultimos?\s+(\d+|[a-z]+)\s+mes(?:es)?", texto)
        if match_ultimos_meses:
            quantidade_texto = match_ultimos_meses.group(1)
            quantidade = int(quantidade_texto) if quantidade_texto.isdigit() else numeros.get(quantidade_texto)
            if quantidade and quantidade > 0:
                inicio = agora.replace(day=1) - relativedelta(months=quantidade)
                return {
                    "mes_inicio": inicio.strftime("%Y/%m"),
                    "mes_fim": agora.strftime("%Y/%m"),
                }

        parsed = date_parser.parse_natural_date(periodo)
        if not parsed:
            return None

        if parsed.get("ano_completo") and parsed.get("ano"):
            ano = parsed["ano"]
            return {"mes_inicio": f"{ano}/01", "mes_fim": f"{ano}/12"}

        if parsed.get("meses") and parsed.get("ano"):
            return {
                "mes_inicio": f"{parsed['ano']}/{parsed['meses'][0]}",
                "mes_fim": f"{parsed['ano']}/{parsed['meses'][-1]}",
            }

        if parsed.get("mes_embarque"):
            return {
                "mes_inicio": parsed["mes_embarque"],
                "mes_fim": parsed["mes_embarque"],
            }

        if parsed.get("data_inicio"):
            mes_inicio = f"{parsed['data_inicio'][:4]}/{parsed['data_inicio'][4:6]}"
            data_fim = parsed.get("data_fim", parsed["data_inicio"])
            mes_fim = f"{data_fim[:4]}/{data_fim[4:6]}"
            return {"mes_inicio": mes_inicio, "mes_fim": mes_fim}

        return None

    def _parse_emissao_vendas(self, periodo: str) -> Optional[Dict[str, str]]:
        """Converte o periodo de inclusao da venda para EmisIni/EmisFim."""
        from datetime import timedelta

        texto = self._remove_accents(str(periodo or "").lower())
        agora = date_parser.get_current_date()

        intervalo = re.search(
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s*'
            r'(?:a|ate|entre|-)\s*'
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
            texto,
        )
        if intervalo:
            dia_ini, mes_ini, ano_ini, dia_fim, mes_fim, ano_fim = intervalo.groups()
            return {
                "data_inicio": f"{ano_ini}{int(mes_ini):02d}{int(dia_ini):02d}",
                "data_fim": f"{ano_fim}{int(mes_fim):02d}{int(dia_fim):02d}",
            }

        if any(
            expressao in texto
            for expressao in ("esta semana", "essa semana", "desta semana", "nessa semana")
        ):
            dias_desde_domingo = (agora.weekday() + 1) % 7
            domingo = agora - timedelta(days=dias_desde_domingo)
            sabado = domingo + timedelta(days=6)
            return {
                "data_inicio": domingo.strftime("%Y%m%d"),
                "data_fim": sabado.strftime("%Y%m%d"),
            }

        parsed = date_parser.parse_natural_date(periodo)
        if not parsed or not parsed.get("data_inicio"):
            return None
        return {
            "data_inicio": parsed["data_inicio"],
            "data_fim": parsed.get("data_fim", parsed["data_inicio"]),
        }

    def _pesquisa_vendas(
        self,
        periodo: Optional[str] = None,
        data_emissao: Optional[str] = None,
        cliente: Optional[str] = None,
        contrato: Optional[str] = None,
        mes_fixacao: Optional[str] = None,
        verificar_fixacao: bool = False,
        limite: Optional[int] = None,
        pagina: int = 1,
    ) -> str:
        """
        Consulta dados de vendas e embarques da empresa.

        Args:
            periodo: Período de embarque desejado (ex: "dezembro 2025")
            data_emissao: Período em que os contratos foram inseridos, digitados ou lançados
            cliente: Nome do cliente
            contrato: Número do contrato de venda (ex: "032/26A")
            mes_fixacao: Índice ou mês de fixação (ex: "U26", "setembro/26")
            verificar_fixacao: Força a resposta determinística baseada em valorFixado
            limite: Quantidade máxima de registros em consultas somente por cliente
            pagina: Página de contratos a retornar (default=1, cada página tem 100 contratos)
                   Se a resposta indicar "HÁ MAIS CONTRATOS", chame com pagina=2, pagina=3, etc.

        Returns:
            Dados de vendas formatados
        """
        logger.info(
            f"[DEBUG] _pesquisa_vendas chamado com periodo={periodo}, data_emissao={data_emissao}, cliente={cliente}, "
            f"contrato={contrato}, mes_fixacao={mes_fixacao}, verificar_fixacao={verificar_fixacao}, "
            f"limite={limite}, pagina={pagina}"
        )
        self._series_expected_months = []
        self._series_date_fields = ("mesEmbarque", "mesembarque")

        # DETECÇÃO DE CONTEXTO DE CONTRATO: Detecta se é pergunta de seguimento sobre contrato anterior
        contrato_na_query = contrato.upper().strip() if contrato else None
        if self.user_query_original:
            # Tenta extrair contrato da pergunta atual
            match_contrato = re.search(r'(?<![\d/])(\d{2,4}/\d{2}(?![\d/])[A-Z]?)', self.user_query_original, re.IGNORECASE)
            if match_contrato:
                contrato_na_query = match_contrato.group(1).upper()
                logger.info(f"[CONTEXTO CONTRATO] Contrato mencionado explicitamente: {contrato_na_query}")
                self.ultimo_contrato_consultado = contrato_na_query

                # Salva no Redis para persistir entre chamadas
                if self.session_id:
                    try:
                        self._run_coroutine(self._salvar_contrato_redis(contrato_na_query))
                    except Exception as e:
                        logger.warning(f"[CONTEXTO REDIS] Erro ao salvar contrato: {e}")
            else:
                # NÃO mencionou contrato, mas pode ser pergunta de seguimento
                # Palavras que indicam pergunta de seguimento sobre contrato
                palavras_seguimento = [
                    r'\btotal\b', r'\bquantidade\b', r'\bsacas?\b', r'\bvendedor\b',
                    r'\bcliente\b', r'\bvalor\b', r'\bpreço\b', r'\bpreco\b',
                    r'\bdiferencial\b', r'\bembarque\b', r'\bqual(is)?\b',
                    r'\bmostre\b', r'\binforme\b', r'\bme\s+d[eê]\b'
                ]

                query_lower = self.user_query_original.lower()
                eh_pergunta_seguimento = any(re.search(padrao, query_lower) for padrao in palavras_seguimento)

                if eh_pergunta_seguimento and self.ultimo_contrato_consultado:
                    contrato_na_query = self.ultimo_contrato_consultado
                    logger.info(f"[CONTEXTO CONTRATO] Pergunta de seguimento detectada! Usando contrato anterior: {self.ultimo_contrato_consultado}")
                    # Injeta contrato na query para que o filtro funcione
                    self.user_query_original = f"{self.user_query_original} (contrato {self.ultimo_contrato_consultado})"
                    logger.info(f"[CONTEXTO CONTRATO] Query modificada: {self.user_query_original}")
                elif eh_pergunta_seguimento and not self.ultimo_contrato_consultado:
                    logger.warning(f"[CONTEXTO CONTRATO] Pergunta de seguimento detectada mas SEM contrato anterior armazenado")

        # PROTEÇÃO: Detecta queries sobre "baixados EM [data]" e força periodo=None
        if periodo and self.user_query:
            query_lower = self.user_query.lower()
            # Padrões que indicam query sobre DATA DE BAIXA (não embarque)
            if re.search(r'baixad[oa]s?\s+(no\s+contas\s+a\s+receber\s+)?em\s+', query_lower):
                logger.warning(f"[PROTEÇÃO] Query sobre 'baixados EM [data]' detectada - IGNORANDO periodo={periodo}")
                logger.warning(f"[PROTEÇÃO] Query original: {self.user_query}")
                logger.warning(f"[PROTEÇÃO] Usando periodo=None para buscar TODOS os contratos e filtrar por campos específicos")
                periodo = None  # Força periodo=None

        # Em uma série mensal, a pergunta original é a fonte do intervalo.
        # Isso impede que uma chamada fragmentada do modelo (ex.: "julho 2026")
        # reduza "segundo semestre de 2026" a um único mês.
        series_period_override = None
        if self._is_monthly_series_request():
            series_source = self.user_query_original or self.user_query or ""
            parsed_series = self._parse_periodo_vendas(series_source)
            if (
                parsed_series
                and parsed_series.get("mes_inicio")
                and parsed_series.get("mes_fim")
                and parsed_series["mes_inicio"] != parsed_series["mes_fim"]
            ):
                series_period_override = parsed_series
                logger.info(
                    "[VENDAS SÉRIE] Intervalo completo da pergunta prevalece: %s a %s",
                    parsed_series["mes_inicio"],
                    parsed_series["mes_fim"],
                )

        # Extrai nome do cliente da pergunta original do usuário
        client_filter = cliente
        if not client_filter and self.user_query:
            client_filter = self._extract_client_name(self.user_query)
            if client_filter:
                logger.info(f"[FILTRO CLIENTE] Detectado '{client_filter}' na pergunta: {self.user_query}")

        procedure_name = "usp_IA_Vendas"
        procedure_params = {}

        pergunta_original = self._remove_accents(
            (self.user_query_original or self.user_query or "").lower()
        )
        contexto_emissao = bool(data_emissao) or bool(
            re.search(
                r'\b(?:inserid[oa]s?|digitad[oa]s?|lancad[oa]s?|cadastrad[oa]s?|emitid[oa]s?)\b',
                pergunta_original,
            )
            or re.search(
                r'\bvendid[oa]s?\b.*\b(?:hoje|ontem|semana|mes|ano|\d{1,2}[/-]\d{1,2})\b',
                pergunta_original,
            )
        )
        fonte_emissao = data_emissao or (
            self.user_query_original or self.user_query or periodo or ""
        )
        periodo_emissao = (
            self._parse_emissao_vendas(fonte_emissao) if contexto_emissao else None
        )
        if periodo_emissao:
            procedure_params["EmisIni"] = periodo_emissao["data_inicio"]
            procedure_params["EmisFim"] = periodo_emissao["data_fim"]
            logger.info(
                "[VENDAS] Periodo de emissao detectado: %s ate %s",
                periodo_emissao["data_inicio"],
                periodo_emissao["data_fim"],
            )

        fonte_mes_fixacao = mes_fixacao or self.user_query_original or self.user_query or ""
        periodo_fixacao = self._parse_mes_fixacao_vendas(
            fonte_mes_fixacao,
            exigir_contexto=mes_fixacao is None,
        )

        if periodo_fixacao:
            procedure_params["MesFixIni"] = periodo_fixacao["mes_inicio"]
            procedure_params["MesFixFim"] = periodo_fixacao["mes_fim"]
            logger.info(
                "[VENDAS] Mês de fixação detectado: %s até %s",
                periodo_fixacao["mes_inicio"],
                periodo_fixacao["mes_fim"],
            )
        elif (periodo or series_period_override) and not periodo_emissao:
            parsed = series_period_override or self._parse_periodo_vendas(periodo)
            logger.info(f"[VENDAS] Período convertido para meses: {parsed}")
            if parsed:
                procedure_params["MesIni"] = parsed["mes_inicio"]
                procedure_params["MesFim"] = parsed["mes_fim"]
        else:
            logger.info("[VENDAS] Consulta sem filtro de mês de embarque")

        if client_filter:
            procedure_params["Cliente"] = client_filter

        if contrato_na_query:
            procedure_params["Contrato"] = contrato_na_query

        if procedure_params.get("MesFixIni") and procedure_params.get("MesFixFim"):
            self._series_expected_months = month_keys_between(
                procedure_params["MesFixIni"], procedure_params["MesFixFim"]
            )
            self._series_date_fields = ("mesFixacao", "mesfixacao")
        elif procedure_params.get("MesIni") and procedure_params.get("MesFim"):
            self._series_expected_months = month_keys_between(
                procedure_params["MesIni"], procedure_params["MesFim"]
            )
        elif procedure_params.get("EmisIni") and procedure_params.get("EmisFim"):
            self._series_expected_months = month_keys_between(
                procedure_params["EmisIni"], procedure_params["EmisFim"]
            )
            self._series_date_fields = ("emissao", "dataEmissao", "dataemissao")

        has_permission, error_msg = sql_validator.validate_permission(self.user, procedure_name)
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: {procedure_name}")
            return error_msg

        logger.info(f"[VENDAS] Executando {procedure_name} com parâmetros: {procedure_params}")
        self._series_query_context = {
            "procedure": procedure_name,
            "params": dict(procedure_params),
        }

        try:
            results = sql_client.execute_procedure(procedure_name, procedure_params or None)
            self._salvar_resultado_scheduler(results)

            query_fixacao = self._remove_accents((self.user_query_original or "").lower())
            pergunta_status_fixacao = bool(contrato_na_query) and (
                verificar_fixacao
                or (
                    "fixad" in query_fixacao
                    and any(
                        term in query_fixacao
                        for term in ("ja foi", "foi fixado", "esta fixado", "esta fixada")
                    )
                )
            )
            if pergunta_status_fixacao:
                if not results:
                    return f"Não encontrei o contrato {contrato_na_query}."

                valores_fixados = []
                for row in results:
                    valor = row.get("valorFixado")
                    try:
                        valores_fixados.append(float(valor or 0))
                    except (TypeError, ValueError):
                        logger.warning(
                            "[FIXAÇÃO] valorFixado inválido no contrato %s: %r",
                            contrato_na_query,
                            valor,
                        )

                valor_positivo = next((valor for valor in valores_fixados if valor > 0), None)
                if valor_positivo is not None:
                    valor_formatado = f"{valor_positivo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    return (
                        f"Sim. O contrato {contrato_na_query} já foi fixado, "
                        f"pois o valorFixado é {valor_formatado}."
                    )

                return (
                    f"Não. O contrato {contrato_na_query} ainda não foi fixado, "
                    "pois o valorFixado está zerado."
                )

            filial_solicitada = detect_sales_branch_from_query(
                self.user_query_original or self.user_query or ""
            )
            if (
                periodo_emissao
                and not filial_solicitada
                and not self._is_monthly_series_request()
            ):
                totais = aggregate_sales_totals(results)
                por_filial = aggregate_sales_by_branch(results)
                linhas = [
                    f"- {item['empresa']} (filial {item['filial']}): "
                    f"{item['contratos']} contrato(s) | "
                    f"{format_pt_br(item['sacas'])} sacas | "
                    f"USD {format_pt_br(item['valor_usd'])}"
                    for item in por_filial
                ]
                if not linhas:
                    return "Não foram encontrados contratos de venda inseridos no período informado."
                return (
                    "RESUMO DE VENDAS INSERIDAS POR FILIAL\n\n"
                    f"Período de emissão: {periodo_emissao['data_inicio']} a "
                    f"{periodo_emissao['data_fim']}\n"
                    f"Total: {totais['contratos']} contrato(s) | "
                    f"{format_pt_br(totais['sacas'])} sacas | "
                    f"USD {format_pt_br(totais['valor_usd'])}\n\n"
                    + "\n".join(linhas)
                )

            if client_filter and not periodo:
                if limite is None:
                    results = results[:10]
                elif limite > 0:
                    results = results[:limite]

            return self._format_results(results, "IA_Vendas", client_filter, pagina=pagina)
        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar {procedure_name}: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return "Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _parse_periodo_compras(self, periodo: str) -> Optional[Dict[str, str]]:
        """Converte periodos de compras para datas no formato YYYYMMDD."""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta

        texto = unicodedata.normalize("NFKD", str(periodo).lower().strip()).encode("ascii", "ignore").decode("ascii")
        agora = date_parser.get_current_date()
        ultimo_dia_semana = parse_last_weekday_date(periodo, agora)
        if ultimo_dia_semana:
            return {
                "data_inicio": ultimo_dia_semana,
                "data_fim": ultimo_dia_semana,
            }
        numeros = {
            "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
            "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
            "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
        }

        if any(expressao in texto for expressao in ("este ano", "esse ano", "ano atual")):
            return {
                "data_inicio": f"{agora.year}0101",
                "data_fim": f"{agora.year}1231",
            }

        match_ultimos_meses = re.search(r"ultimos?\s+(\d+|[a-z]+)\s+mes(?:es)?", texto)
        if match_ultimos_meses:
            quantidade_texto = match_ultimos_meses.group(1)
            quantidade = int(quantidade_texto) if quantidade_texto.isdigit() else numeros.get(quantidade_texto)
            if quantidade and quantidade > 0:
                inicio = agora.replace(day=1) - relativedelta(months=quantidade)
                fim = agora.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
                return {
                    "data_inicio": inicio.strftime("%Y%m%d"),
                    "data_fim": fim.strftime("%Y%m%d"),
                }

        parsed = date_parser.parse_natural_date(periodo)
        if not parsed:
            return None

        if parsed.get("data_inicio"):
            return {
                "data_inicio": parsed["data_inicio"],
                "data_fim": parsed.get("data_fim", parsed["data_inicio"]),
            }

        if parsed.get("mes_embarque"):
            from calendar import monthrange
            ano, mes = map(int, parsed["mes_embarque"].split("/"))
            return {
                "data_inicio": f"{ano:04d}{mes:02d}01",
                "data_fim": f"{ano:04d}{mes:02d}{monthrange(ano, mes)[1]:02d}",
            }

        return None

    def _pesquisa_compras(self, data_inicio: Optional[str] = None, data_fim: Optional[str] = None, fornecedor: Optional[str] = None, limite: Optional[int] = None, pagina: int = 1) -> str:
        """
        Consulta dados de compras e aquisições.

        Args:
            data_inicio: Data/período inicial (ex: "janeiro 2025", "2025", "05/12/2025")
            data_fim: Data/período final para range (ex: "outubro 2025", "dezembro 2025")
            fornecedor: Nome do fornecedor
            limite: Quantidade máxima de registros em consultas somente por fornecedor
            pagina: Página de contratos a retornar (default=1, cada página tem 50 contratos)

        Returns:
            Dados de compras formatados
        """
        procedure_name = "usp_IA_Compras"

        # Autoriza antes de interpretar filtros ou datas. Além de evitar
        # trabalho desnecessário, garante que nenhum passo da consulta seja
        # preparado para um usuário sem acesso ao módulo de Compras.
        has_permission, error_msg = sql_validator.validate_permission(self.user, procedure_name)
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: {procedure_name}")
            return error_msg

        procedure_params = {}
        self._series_expected_months = []
        self._series_date_fields = ("emissao", "dataEmissao", "dataemissao")

        # Se data_fim fornecido separadamente, parseia os dois e monta range
        if data_inicio and data_fim:
            parsed_inicio = self._parse_periodo_compras(data_inicio)
            parsed_fim = self._parse_periodo_compras(data_fim)
            logger.info(f"[COMPRAS] Range: data_inicio={parsed_inicio}, data_fim={parsed_fim}")

            if parsed_inicio and parsed_fim:
                procedure_params["DataIni"] = parsed_inicio["data_inicio"]
                procedure_params["DataFim"] = parsed_fim["data_fim"]

        elif data_inicio:
            parsed = self._parse_periodo_compras(data_inicio)
            logger.info(f"[COMPRAS] date_parser retornou: {parsed}")

            if parsed:
                procedure_params["DataIni"] = parsed["data_inicio"]
                procedure_params["DataFim"] = parsed["data_fim"]
        else:
            logger.info("[COMPRAS] Consulta sem filtro de data")

        if fornecedor:
            procedure_params["Fornec"] = fornecedor

        if procedure_params.get("DataIni") and procedure_params.get("DataFim"):
            self._series_expected_months = month_keys_between(
                procedure_params["DataIni"], procedure_params["DataFim"]
            )

        logger.info(f"[COMPRAS] Executando {procedure_name} com parâmetros: {procedure_params}")
        self._series_query_context = {
            "procedure": procedure_name,
            "params": dict(procedure_params),
        }

        try:
            results = sql_client.execute_procedure(procedure_name, procedure_params or None)
            self._salvar_resultado_scheduler(results)

            if fornecedor and not data_inicio and not data_fim:
                if limite is None:
                    results = results[:10]
                elif limite > 0:
                    results = results[:limite]

            return self._format_results(results, "IA_Compras", pagina=pagina)
        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar {procedure_name}: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return "Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _parse_periodo_contas_pagas(self, periodo: str) -> Optional[Dict[str, str]]:
        """Normaliza periodos financeiros especificos para a procedure de contas pagas."""
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta

        texto = unicodedata.normalize("NFKD", str(periodo).lower().strip()).encode("ascii", "ignore").decode("ascii")
        agora = date_parser.get_current_date()

        meses = {
            "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
            "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
            "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
        }
        numeros = {
            "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
            "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
            "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
        }

        def intervalo(inicio: datetime, fim: datetime) -> Dict[str, str]:
            return {
                "data_inicio": inicio.strftime("%Y%m%d"),
                "data_fim": fim.strftime("%Y%m%d"),
            }

        # Quinzenas devem ser resolvidas antes de mes/ano.
        if "quinzena" in texto:
            ano_match = re.search(r"(20\d{2})", texto)
            ano = int(ano_match.group(1)) if ano_match else agora.year
            mes = agora.month
            for nome, numero in meses.items():
                if nome in texto:
                    mes = numero
                    break

            primeira = "primeira" in texto or "1a" in texto or "1 " in texto
            segunda = "segunda" in texto or "2a" in texto or "2 " in texto
            if primeira or (not segunda and agora.day <= 15):
                return intervalo(datetime(ano, mes, 1), datetime(ano, mes, 15))

            primeiro_dia = datetime(ano, mes, 1)
            ultimo_dia = primeiro_dia + relativedelta(months=1) - timedelta(days=1)
            return intervalo(datetime(ano, mes, 16), ultimo_dia)

        # "Ultimos N meses" usa meses completos, incluindo o mes atual.
        match_meses = re.search(r"ultimos?\s+(\d+|[a-z]+)\s+mes(?:es)?", texto)
        if match_meses:
            quantidade_texto = match_meses.group(1)
            quantidade = int(quantidade_texto) if quantidade_texto.isdigit() else numeros.get(quantidade_texto)
            if quantidade and quantidade > 0:
                inicio_mes_atual = agora.replace(day=1)
                inicio = inicio_mes_atual - relativedelta(months=quantidade - 1)
                fim = inicio_mes_atual + relativedelta(months=1) - timedelta(days=1)
                return intervalo(inicio, fim)

        if any(expressao in texto for expressao in ("este trimestre", "esse trimestre", "trimestre atual")):
            primeiro_mes = ((agora.month - 1) // 3) * 3 + 1
            inicio = datetime(agora.year, primeiro_mes, 1)
            fim = inicio + relativedelta(months=3) - timedelta(days=1)
            return intervalo(inicio, fim)

        if "trimestre passado" in texto or "ultimo trimestre" in texto:
            primeiro_mes = ((agora.month - 1) // 3) * 3 + 1
            inicio = datetime(agora.year, primeiro_mes, 1) - relativedelta(months=3)
            fim = inicio + relativedelta(months=3) - timedelta(days=1)
            return intervalo(inicio, fim)

        if any(expressao in texto for expressao in ("este ano", "esse ano", "ano atual")):
            return intervalo(datetime(agora.year, 1, 1), datetime(agora.year, 12, 31))

        if "ano passado" in texto or "ultimo ano" in texto:
            ano = agora.year - 1
            return intervalo(datetime(ano, 1, 1), datetime(ano, 12, 31))

        # Regra financeira solicitada: uma referencia mensal com ano abrange o ano inteiro.
        ano_match = re.search(r"(20\d{2})", texto)
        tem_mes_nomeado = any(nome in texto for nome in meses)
        tem_mes_ano_numerico = bool(re.match(r"^\s*(0?[1-9]|1[0-2])/(20\d{2})\s*$", texto))
        if ano_match and (tem_mes_nomeado or tem_mes_ano_numerico):
            ano = int(ano_match.group(1))
            return intervalo(datetime(ano, 1, 1), datetime(ano, 12, 31))

        return date_parser.parse_natural_date(periodo)

    def _pesquisa_contas_pagas(self, data_inicio: Optional[str] = None, fornecedor: Optional[str] = None, limite: Optional[int] = None) -> str:
        """
        Consulta contas já pagas pela empresa.

        Args:
            data_inicio: Data inicial (ex: "este mês", "últimos 30 dias")
            fornecedor: Nome do fornecedor/beneficiário
            limite: Quantidade máxima de registros em consultas somente por fornecedor

        Returns:
            Dados de contas pagas formatados
        """
        logger.info(f"[CONTAS PAGAS] Consultando contas pagas - data_inicio: {data_inicio}, fornecedor: {fornecedor}, limite: {limite}")

        procedure_name = "usp_IA_ContasPagas"
        procedure_params = {}

        if data_inicio:
            parsed = self._parse_periodo_contas_pagas(data_inicio)
            logger.info(f"[CONTAS PAGAS] date_parser retornou: {parsed}")

            if parsed:
                # Extrai datas do parsed
                inicio = None
                fim = None

                # Prioridade 1: Se tem data_inicio e data_fim
                if "data_inicio" in parsed and "data_fim" in parsed:
                    inicio = parsed["data_inicio"]
                    fim = parsed["data_fim"]
                    logger.info(f"[CONTAS PAGAS] Período detectado ({inicio} até {fim})")
                # Prioridade 2: Se tem apenas data_inicio
                elif "data_inicio" in parsed:
                    inicio = parsed["data_inicio"]
                    fim = parsed.get("data_fim", inicio)
                    logger.info(f"[CONTAS PAGAS] Data única detectada: {inicio}")

                # Para contas pagas, "esta semana" considera domingo a sábado.
                texto_data = str(data_inicio).lower()
                if inicio and fim and any(expressao in texto_data for expressao in ("esta semana", "essa semana", "desta semana", "nessa semana")):
                    from datetime import datetime, timedelta
                    inicio = (datetime.strptime(inicio, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                    fim = (datetime.strptime(fim, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")

                if inicio and fim:
                    procedure_params["DataIni"] = inicio
                    procedure_params["DataFim"] = fim
        else:
            logger.info("[CONTAS PAGAS] Consulta sem filtro de data")

        if fornecedor:
            procedure_params["Fornec"] = fornecedor

        # Valida permissão
        has_permission, error_msg = sql_validator.validate_permission(self.user, procedure_name)
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: {procedure_name}")
            return error_msg

        logger.info(f"[CONTAS PAGAS] Executando {procedure_name} com parâmetros: {procedure_params}")

        # Executa stored procedure
        try:
            result_list = sql_client.execute_procedure(procedure_name, procedure_params or None)
            self._log_financial_field_anomalies(result_list or [], "CONTAS PAGAS")
            self._salvar_resultado_scheduler(result_list)

            if not result_list:
                return "Nenhuma conta paga encontrada para o período especificado."

            # Consultas somente por fornecedor retornam 10 registros por padrão.
            if fornecedor and not data_inicio:
                if limite is None:
                    result_list = result_list[:10]
                elif limite > 0:
                    result_list = result_list[:limite]

            log_query_processing(
                source_name=procedure_name,
                original_count=len(result_list),
                final_count=len(result_list),
                post_filters={"fornecedor": fornecedor, "limite": limite},
                calculated_totals={
                    "valor_total": sum(
                        (payable_decimal(row.get("valor") or row.get("valorStr")) for row in result_list),
                        Decimal("0"),
                    )
                },
                status_criterion="pagamentos efetuados",
                unit="títulos",
                currency="BRL",
            )

            # Se poucos registros (<= 50), retorna todos
            if len(result_list) <= 50:
                def convert_decimals(obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

                display_rows = [prepare_financial_record(row) for row in result_list]
                formatted = json.dumps(display_rows, ensure_ascii=False, indent=2, default=convert_decimals)

                return f"""Resultados da consulta usp_IA_ContasPagas:

Total de registros: {len(result_list)}

Dados completos:
{formatted}

CAMPOS DISPONÍVEIS:
- numero: Número do título/documento
- fornecedor: Valor original do banco; pode estar vazio
- fornecedor_exibicao: Nome para resposta; quando o original está vazio, é "Fornecedor não informado"
- valor: Valor principal pago
- valorStr: Valor em formato string
- moeda: Tipo de moeda (BRL/USD/EUR)
- juros: Valor de juros
- acrescimo: Acréscimos
- decrescimo: Descontos/decréscimos
- emissao: Data de emissão (YYYYMMDD)
- vencimento: Data de vencimento
- pagamento: Data efetiva do pagamento
- banco: Banco utilizado
- centroCusto: Centro de custo
- natureza: Natureza/tipo da despesa
- aprovador: Primeiro aprovador
- aprovador2: Segundo aprovador
- filial: Código da filial
- valor_zerado: indica registro com valor igual a zero
- classificacao_valor_zero: ajuste cambial/contábil quando há evidência no texto, ou registro sem valor

Analise TODOS os {len(result_list)} registros acima e responda com base nos campos disponíveis.
Nunca use natureza ou descrição como fornecedor. Identifique explicitamente os registros zerados."""

            # Se muitos registros (> 50), agrega por fornecedor. Zeros ficam
            # fora do ranking e são exibidos separadamente.
            from collections import defaultdict
            por_fornecedor = defaultdict(lambda: {
                "valor_total": 0,
                "quantidade": 0,
                "naturezas": set(),
                "bancos": set()
            })

            total_geral = 0
            ranking_rows, zero_rows = split_zero_value_records(result_list)

            for r in ranking_rows:
                fornecedor = supplier_display(r)
                valor = r.get("valor", 0)

                # Converte valor para float
                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        # Tenta conversao direta primeiro (campo 'valor' eh simples: "-2000")
                        valor = float(valor)
                    except:
                        try:
                            # Se falhar, tenta limpar formatacao (para campo 'valorStr': "R$  -2000.00")
                            valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                            valor = float(valor_limpo)
                        except:
                            valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_fornecedor[fornecedor]["valor_total"] += valor
                por_fornecedor[fornecedor]["quantidade"] += 1

                natureza = str(r.get("natureza") or "").strip()
                if natureza:
                    por_fornecedor[fornecedor]["naturezas"].add(natureza)

                banco = str(r.get("banco") or "").strip()
                if banco:
                    por_fornecedor[fornecedor]["bancos"].add(banco)

                total_geral += valor

            # Zeros não alteram o total, mas continuam visíveis e preservados.
            zero_notice = ""
            if zero_rows:
                zero_notice = (
                    f"\n\nREGISTROS COM VALOR ZERO (fora do ranking): {len(zero_rows)}\n"
                    + format_zero_value_records(zero_rows)
                )

            # Converte sets para listas para JSON
            # Ordena por VALOR ABSOLUTO (maiores pagamentos primeiro) e limita aos top 50
            fornecedores_list = []
            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor_total"]), reverse=True)

            # Limita aos top 50 fornecedores para evitar respostas muito grandes
            for fornecedor, dados in fornecedores_ordenados[:50]:
                fornecedores_list.append({
                    "fornecedor": fornecedor,
                    "valor_total": round(dados["valor_total"], 2),
                    "quantidade_pagamentos": dados["quantidade"],
                    "naturezas": sorted(list(dados["naturezas"])),
                    "bancos": sorted(list(dados["bancos"]))
                })

            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            formatted = json.dumps(fornecedores_list, ensure_ascii=False, indent=2, default=convert_decimals)

            return f"""Resultados da consulta usp_IA_ContasPagas (AGREGADOS POR FORNECEDOR):

Total de registros SQL: {len(result_list)}
Total de fornecedores únicos: {len(por_fornecedor)}
Valor total pago: R$ {total_geral:,.2f}

Top {len(fornecedores_list)} maiores fornecedores (por valor):
{formatted}{zero_notice}

CAMPOS DISPONÍVEIS POR FORNECEDOR:
- fornecedor: Nome do fornecedor/beneficiário
- valor_total: Total pago para este fornecedor (R$)
- quantidade_pagamentos: Número de pagamentos realizados
- naturezas: Lista de naturezas/tipos de despesa
- bancos: Lista de bancos utilizados nos pagamentos

IMPORTANTE:
1. Estes são pagamentos JÁ EFETUADOS (contas pagas)
2. O valor_total já está calculado e somado por fornecedor
3. Mostrando apenas os {len(fornecedores_list)} maiores fornecedores de um total de {len(por_fornecedor)}
4. O valor_total mostrado representa a soma de TODOS os fornecedores, não apenas os {len(fornecedores_list)} listados"""

        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar usp_IA_ContasPagas: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _pesquisa_contas_a_pagar(self, data_vencimento: Optional[str] = None, data_emissao: Optional[str] = None, natureza: Optional[str] = None, fornecedor: Optional[str] = None, limite: Optional[int] = None) -> str:
        """
        Consulta contas a pagar (vencimentos futuros/pendentes).

        Args:
            data_vencimento: Data de vencimento (ex: "hoje", "próximos 7 dias", "este mês")
            data_emissao: Data de emissão do título (ex: "06/02/2026", "este mês")
            natureza: Filtro por natureza/tipo de despesa (ex: "compra de café", "INSS", "salário")

        Returns:
            Dados de contas a pagar formatados
        """
        logger.info(f"[CONTAS A PAGAR] Consultando contas a pagar - data_vencimento: {data_vencimento}, data_emissao: {data_emissao}, natureza: {natureza}, fornecedor: {fornecedor}, limite: {limite}")

        procedure_name = "usp_IA_ContasAPagar"
        procedure_params = {}
        expressao_periodo = data_vencimento if data_vencimento else data_emissao
        campo_data_periodo = "vencimento" if data_vencimento or not data_emissao else "emissao"
        periodo_inicio = None
        periodo_fim = None
        data_fim_filter = None
        emissao_fim_filter = None

        # Decide qual data usar e se usar versão _Par
        if data_emissao or data_vencimento:
            # Prioriza data_vencimento sobre data_emissao (mais comum)
            data_para_parse = data_vencimento if data_vencimento else data_emissao
            parsed = date_parser.parse_natural_date(data_para_parse)
            logger.info(f"[CONTAS A PAGAR] date_parser retornou: {parsed}")

            if parsed:
                # Extrai datas do parsed
                inicio = None
                fim = None

                # Prioridade 1: Se tem data_inicio e data_fim em YYYYMMDD (sempre preferir)
                if "data_inicio" in parsed and "data_fim" in parsed:
                    inicio = parsed["data_inicio"]
                    fim = parsed["data_fim"]
                    logger.info(f"[CONTAS A PAGAR] Período detectado ({inicio} até {fim})")
                # Prioridade 3: Se tem apenas data_inicio
                elif "data_inicio" in parsed:
                    inicio = parsed["data_inicio"]
                    fim = parsed.get("data_fim", inicio)
                    logger.info(f"[CONTAS A PAGAR] Data única detectada: {inicio}")

                # Para contas a pagar, "esta semana" considera domingo a sábado.
                texto_data = str(data_para_parse).lower()
                if inicio and fim and any(expressao in texto_data for expressao in ("esta semana", "essa semana", "desta semana", "nessa semana")):
                    from datetime import datetime, timedelta
                    inicio = (datetime.strptime(inicio, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                    fim = (datetime.strptime(fim, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")

                if inicio and fim:
                    inicio, fim = resolve_business_day_range(
                        expressao_periodo,
                        inicio,
                        fim,
                        today=date_parser.get_current_date(),
                    )
                    periodo_inicio, periodo_fim = inicio, fim
                    procedure_params["VencIni"] = inicio
                    procedure_params["VencFim"] = fim
        else:
            logger.info("[CONTAS A PAGAR] Consulta sem filtro de vencimento")

        if fornecedor:
            procedure_params["Fornec"] = fornecedor

        # Valida permissão
        has_permission, error_msg = sql_validator.validate_permission(self.user, procedure_name)
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: {procedure_name}")
            return error_msg

        logger.info(f"[CONTAS A PAGAR] Executando {procedure_name} com parâmetros: {procedure_params}")

        # Executa stored procedure
        try:
            result_list = sql_client.execute_procedure(procedure_name, procedure_params or None)
            self._log_financial_field_anomalies(result_list or [], "CONTAS A PAGAR")
            aviso_escopo = current_open_scope_notice(
                periodo_inicio,
                periodo_fim,
                today=date_parser.get_current_date(),
            )
            logger.info(
                "[CONTAS A PAGAR][ESCOPO] inicio=%s fim=%s classificacao=%s",
                periodo_inicio,
                periodo_fim,
                "posicao_atual_filtrada_data_passada" if aviso_escopo else "posicao_atual",
            )

            if result_list and periodo_inicio and periodo_fim and uses_business_days(expressao_periodo):
                result_list = filter_financial_rows_by_calendar(
                    result_list,
                    date_field=campo_data_periodo,
                    start=periodo_inicio,
                    end=periodo_fim,
                    business_days=True,
                )

            # Aplica filtro manual de emissao_fim se necessário
            if result_list and emissao_fim_filter:
                original_count = len(result_list)
                # Filtra: emissao >= data_inicio AND emissao <= emissao_fim
                result_list = [r for r in result_list if r.get("emissao", "") <= emissao_fim_filter]
                logger.info(f"[CONTAS A PAGAR] Filtro manual de emissão aplicado: {original_count} → {len(result_list)} registros (emissao <= {emissao_fim_filter})")

            # Aplica filtro manual de data_fim (vencimento) se necessário
            # IMPORTANTE: Se data_inicio == data_fim (mesmo dia), filtra para retornar APENAS aquele dia
            if result_list and data_fim_filter:
                original_count = len(result_list)
                # Filtra: vencimento >= data_inicio AND vencimento <= data_fim
                result_list = [r for r in result_list if r.get("vencimento", "") <= data_fim_filter]
                logger.info(f"[CONTAS A PAGAR] Filtro manual de vencimento aplicado: {original_count} → {len(result_list)} registros (vencimento <= {data_fim_filter})")

            # Aplica filtro por natureza se fornecido
            if result_list and natureza:
                original_count = len(result_list)
                natureza_upper = natureza.upper()
                # Filtro flexível: aceita match parcial (ex: "cafe" encontra "COMPRA DE CAFE BENEFICIADO")
                result_list = [r for r in result_list if natureza_upper in str(r.get("natureza", "")).upper()]
                logger.info(f"[CONTAS A PAGAR] Filtro por natureza '{natureza}': {original_count} → {len(result_list)} registros")

            contexto_periodo = build_financial_period_context(
                expressao_periodo,
                periodo_inicio,
                periodo_fim,
                result_list or [],
                date_field=campo_data_periodo,
            )
            if contexto_periodo:
                logger.info("[CONTAS A PAGAR][PERÍODO] %s", contexto_periodo)

            if not result_list:
                log_query_processing(
                    source_name=procedure_name,
                    original_count=0,
                    final_count=0,
                    post_filters={"natureza": natureza, "fornecedor": fornecedor},
                    calculated_totals={"valor_total": 0},
                    status_criterion="títulos atualmente pendentes",
                    unit="títulos",
                    currency="BRL",
                )
                return append_period_context(append_scope_notice(
                    "Nenhuma conta a pagar encontrada para o período especificado.",
                    aviso_escopo,
                ), contexto_periodo)

            result_list, duplicate_count = deduplicate_payables(result_list)
            if duplicate_count:
                logger.info(
                    "[CONTAS A PAGAR] Deduplicação: %s título(s) duplicado(s) removido(s)",
                    duplicate_count,
                )

            complete_result_list = result_list
            complete_total = sum(
                (payable_decimal(r.get("valor")) for r in complete_result_list),
                Decimal("0"),
            )
            log_query_processing(
                source_name=procedure_name,
                original_count=len(result_list) + duplicate_count,
                final_count=len(result_list),
                post_filters={
                    "natureza": natureza,
                    "fornecedor": fornecedor,
                    "duplicados_idProtheus_removidos": duplicate_count,
                },
                calculated_totals={"valor_total": complete_total},
                status_criterion="títulos atualmente pendentes",
                unit="títulos",
                currency="BRL",
            )
            full_reconciliation = reconcile_payables(
                complete_result_list,
                aggregate_total=complete_total,
                declared_count=len(complete_result_list),
            )
            if not full_reconciliation["valido"]:
                logger.error(
                    "[CONTAS A PAGAR][RECONCILIAÇÃO] Inconsistência. params=%s "
                    "total=%s soma_detalhes=%s diferenca=%s quantidade_declarada=%s "
                    "quantidade_detalhada=%s violacoes=%s",
                    procedure_params,
                    full_reconciliation["total"],
                    full_reconciliation["soma_detalhes"],
                    full_reconciliation["diferenca"],
                    full_reconciliation["quantidade_declarada"],
                    full_reconciliation["quantidade_detalhada"],
                    full_reconciliation["violacoes"],
                )
                return (
                    "Foi encontrada uma inconsistência na reconciliação das contas a pagar. "
                    "O resultado não será apresentado como confiável.\n\n"
                    f"Total informado: R$ {complete_total:,.2f}\n"
                    f"Soma dos títulos: R$ {full_reconciliation['soma_detalhes']:,.2f}\n"
                    f"Diferença: R$ {full_reconciliation['diferenca']:,.2f}"
                )

            # Consultas somente por fornecedor retornam 10 registros distintos por padrão.
            partial_listing = False
            if fornecedor and not data_vencimento and not data_emissao:
                if limite is None:
                    result_list = result_list[:10]
                elif limite > 0:
                    result_list = result_list[:limite]
                partial_listing = len(result_list) < len(complete_result_list)

            # O anexo do e-mail deve refletir o resultado final, depois dos
            # filtros e da deduplicacao aplicados nesta consulta.
            self._salvar_resultado_scheduler(result_list)

            # Se poucos registros (<= 50), retorna tabela compacta (evita JSON bruto que estoura tokens)
            if len(result_list) <= 50:
                total_geral = Decimal("0")
                linhas = []
                for r in result_list:
                    valor = payable_decimal(r.get("valor"))
                    total_geral += valor
                    num = str(r.get('numero', '')).strip()
                    parc = str(r.get('parcela', '')).strip()
                    forn = supplier_display(r)
                    nat = str(r.get('natureza', '')).strip()
                    venc = str(r.get('vencimento', '')).strip()
                    fil = str(r.get('filial', '')).strip()
                    zero_label = zero_value_classification(r)
                    zero_suffix = f" | {zero_label}" if zero_label else ""
                    linhas.append(f"{num}/{parc} | fil.{fil} | {forn} | {nat} | R$ {valor:,.2f} | venc:{venc}{zero_suffix}")

                detail_reconciliation = reconcile_payables(
                    result_list,
                    aggregate_total=complete_total if not partial_listing else total_geral,
                    declared_count=len(result_list),
                    partial=partial_listing,
                    complete_count=len(complete_result_list),
                )
                if not detail_reconciliation["valido"]:
                    logger.error(
                        "[CONTAS A PAGAR][RECONCILIAÇÃO] Detalhe divergente. params=%s dados=%s",
                        procedure_params,
                        detail_reconciliation,
                    )
                    return (
                        "Foi encontrada uma inconsistência entre o total e os títulos das "
                        "contas a pagar. O resultado não será apresentado como confiável."
                    )

                tabela_str = "\n".join(linhas)
                partial_notice = ""
                total_complete_notice = ""
                if partial_listing:
                    partial_notice = (
                        f"LISTAGEM PARCIAL: exibindo {len(result_list)} de "
                        f"{len(complete_result_list)} títulos.\n"
                    )
                    total_complete_notice = f"Valor total do conjunto completo: R$ {complete_total:,.2f}\n"
                partial_instruction = (
                    "A listagem é parcial. Não afirme que os títulos exibidos representam "
                    "todo o conjunto."
                    if partial_listing
                    else "A listagem contém todos os títulos usados no total informado."
                )
                return append_period_context(append_scope_notice(f"""Resultados da consulta usp_IA_ContasAPagar:

{partial_notice}Total de títulos detalhados: {len(result_list)}
Valor dos títulos detalhados: R$ {total_geral:,.2f}
{total_complete_notice}

TABELA (numero/parcela | filial | fornecedor | natureza | valor | vencimento):
{tabela_str}

Analise os {len(result_list)} registros acima e responda com base nos dados fornecidos.
Fornecedor e natureza são campos separados; nunca copie natureza/descrição para fornecedor.
As classificações após o vencimento identificam registros com valor zero.
{partial_instruction}""", aviso_escopo), contexto_periodo)

            # Agrega por dia de vencimento E por fornecedor
            from collections import defaultdict
            por_dia = defaultdict(lambda: {"valor_total": 0, "quantidade": 0})
            por_fornecedor = defaultdict(lambda: {
                "valor_total": 0,
                "quantidade": 0,
                "naturezas": set(),
                "vencimentos": []
            })

            total_geral = 0
            _, zero_rows = split_zero_value_records(result_list)

            for r in result_list:
                fornecedor = supplier_display(r)
                vencimento = str(r.get("vencimento", "")).strip() or "SEM DATA"
                valor = r.get("valor", 0)

                # Converte valor para float
                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        # Tenta conversao direta primeiro
                        valor = float(valor)
                    except:
                        try:
                            # Se falhar, tenta limpar formatacao
                            valor_limpo = valor.replace("R$", "").replace(",", "").strip()
                            valor = float(valor_limpo)
                        except:
                            valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                # Agrega por dia de vencimento
                por_dia[vencimento]["valor_total"] += valor
                por_dia[vencimento]["quantidade"] += 1

                # Registros zerados não participam do ranking de fornecedores.
                if valor != 0:
                    por_fornecedor[fornecedor]["valor_total"] += valor
                    por_fornecedor[fornecedor]["quantidade"] += 1

                    natureza = str(r.get("natureza") or "").strip()
                    if natureza:
                        por_fornecedor[fornecedor]["naturezas"].add(natureza)

                    if vencimento != "SEM DATA":
                        por_fornecedor[fornecedor]["vencimentos"].append(vencimento)

                total_geral += valor

            # Monta lista de totais por dia (ordenada por data)
            dias_list = [
                {
                    "vencimento": v,
                    "valor_total": round(d["valor_total"], 2),
                    "quantidade_titulos": d["quantidade"]
                }
                for v, d in sorted(por_dia.items())
            ]

            # Monta lista por fornecedor (top 50 por valor)
            fornecedores_list = []
            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor_total"]), reverse=True)

            for fornecedor, dados in fornecedores_ordenados[:50]:
                vencimentos_unicos = sorted(set(dados["vencimentos"]))[:3]
                fornecedores_list.append({
                    "fornecedor": fornecedor,
                    "valor_total": round(dados["valor_total"], 2),
                    "quantidade_titulos": dados["quantidade"],
                    "naturezas": sorted(list(dados["naturezas"])),
                    "proximos_vencimentos": vencimentos_unicos
                })

            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            formatted_por_dia = json.dumps(dias_list, ensure_ascii=False, indent=2, default=convert_decimals)
            formatted_por_fornecedor = json.dumps(fornecedores_list, ensure_ascii=False, indent=2, default=convert_decimals)
            zero_notice = ""
            if zero_rows:
                zero_notice = (
                    f"\n\nREGISTROS COM VALOR ZERO (fora do ranking): {len(zero_rows)}\n"
                    + format_zero_value_records(zero_rows)
                )

            return append_period_context(append_scope_notice(f"""Resultados da consulta usp_IA_ContasAPagar:

Total de registros: {len(result_list)}
Total de fornecedores únicos: {len(por_fornecedor)}
Valor total a pagar: R$ {total_geral:,.2f}

TOTAIS POR DIA DE VENCIMENTO:
{formatted_por_dia}

Top {len(fornecedores_list)} maiores fornecedores (por valor):
{formatted_por_fornecedor}{zero_notice}

IMPORTANTE:
1. Estas são contas PENDENTES (a pagar no futuro)
2. Os totais por dia e por fornecedor já estão calculados acima
3. Para responder "total por dia", use a seção TOTAIS POR DIA DE VENCIMENTO
4. Mostrando apenas os {len(fornecedores_list)} maiores fornecedores de um total de {len(por_fornecedor)}""", aviso_escopo), contexto_periodo)

        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar usp_IA_ContasAPagar: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _pesquisa_saldo_bancario(self, banco: Optional[str] = None) -> str:
        """
        Consulta saldo bancário atual da empresa.
        NÃO requer filtros de data (retorna snapshot atual).

        Args:
            banco: Filtro por banco (ex: "ITAU SANTOS", "BB", "BRADESCO")

        Returns:
            Saldo bancário agregado por banco e moeda
        """
        logger.info(f"[SALDO BANCARIO] Consultando saldo bancário - banco: {banco}")

        # Valida permissão
        has_permission, error_msg = sql_validator.validate_permission(self.user, "IA_SaldoBancario")
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: IA_SaldoBancario")
            return error_msg

        # Executa query
        try:
            result_list = sql_client.execute_function("dbo.IA_SaldoBancario", filters=None)
            self._salvar_resultado_scheduler(result_list)

            if not result_list:
                return "Nenhum saldo bancário encontrado."

            # OTIMIZAÇÃO: Detecta múltiplos bancos mencionados na pergunta do usuário
            # Exemplo: "Banco do Brasil e Itaú Santos" → filtra apenas esses dois
            bancos_mencionados = []
            if self.user_query and not banco:  # Só se não veio filtro explícito
                query_lower = self.user_query.lower()

                # Mapeamento de nomes comuns → padrões de busca no banco
                bancos_conhecidos = {
                    "banco do brasil": ["BB STOS", "BB NY"],  # Específicos para evitar "BB" genérico
                    "itau santos": ["ITAU STOS"],  # Apenas ITAU STOS (não todos os ITAU)
                    "itaú santos": ["ITAU STOS"],
                    "bradesco santos": ["BRADESCO STOS"],
                    "bradesco": ["BRADESCO"],
                    "santander": ["SANTANDER"],
                    "citibank": ["CITI"],
                    "safra": ["SAFRA"],
                }

                for nome_busca, padroes in bancos_conhecidos.items():
                    if nome_busca in query_lower:
                        bancos_mencionados.extend(padroes)
                        logger.info(f"[SALDO BANCARIO] Banco detectado na pergunta: '{nome_busca}' → {padroes}")

                # Se detectou múltiplos bancos, filtra apenas esses
                if len(bancos_mencionados) > 0:
                    original_count = len(result_list)
                    result_list_filtrado = []

                    for r in result_list:
                        banco_row = self._remove_accents(str(r.get("banco", "")).upper())
                        for padrao in bancos_mencionados:
                            padrao_normalizado = self._remove_accents(padrao.upper())
                            if padrao_normalizado in banco_row:
                                result_list_filtrado.append(r)
                                break

                    if result_list_filtrado:
                        result_list = result_list_filtrado
                        logger.info(f"[SALDO BANCARIO] Filtro automático aplicado: {original_count} → {len(result_list)} registros (bancos: {bancos_mencionados})")
                    else:
                        logger.warning(f"[SALDO BANCARIO] Filtro automático não encontrou bancos para: {bancos_mencionados}")

            # Aplica filtro por banco se fornecido explicitamente
            if result_list and banco:
                original_count = len(result_list)

                # Mapeamento de aliases comuns (cidade completa → abreviação)
                banco_aliases = {
                    "SANTOS": "STOS",
                    "SAO PAULO": "SP",
                    "SÃO PAULO": "SP",
                    "BANCO DO BRASIL": "BB",
                }

                # Remove acentos e converte para maiúsculas
                banco_normalizado = self._remove_accents(banco.upper())

                # Aplica aliases
                for alias, real in banco_aliases.items():
                    alias_sem_acento = self._remove_accents(alias)
                    if alias_sem_acento in banco_normalizado:
                        banco_normalizado = banco_normalizado.replace(alias_sem_acento, real)
                        logger.info(f"[SALDO BANCARIO] Alias aplicado: '{alias}' → '{real}'")

                result_list = [
                    r for r in result_list
                    if banco_normalizado in self._remove_accents(str(r.get("banco", "")).upper())
                ]
                logger.info(f"[SALDO BANCARIO] Filtro por banco '{banco}' (normalizado: '{banco_normalizado}'): {original_count} → {len(result_list)} registros")

                if not result_list:
                    return f"Nenhuma conta bancária encontrada para '{banco}'."

            # Mostra cada conta individualmente (sem agregar por banco+moeda)
            # Isso garante que múltiplas contas do mesmo banco sejam mostradas separadamente
            # Ex: ABC BRASIL com 2 contas em Reais → aparecem como 2 entradas distintas
            from collections import defaultdict

            total_por_moeda = defaultdict(float)
            entradas_list = []
            ordem_moedas = {"Reais": 0, "Dolares": 1, "Dolar": 1, "Euros": 2, "Euro": 2, "Libras": 3, "Libra": 3}

            for r in result_list:
                banco_nome = r.get("banco", "").strip() or "SEM BANCO"
                moeda = r.get("moeda", "").strip() or "Reais"
                saldo = r.get("saldo", 0)

                # Converte saldo
                if saldo is None:
                    saldo = 0
                elif isinstance(saldo, Decimal):
                    saldo = float(saldo)
                elif isinstance(saldo, str):
                    try:
                        saldo = float(saldo)
                    except:
                        saldo = 0
                elif not isinstance(saldo, (int, float)):
                    saldo = 0

                # Ignora contas com saldo zero
                if saldo == 0:
                    continue

                agencia = r.get("agencia", "").strip()
                conta_num = r.get("conta", "").strip()
                filial_num = str(r.get("filial", "")).strip()

                entradas_list.append({
                    "banco": banco_nome,
                    "moeda": moeda,
                    "saldo": round(saldo, 2),
                    "agencia": agencia,
                    "conta": conta_num,
                    "filial": filial_num
                })

                total_por_moeda[moeda] += saldo

            # Ordena: primeiro por moeda (Reais, depois outras), depois por saldo absoluto
            entradas_ordenadas = sorted(
                entradas_list,
                key=lambda x: (ordem_moedas.get(x["moeda"], 99), -abs(x["saldo"]))
            )

            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            formatted = json.dumps(entradas_ordenadas, ensure_ascii=False, indent=2, default=convert_decimals)

            # Monta resumo por moeda (todas as moedas encontradas)
            resumo_moedas = []
            moedas_ordenadas = sorted(total_por_moeda.items(), key=lambda x: ordem_moedas.get(x[0], 99))

            for moeda, total in moedas_ordenadas:
                resumo_moedas.append(f"  {moeda}: R$ {total:,.2f}")

            resumo_str = "\n".join(resumo_moedas) if resumo_moedas else "  Nenhum saldo"

            # Mensagem adicional se filtrou automaticamente
            filtro_msg = ""
            if bancos_mencionados:
                filtro_msg = f"\n⚠️ FILTRADO AUTOMATICAMENTE: Mostrando apenas bancos mencionados na pergunta ({', '.join(set(bancos_mencionados))})\n"

            return f"""Resultados da consulta IA_SaldoBancario:

Total de contas com saldo: {len(entradas_list)} (de {len(result_list)} contas no total)
{filtro_msg}
SALDO TOTAL POR MOEDA:
{resumo_str}

⚠️ CRÍTICO: INCLUA TODAS AS {len(entradas_list)} CONTAS LISTADAS ABAIXO NA SUA RESPOSTA.
NÃO omita nenhuma conta, mesmo que o saldo seja pequeno.
Cada linha abaixo é uma conta DIFERENTE que deve aparecer na resposta.

Detalhamento por conta:
{formatted}

IMPORTANTE:
1. Saldos POSITIVOS = dinheiro disponível
2. Saldos NEGATIVOS = saldo devedor (banco emprestou para empresa)
3. Cada entrada é uma conta bancária individual
4. Um mesmo banco pode ter múltiplas contas (ex: ABC BRASIL com conta A e conta B)
5. Apresente TODAS as contas agrupadas por banco na resposta final

⚠️ ATENÇÃO - MÚLTIPLAS CONTAS DO MESMO BANCO:
- Se o mesmo banco aparecer mais de uma vez, liste TODAS as contas separadamente
- Exemplo: ABC BRASIL conta 0066011568 E conta 0002231517 são contas DIFERENTES
- NÃO some contas diferentes do mesmo banco a menos que o usuário peça o total do banco

⚠️ ATENÇÃO - MÚLTIPLOS BANCOS NA PERGUNTA:
- Se a pergunta menciona "Banco A e Banco B", inclua AMBOS na resposta
- SOME os saldos de TODOS os bancos mencionados
- NÃO omita nenhum banco que foi explicitamente mencionado"""

        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar IA_SaldoBancario: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _pesquisa_estoque(self) -> str:
        """
        Consulta estoque de produtos.
        NÃO requer filtros de data (retorna snapshot atual).

        Returns:
            Dados do estoque atual
        """
        return self._validate_and_execute("IA_Estoque")

    def _pesquisa_orcamento(self, periodo: Optional[str] = None, filial: Optional[str] = None, cc: Optional[str] = None) -> str:
        """
        Consulta orçamento vs realizado.

        Args:
            periodo: Período desejado (ex: "dezembro 2025", "2025/12", "2TRIM 2025")
            filial: Código da filial para filtrar (ex: "61", "Santos")
            cc: Código do centro de custo para filtrar (ex: "TI", "0010")

        Returns:
            Dados de orçamento
        """
        # NOVA LÓGICA: Detecta se deve usar IA_OrcamentoPar ou IA_Orcamento
        function_name = "IA_Orcamento"
        filters = None

        if periodo:
            parsed = date_parser.parse_natural_date(periodo)
            logger.info(f"[ORÇAMENTO] date_parser retornou: {parsed}")

            if parsed:
                # PRIORIDADE 1: Se tem lista de meses (trimestre/semestre)
                if "meses" in parsed and "ano" in parsed:
                    # Para múltiplos meses, usa primeira e última data
                    ano = parsed["ano"]
                    meses = parsed["meses"]
                    mes_inicio = meses[0]  # Primeiro mês
                    mes_fim = meses[-1]    # Último mês

                    function_name = "IA_OrcamentoPar"
                    filters = {
                        "data_inicio": f"{ano}{mes_inicio}",  # Ex: "202604"
                        "data_fim": f"{ano}{mes_fim}"         # Ex: "202606"
                    }
                    logger.info(f"[ORÇAMENTO] Trimestre/Semestre detectado - Usando IA_OrcamentoPar('{ano}{mes_inicio}', '{ano}{mes_fim}')")
                # PRIORIDADE 2: Mês único
                elif "ano" in parsed and "mes" in parsed:
                    ano = parsed["ano"]
                    mes = parsed["mes"]

                    function_name = "IA_OrcamentoPar"
                    filters = {
                        "data_inicio": f"{ano}{mes}",  # Ex: "202601"
                        "data_fim": f"{ano}{mes}"      # Ex: "202601"
                    }
                    logger.info(f"[ORÇAMENTO] Mês único - Usando IA_OrcamentoPar('{ano}{mes}', '{ano}{mes}')")
                # PRIORIDADE 3: Se tem mes_embarque (formato YYYY/MM)
                elif "mes_embarque" in parsed:
                    mes_embarque = parsed["mes_embarque"].replace("/", "")  # "2026/01" → "202601"

                    function_name = "IA_OrcamentoPar"
                    filters = {
                        "data_inicio": mes_embarque,
                        "data_fim": mes_embarque
                    }
                    logger.info(f"[ORÇAMENTO] Mês detectado - Usando IA_OrcamentoPar('{mes_embarque}', '{mes_embarque}')")
        else:
            logger.info("[ORÇAMENTO] Sem período - usando IA_Orcamento() sem parâmetros")

        # Adiciona filtros de filial e cc se fornecidos (como WHERE filters)
        if filial:
            filters = filters or {}
            filters["filial"] = filial
            logger.info(f"[ORÇAMENTO] Filtro filial: {filial}")
        if cc:
            filters = filters or {}
            filters["cc"] = cc
            logger.info(f"[ORÇAMENTO] Filtro centro de custo: {cc}")

        return self._validate_and_execute(function_name, filters)

    def _pesquisa_longshort(self) -> str:
        """
        Consulta posição do Long/Short por filial.

        Detecta automaticamente a filial mencionada na query:
        - COBRA / comexim brasil → @FILIAL='COBRA'
        - CUSA / comexim usa → @FILIAL='CUSA'
        - CEU / comexim europa → @FILIAL='CEU'
        - Sem especificação → @FILIAL='FILIAIS' (totalizador)

        Colunas disponíveis:
        - netPosition: Posição do LongShort
        - totalEstoque: Total do estoque
        - vendasExportacao: Vendas exportáveis
        - comprasConsumo: Compras de mercado interno/consumo

        Returns:
            Dados de Long/Short formatados
        """
        logger.info(f"[LONGSHORT] Consultando Long/Short - query original: {self.user_query_original}")

        # Valida permissão
        has_permission, error_msg = sql_validator.validate_permission(self.user, "usp_LS_FILIAIS")
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: usp_LS_FILIAIS")
            return error_msg

        # Detecta filial mencionada na query
        filial = None
        query_lower = self.user_query_original.lower() if self.user_query_original else ""

        # Mapeamento de termos para códigos de filial
        if any(term in query_lower for term in ["cobra", "comexim brasil", "brasil"]):
            filial = "COBRA"
            logger.info(f"[LONGSHORT] Filial detectada: COBRA")
        elif any(term in query_lower for term in ["cusa", "comexim usa", "usa", "eua"]):
            filial = "CUSA"
            logger.info(f"[LONGSHORT] Filial detectada: CUSA")
        elif any(term in query_lower for term in ["ceu", "comexim europa", "europa"]):
            filial = "CEU"
            logger.info(f"[LONGSHORT] Filial detectada: CEU")
        else:
            # Padrão: totalizador de todas as filiais
            filial = "FILIAIS"
            logger.info(f"[LONGSHORT] Nenhuma filial específica detectada, usando totalizador FILIAIS")

        # Monta parâmetros para a stored procedure
        params = {"FILIAL": filial}

        # Executa stored procedure (usa EXEC ao invés de SELECT)
        try:
            execution_id = uuid.uuid4().hex[:12]
            started_at = datetime.now(timezone.utc)
            started_clock = time.perf_counter()
            logger.info(
                "[LONGSHORT SNAPSHOT][%s] início=%s procedure=usp_LS_FILIAIS parâmetros=%s",
                execution_id,
                started_at.isoformat(),
                params,
            )
            results = sql_client.execute_procedure("usp_LS_FILIAIS", params)
            self._salvar_resultado_scheduler(results)
            if results:
                snapshot = build_longshort_snapshot(results[0])
                logger.info(
                    "[LONGSHORT SNAPSHOT][%s] fim=%s duração_ms=%.2f "
                    "procedure=usp_LS_FILIAIS parâmetros=%s linhas=%s fingerprint=%s "
                    "componentes=%s colunas=%s",
                    execution_id,
                    datetime.now(timezone.utc).isoformat(),
                    (time.perf_counter() - started_clock) * 1000,
                    params,
                    len(results),
                    snapshot_fingerprint(results),
                    snapshot,
                    sorted(str(key) for key in results[0].keys()),
                )
                if len(results) != 1:
                    logger.warning(
                        "[LONGSHORT SNAPSHOT][%s] A procedure retornou %s linhas; "
                        "o quadro oficial usa exclusivamente a primeira linha do mesmo snapshot.",
                        execution_id,
                        len(results),
                    )
            else:
                logger.info(
                    "[LONGSHORT SNAPSHOT][%s] fim=%s duração_ms=%.2f "
                    "procedure=usp_LS_FILIAIS parâmetros=%s linhas=0 fingerprint=%s",
                    execution_id,
                    datetime.now(timezone.utc).isoformat(),
                    (time.perf_counter() - started_clock) * 1000,
                    params,
                    snapshot_fingerprint(results),
                )
            return self._format_longshort_results(results)
        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar usp_LS_FILIAIS: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    @staticmethod
    def _format_longshort_results(results: list[Dict[str, Any]]) -> str:
        """Formata a posicao Long/Short sempre no modelo comercial oficial."""
        if not results:
            return "Nenhum dado de posição Long/Short foi encontrado."

        snapshot = build_longshort_snapshot(results[0])
        log_query_processing(
            source_name="usp_LS_FILIAIS",
            original_count=len(results),
            final_count=1,
            post_filters={"snapshot": "primeira linha da mesma execução"},
            calculated_totals=snapshot,
            status_criterion="posição atual",
            unit="sacas/lotes",
        )
        return format_longshort_snapshot(snapshot)

    def _pesquisa_contas_a_receber_vencidas(
        self,
        cliente: Optional[str] = None,
        somente_negativas: bool = False,
    ) -> str:
        """Consulta a posição vencida, opcionalmente por cliente ou somente créditos."""
        function_name = "IA_ContasAReceberPar"
        hoje = date_parser.get_current_date().strftime("%Y%m%d")
        filters = {
            "data_inicio": "19990101",
            "data_fim": hoje,
            "tipo": "Receber",
        }
        if cliente:
            filters["cliente"] = cliente.strip()
        if somente_negativas:
            filters["saldo_lt"] = 0

        has_permission, error_msg = sql_validator.validate_permission(self.user, function_name)
        if not has_permission:
            logger.warning(
                "Permissão negada para %s: %s",
                self.user.telefone,
                function_name,
            )
            return error_msg

        logger.info(
            "[CONTAS A RECEBER VENCIDAS] Executando dbo.%s('19990101', '%s') "
            "com tipo='Receber', cliente=%r e somente_negativas=%s",
            function_name,
            hoje,
            cliente,
            somente_negativas,
        )

        try:
            result_list = sql_client.execute_function(f"dbo.{function_name}", filters)
            self._salvar_resultado_scheduler(result_list)

            def numero(valor: Any) -> Decimal:
                if valor is None:
                    return Decimal("0")
                if isinstance(valor, Decimal):
                    return valor
                if isinstance(valor, (int, float)):
                    return Decimal(str(valor))
                try:
                    texto = str(valor).replace("R$", "").strip()
                    if "," in texto:
                        texto = texto.replace(".", "").replace(",", ".")
                    return Decimal(texto)
                except (TypeError, ValueError, ArithmeticError):
                    return Decimal("0")

            def moeda_da_linha(row: Dict[str, Any]) -> str:
                # O banco fornece a sigla/simbolo pronto para exibicao (por
                # exemplo, US$ e EU$). Nao convertemos nem presumimos que
                # moedas diferentes possam ser somadas.
                return str(row.get("moeda") or "Moeda não informada").strip()

            def saldos_formatados(saldos: Dict[str, Decimal]) -> str:
                return "; ".join(
                    f"{moeda} {format_pt_br(saldo)}"
                    for moeda, saldo in sorted(saldos.items(), key=lambda item: item[0].casefold())
                )

            from collections import defaultdict

            totais_por_moeda = defaultdict(lambda: Decimal("0"))
            for row in result_list:
                totais_por_moeda[moeda_da_linha(row)] += numero(row.get("saldo"))

            log_query_processing(
                source_name=function_name,
                original_count=len(result_list),
                final_count=len(result_list),
                post_filters={"cliente": cliente, "somente_negativas": somente_negativas},
                calculated_totals={
                    "saldo_total_por_moeda": dict(totais_por_moeda),
                },
                status_criterion="vencidos que permanecem em aberto atualmente",
                unit="títulos",
                currency=",".join(sorted(totais_por_moeda, key=str.casefold)),
            )

            if not result_list:
                return append_scope_notice(
                    "Nenhuma conta a receber vencida encontrada.",
                    CURRENT_OPEN_PAST_NOTICE,
                )

            # Em seguimentos por cliente, detalha todos os contratos encontrados.
            if cliente:
                por_contrato = defaultdict(
                    lambda: {"saldos": defaultdict(lambda: Decimal("0")), "titulos": 0}
                )
                for row in result_list:
                    contrato = str(row.get("contrato") or "SEM CONTRATO").strip()
                    moeda = moeda_da_linha(row)
                    por_contrato[contrato]["saldos"][moeda] += numero(row.get("saldo"))
                    por_contrato[contrato]["titulos"] += 1

                contratos = sorted(
                    por_contrato.items(),
                    key=lambda item: item[0].casefold(),
                )
                linhas_contratos = [
                    f"- {contrato}: {saldos_formatados(dados['saldos'])} "
                    f"({dados['titulos']} título(s))"
                    for contrato, dados in contratos
                ]
                return append_scope_notice((
                    f"Contas a receber vencidas do cliente {cliente}:\n\n"
                    f"Saldo líquido por moeda: {saldos_formatados(totais_por_moeda)}\n"
                    f"Quantidade de contratos: {len(por_contrato)}\n\n"
                    "Todos os contratos:\n"
                    + "\n".join(linhas_contratos)
                ), CURRENT_OPEN_PAST_NOTICE)

            por_cliente = defaultdict(
                lambda: {
                    "saldos": defaultdict(lambda: Decimal("0")),
                    "contratos": set(),
                    "titulos": 0,
                }
            )
            for row in result_list:
                nome = str(row.get("cliente") or row.get("fornecedor") or "SEM IDENTIFICAÇÃO").strip()
                moeda = moeda_da_linha(row)
                por_cliente[nome]["saldos"][moeda] += numero(row.get("saldo"))
                contrato = str(row.get("contrato") or "").strip()
                if contrato:
                    por_cliente[nome]["contratos"].add(contrato)
                por_cliente[nome]["titulos"] += 1

            clientes_ordenados = sorted(
                por_cliente.items(),
                key=lambda item: item[0].casefold(),
            )
            linhas = [
                f"- {nome}: {saldos_formatados(dados['saldos'])} | "
                f"{len(dados['contratos'])} contrato(s)"
                for nome, dados in clientes_ordenados
            ]
            linhas_totais = [
                f"- {moeda}: {format_pt_br(saldo)}"
                for moeda, saldo in sorted(
                    totais_por_moeda.items(), key=lambda item: item[0].casefold()
                )
            ]
            titulo_lista = (
                "Todos os clientes com contas negativas (créditos):"
                if somente_negativas
                else "Todos os clientes:"
            )
            return append_scope_notice((
                "Resultados de contas a receber vencidas:\n\n"
                f"Total de registros: {len(result_list)}\n"
                "Saldo total vencido por moeda:\n"
                + "\n".join(linhas_totais)
                + "\n"
                f"Total de clientes: {len(por_cliente)}\n\n"
                f"{titulo_lista}\n"
                + "\n".join(linhas)
                + "\n\nOs saldos totais por moeda são líquidos: incluem valores positivos e negativos (créditos do comprador). Todos os registros possuem tipo Receber."
            ), CURRENT_OPEN_PAST_NOTICE)
        except Exception as e:
            logger.error("[CONTAS A RECEBER VENCIDAS] Erro na consulta: %s", e, exc_info=True)
            return "Desculpe, ocorreu um erro ao consultar as contas a receber vencidas."

    def _pesquisa_contas_a_receber(self, data_vencimento: Optional[str] = None, cliente: Optional[str] = None, contrato: Optional[str] = None) -> str:
        """
        Consulta contas a receber (recebimentos futuros/pendentes).

        Args:
            data_vencimento: Data de vencimento (ex: "hoje", "próximos 7 dias", "este mês")
            cliente: Filtro por cliente (ex: "NESTLE", "STARBUCKS")
            contrato: Filtro por contrato específico (ex: "256/25R", "031/25")

        Returns:
            Dados de contas a receber formatados
        """
        logger.info(f"[CONTAS A RECEBER] Consultando contas a receber - data_vencimento: {data_vencimento}, cliente: {cliente}, contrato: {contrato}")

        # NOVA LÓGICA: Detecta se deve usar IA_ContasAReceberPar ou IA_ContasAReceber
        function_name = "IA_ContasAReceber"
        filters = {"tipo": "Receber"}
        vencimento_inicio_filter = None
        data_fim_filter = None
        periodo_inicio = None
        periodo_fim = None

        # DETECÇÃO DE "VENCIDO": se query menciona "vencido/vencidas" sem data explícita,
        # usa range de 1 ano atrás até hoje (contas já vencidas)
        if not data_vencimento and self.user_query_original:
            query_lower = self.user_query_original.lower()
            if re.search(r'\bvencid[oa]s?\b', query_lower):
                import pytz
                from datetime import datetime as _dt, timedelta as _td
                TZ_SP = pytz.timezone("America/Sao_Paulo")
                hoje_sp = _dt.now(TZ_SP)
                um_ano_atras = hoje_sp - _td(days=365)
                function_name = "IA_ContasAReceberPar"
                filters = {
                    "data_inicio": um_ano_atras.strftime('%Y%m%d'),
                    "data_fim": hoje_sp.strftime('%Y%m%d'),
                    "tipo": "Receber",
                }
                periodo_inicio = filters["data_inicio"]
                periodo_fim = filters["data_fim"]
                logger.info(f"[CONTAS A RECEBER] 'vencido' detectado sem data - usando IA_ContasAReceberPar({filters['data_inicio']}, {filters['data_fim']})")

        if data_vencimento:
            parsed = date_parser.parse_natural_date(data_vencimento)
            logger.info(f"[CONTAS A RECEBER] date_parser retornou: {parsed}")

            if parsed:
                # Extrai datas do parsed
                inicio = None
                fim = None

                # Datas de vencimento têm prioridade. O campo mes_embarque é
                # apenas metadado do parser e não pode substituir YYYYMMDD.
                if "data_inicio" in parsed and "data_fim" in parsed:
                    inicio = parsed["data_inicio"]
                    fim = parsed["data_fim"]
                    logger.info(f"[CONTAS A RECEBER] Período detectado ({inicio} até {fim})")
                elif "data_inicio" in parsed:
                    inicio = parsed["data_inicio"]
                    fim = parsed.get("data_fim", inicio)
                    logger.info(f"[CONTAS A RECEBER] Data única detectada: {inicio}")

                # Se temos datas, usa IA_ContasAReceberPar com parâmetros
                if inicio and fim:
                    inicio, fim = resolve_business_day_range(
                        data_vencimento,
                        inicio,
                        fim,
                        today=date_parser.get_current_date(),
                    )
                    periodo_inicio, periodo_fim = inicio, fim
                    function_name = "IA_ContasAReceberPar"
                    filters, vencimento_inicio_filter, data_fim_filter = (
                        build_receivables_current_open_query(
                            inicio,
                            fim,
                            today=date_parser.get_current_date(),
                        )
                    )
                    logger.info(
                        "[CONTAS A RECEBER] Usando IA_ContasAReceberPar('%s', '%s') "
                        "WHERE tipo='Receber'; recorte local vencimentoReal=%s..%s",
                        filters["data_inicio"],
                        filters["data_fim"],
                        vencimento_inicio_filter,
                        data_fim_filter,
                    )
                else:
                    # Mantém lógica antiga de filtro manual para compatibilidade
                    filters = {"vencimentoReal": parsed["data_inicio"], "tipo": "Receber"}
                    if "data_fim" in parsed:
                        data_fim_filter = parsed["data_fim"]
        else:
            logger.info("[CONTAS A RECEBER] Sem data - usando IA_ContasAReceber() sem parâmetros")

        # Valida permissão (usa function_name detectado)
        has_permission, error_msg = sql_validator.validate_permission(self.user, function_name)
        if not has_permission:
            logger.warning(f"Permissão negada para {self.user.telefone}: {function_name}")
            return error_msg

        # Executa query
        try:
            result_list = sql_client.execute_function(f"dbo.{function_name}", filters)
            aviso_escopo = current_open_scope_notice(
                periodo_inicio,
                periodo_fim,
                today=date_parser.get_current_date(),
            )
            logger.info(
                "[CONTAS A RECEBER][ESCOPO] fonte=%s inicio=%s fim=%s classificacao=%s",
                function_name,
                periodo_inicio,
                periodo_fim,
                "posicao_atual_filtrada_data_passada" if aviso_escopo else "posicao_atual",
            )
            # A função retorna a posição atual acumulada. Para uma data passada,
            # recorta em código somente o vencimento solicitado.
            if result_list and vencimento_inicio_filter and data_fim_filter:
                original_count = len(result_list)
                result_list = [
                    r for r in result_list
                    if vencimento_inicio_filter
                    <= compact_financial_date(r.get("vencimentoReal"))
                    <= data_fim_filter
                ]
                logger.info(
                    "[CONTAS A RECEBER] Recorte local de vencimentoReal %s..%s: %s → %s registros",
                    vencimento_inicio_filter,
                    data_fim_filter,
                    original_count,
                    len(result_list),
                )

            if result_list and periodo_inicio and periodo_fim and uses_business_days(data_vencimento):
                result_list = filter_financial_rows_by_calendar(
                    result_list,
                    date_field="vencimentoReal",
                    start=periodo_inicio,
                    end=periodo_fim,
                    business_days=True,
                )

            # Aplica filtro por cliente se fornecido
            if result_list and cliente:
                original_count = len(result_list)
                cliente_upper = cliente.upper()
                result_list = [r for r in result_list if cliente_upper in str(r.get("cliente", "")).upper()]
                logger.info(f"[CONTAS A RECEBER] Filtro por cliente '{cliente}': {original_count} → {len(result_list)} registros")

            # Aplica filtro por contrato se fornecido
            if result_list and contrato:
                original_count = len(result_list)
                contrato_normalizado = self._normalizar_contrato(contrato)
                result_list = [r for r in result_list if self._normalizar_contrato(str(r.get("contrato", ""))) == contrato_normalizado]
                logger.info(f"[CONTAS A RECEBER] Filtro por contrato '{contrato}' (normalizado: {contrato_normalizado}): {original_count} → {len(result_list)} registros")

            contexto_periodo = build_financial_period_context(
                data_vencimento,
                periodo_inicio,
                periodo_fim,
                result_list or [],
                date_field="vencimentoReal",
            )
            if contexto_periodo:
                logger.info("[CONTAS A RECEBER][PERÍODO] %s", contexto_periodo)

            # O anexo deve conter somente o período pedido e os demais filtros.
            self._salvar_resultado_scheduler(result_list)

            log_query_processing(
                source_name=function_name,
                original_count=len(result_list),
                final_count=len(result_list),
                post_filters={
                    "vencimento_inicio": periodo_inicio,
                    "vencimento_fim": periodo_fim,
                    "cliente": cliente,
                    "contrato": contrato,
                    "dias_uteis": uses_business_days(data_vencimento),
                },
                calculated_totals={
                    "valor_total": sum(
                        (payable_decimal(row.get("valor")) for row in result_list),
                        Decimal("0"),
                    ),
                    "saldo_total": sum(
                        (payable_decimal(row.get("saldo")) for row in result_list),
                        Decimal("0"),
                    ),
                },
                status_criterion="títulos atualmente pendentes",
                unit="títulos",
                currency="BRL",
            )

            if not result_list:
                msg = "Nenhuma conta a receber encontrada"
                if contrato:
                    msg += f" para o contrato {contrato}"
                if data_vencimento:
                    msg += f" no período especificado"
                return append_period_context(
                    append_scope_notice(msg + ".", aviso_escopo),
                    contexto_periodo,
                )

            # Se contrato específico foi solicitado E poucos registros (<= 50), retorna detalhes completos
            if contrato and len(result_list) <= 50:
                # Calcula total geral
                total_valor = 0
                total_saldo = 0
                for r in result_list:
                    valor = r.get("valor", 0)
                    saldo = r.get("saldo", 0)

                    # Converte valores
                    if isinstance(valor, Decimal):
                        valor = float(valor)
                    elif isinstance(valor, str):
                        try:
                            valor = float(valor)
                        except:
                            valor = 0
                    elif not isinstance(valor, (int, float)):
                        valor = 0

                    if isinstance(saldo, Decimal):
                        saldo = float(saldo)
                    elif isinstance(saldo, str):
                        try:
                            saldo = float(saldo)
                        except:
                            saldo = 0
                    elif not isinstance(saldo, (int, float)):
                        saldo = 0

                    total_valor += valor
                    total_saldo += saldo

                def convert_decimals(obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

                formatted = json.dumps(result_list, ensure_ascii=False, indent=2, default=convert_decimals)

                return append_period_context(append_scope_notice(f"""Resultados da consulta IA_ContasAReceber para o contrato {contrato}:

Total de títulos: {len(result_list)}
Valor total a receber: R$ {total_valor:,.2f}
Saldo total pendente: R$ {total_saldo:,.2f}

Dados completos dos títulos:
{formatted}

IMPORTANTE:
1. Estas são contas PENDENTES (a receber no futuro)
2. Cada linha representa um título individual do contrato
3. valor = valor total do título
4. saldo = saldo pendente a receber
5. Total geral: R$ {total_valor:,.2f}""", aviso_escopo), contexto_periodo)

            # Se NÃO solicitou contrato específico, agrega por cliente para garantir valores corretos
            from collections import defaultdict
            por_cliente = defaultdict(lambda: {
                "valor_total": 0,
                "saldo_total": 0,
                "quantidade": 0,
                "contratos": set(),
                "vencimentos": []
            })

            total_valor = 0
            total_saldo = 0

            for r in result_list:
                cliente_nome = r.get("cliente", "").strip() or "SEM CLIENTE"
                valor = r.get("valor", 0)
                saldo = r.get("saldo", 0)

                # Converte valores
                if valor is None:
                    valor = 0
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                if saldo is None:
                    saldo = 0
                elif isinstance(saldo, Decimal):
                    saldo = float(saldo)
                elif isinstance(saldo, str):
                    try:
                        saldo = float(saldo)
                    except:
                        saldo = 0
                elif not isinstance(saldo, (int, float)):
                    saldo = 0

                por_cliente[cliente_nome]["valor_total"] += valor
                por_cliente[cliente_nome]["saldo_total"] += saldo
                por_cliente[cliente_nome]["quantidade"] += 1

                contrato = r.get("contrato", "").strip()
                if contrato:
                    por_cliente[cliente_nome]["contratos"].add(contrato)

                vencimento = r.get("vencimentoReal", "").strip()
                if vencimento:
                    por_cliente[cliente_nome]["vencimentos"].append(vencimento)

                total_valor += valor
                total_saldo += saldo

            # Ordena por valor e limita aos top 50
            clientes_list = []
            clientes_ordenados = sorted(por_cliente.items(), key=lambda x: abs(x[1]["valor_total"]), reverse=True)

            # Se poucos clientes (≤ 10), mostra detalhes completos incluindo contratos
            if len(por_cliente) <= 10:
                for cliente_nome, dados in clientes_ordenados:
                    vencimentos_unicos = sorted(set(dados["vencimentos"]))[:3]
                    contratos_lista = sorted(list(dados["contratos"]))[:10]
                    clientes_list.append({
                        "cliente": cliente_nome,
                        "valor_total": round(dados["valor_total"], 2),
                        "saldo_total": round(dados["saldo_total"], 2),
                        "quantidade_titulos": dados["quantidade"],
                        "contratos": contratos_lista,
                        "proximos_vencimentos": vencimentos_unicos
                    })
            else:
                # Se muitos clientes (> 10), mostra apenas top 50 sem lista de contratos
                for cliente_nome, dados in clientes_ordenados[:50]:
                    vencimentos_unicos = sorted(set(dados["vencimentos"]))[:3]
                    clientes_list.append({
                        "cliente": cliente_nome,
                        "valor_total": round(dados["valor_total"], 2),
                        "saldo_total": round(dados["saldo_total"], 2),
                        "quantidade_titulos": dados["quantidade"],
                        "numero_contratos": len(dados["contratos"]),
                        "proximos_vencimentos": vencimentos_unicos
                    })

            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            formatted = json.dumps(clientes_list, ensure_ascii=False, indent=2, default=convert_decimals)

            # Detecta se é query sobre vencidas para contextualizar corretamente
            _q = (self.user_query_original or "").lower()
            _eh_vencidas = bool(re.search(r'\bvencid[oa]s?\b', _q))
            _tipo_label = "VENCIDAS (vencimentoReal já passou)" if _eh_vencidas else "PENDENTES (a receber)"
            _aviso_vencidas = "\n⚠️ ATENÇÃO: Estes títulos estão VENCIDOS — o vencimentoReal já passou. Informe ao usuário quais clientes têm contas em atraso." if _eh_vencidas else ""

            if _eh_vencidas and re.search(r'\b(total|quanto|valor)\b', _q):
                total_vencido_positivo = sum(
                    dados["saldo_total"]
                    for dados in por_cliente.values()
                    if dados["saldo_total"] > 0
                )
                clientes_por_saldo = sorted(
                    (
                        (cliente_nome, dados)
                        for cliente_nome, dados in por_cliente.items()
                        if dados["saldo_total"] > 0
                    ),
                    key=lambda item: item[1]["saldo_total"],
                    reverse=True,
                )
                pede_clientes = bool(re.search(r'\b(cliente|clientes|por cliente|quais|quem)\b', _q))
                clientes_texto = ""
                if pede_clientes:
                    linhas_clientes = [
                        f"- {cliente_nome}: R$ {format_pt_br(dados['saldo_total'])}"
                        for cliente_nome, dados in clientes_por_saldo
                    ]
                    if linhas_clientes:
                        clientes_texto = "\n\nClientes em atraso:\n" + "\n".join(linhas_clientes)

                return append_period_context(append_scope_notice((
                    f"O total de contas a receber vencidas: "
                    f"R$ {format_pt_br(total_vencido_positivo)}."
                    f"{clientes_texto}"
                ), aviso_escopo or CURRENT_OPEN_PAST_NOTICE), contexto_periodo)

            return append_period_context(append_scope_notice(f"""Resultados da consulta IA_ContasAReceber (AGREGADOS POR CLIENTE):{_aviso_vencidas}

Total de registros SQL: {len(result_list)}
Total de clientes únicos: {len(por_cliente)}
Valor total a receber: R$ {total_valor:,.2f}
Saldo total pendente: R$ {total_saldo:,.2f}

Clientes (ordenados por valor):
{formatted}

IMPORTANTE:
1. Estas são contas {_tipo_label}
2. Os valores já estão AGREGADOS por cliente (se cliente tem múltiplos títulos, valores foram somados)
3. valor_total = soma de todos os títulos daquele cliente
4. Total geral: R$ {total_valor:,.2f}""", aviso_escopo), contexto_periodo)

        except Exception as e:
            import traceback
            logger.error(f"Erro ao executar IA_ContasAReceber: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."

    def _pesquisa_despesa_venda(self, contrato: Optional[str] = None) -> str:
        """
        Consulta despesas de venda.

        Pode consultar:
        - Despesas de um contrato específico
        - Despesas de todos os contratos (agregadas por tipo)

        Args:
            contrato: Número do contrato (opcional). Se não informado, retorna todas as despesas agregadas.

        Returns:
            Lista de despesas ou agregação por tipo
        """
        logger.info(f"[DESPESA VENDA] Consultando despesas - contrato: {contrato}")

        # Se contrato foi especificado, busca despesas daquele contrato
        if contrato:
            filters = {"contrato": contrato}
            return self._validate_and_execute("IA_DespesaVenda", filters)

        # Sem contrato especificado = busca todas as despesas e agrega
        logger.info(f"[DESPESA VENDA] Buscando todas as despesas para agregação")

        # Busca todas as despesas (sem filtro de contrato)
        result_list = sql_client.execute_function("dbo.IA_DespesaVenda", filters=None)
        self._salvar_resultado_scheduler(result_list)

        if not result_list:
            return "Nenhuma despesa de venda encontrada."

        logger.info(f"[DESPESA VENDA] Total de registros: {len(result_list)}")

        # Verifica se usuário perguntou sobre tipo específico de despesa
        if self.user_query:
            # Pega apenas a última pergunta (caso tenha contexto de múltiplas perguntas)
            perguntas = self.user_query.split('?')
            ultima_pergunta = perguntas[-2] if len(perguntas) > 1 else self.user_query
            query_lower = ultima_pergunta.lower()

            # Detecta tipo de despesa na pergunta
            tipo_despesa = None
            if re.search(r'desemba(ra|ça|raco|raço)', query_lower):
                tipo_despesa = "DESEMBARACO"
            elif re.search(r'fumiga(ção|cao)', query_lower):
                tipo_despesa = "FUMIGACAO"
            elif re.search(r'(taxa|laudo|certificado)', query_lower):
                tipo_despesa = "TAXA"

            # Se tipo específico foi detectado, filtra e soma
            if tipo_despesa:
                despesas_filtradas = []
                total_reais = 0
                total_dolar = 0

                for r in result_list:
                    despesa_nome = r.get("despesa", "").upper()
                    if tipo_despesa in despesa_nome:
                        despesas_filtradas.append(r)
                        total_reais += float(r.get("despesaRea", 0) or 0)
                        total_dolar += float(r.get("despesaDolar", 0) or 0)

                if despesas_filtradas:
                    result = f"Total gasto com {tipo_despesa.lower()}: R$ {total_reais:,.2f}"
                    if total_dolar > 0:
                        result += f" + US$ {total_dolar:,.2f}"
                    result += f"\n\nEncontradas {len(despesas_filtradas)} despesas em {len(set(r.get('contrato') for r in despesas_filtradas))} contratos."

                    logger.info(f"[DESPESA VENDA] Tipo {tipo_despesa}: {len(despesas_filtradas)} despesas, R$ {total_reais:,.2f}")
                    return result
                else:
                    return f"Nenhuma despesa de {tipo_despesa.lower()} encontrada."

        # Sem tipo específico = retorna agregação por tipo de despesa
        from collections import defaultdict
        por_tipo = defaultdict(lambda: {"reais": 0, "dolar": 0, "quantidade": 0, "contratos": set()})

        for r in result_list:
            tipo = r.get("despesa", "").strip() or "SEM DESCRIÇÃO"
            por_tipo[tipo]["reais"] += float(r.get("despesaRea", 0) or 0)
            por_tipo[tipo]["dolar"] += float(r.get("despesaDolar", 0) or 0)
            por_tipo[tipo]["quantidade"] += 1
            por_tipo[tipo]["contratos"].add(r.get("contrato"))

        # Ordena por valor (maior primeiro)
        tipos_ordenados = sorted(por_tipo.items(), key=lambda x: x[1]["reais"], reverse=True)

        despesas_list = []
        for tipo, totais in tipos_ordenados[:20]:  # Top 20
            despesas_list.append({
                "tipo_despesa": tipo,
                "total_reais": round(totais["reais"], 2),
                "total_dolar": round(totais["dolar"], 2),
                "quantidade": totais["quantidade"],
                "numero_contratos": len(totais["contratos"])
            })

        logger.info(f"[DESPESA VENDA] Retornando {len(despesas_list)} tipos de despesa agregados")
        return despesas_list

    def _pesquisa_despesa_venda_par(self, contrato: str, letra: Optional[str] = None) -> str:
        """
        Consulta despesas de venda de um contrato específico via IA_DespesaVendaPar.

        Args:
            contrato: Número do contrato (obrigatório). Ex: "235/25", "400/25A"
            letra: Letra/parcela do contrato (opcional). Ex: "A", "B"

        Returns:
            Lista de despesas do contrato ou mensagem de erro
        """
        logger.info(f"[DESPESA VENDA PAR] Consultando despesas - contrato: {contrato}, letra: {letra}")

        filters = {"numContrato": contrato}
        if letra:
            filters["numLetra"] = letra

        return self._validate_and_execute("IA_DespesaVendaPar", filters)

    def _pesquisa_cotacao(
        self,
        data: Optional[str] = None,
        tipo: Optional[str] = None,
        ativo: Optional[str] = None,
    ) -> str:
        """
        Consulta cotação via IA_Cotacao_Par.

        Args:
            data: Data no formato YYYYMMDD ou qualquer formato legível. Padrão: hoje.
            tipo: Filtro pelo tipo (ex: "Dolar", "Euro", "Café"). Opcional.
            ativo: Filtro pelo ativo/instrumento (ex: "DOLM26", "KCK6"). Opcional.

        Returns:
            Lista de cotações ou mensagem de erro.
        """
        from datetime import date as _date

        # Resolve data
        if data:
            # Tenta converter de formatos comuns (DD/MM/YYYY, YYYY-MM-DD, etc.)
            data_fmt = None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d", "%d-%m-%Y"):
                try:
                    from datetime import datetime as _dt
                    data_fmt = _dt.strptime(data.strip(), fmt).strftime("%Y%m%d")
                    break
                except ValueError:
                    continue
            if not data_fmt:
                data_fmt = data.strip()  # Passa como veio, assume YYYYMMDD
        else:
            data_fmt = _date.today().strftime("%Y%m%d")

        logger.info(f"[COTACAO] Consultando IA_Cotacao_Par('{data_fmt}') tipo={tipo} ativo={ativo}")

        try:
            result_list = sql_client.execute_function(
                "dbo.IA_Cotacao_Par",
                filters={"data": data_fmt},
            )
            self._salvar_resultado_scheduler(result_list)

            if not result_list:
                return f"Nenhuma cotação encontrada para a data {data_fmt}. Deseja que eu busque na internet?"

            # Filtra por tipo
            if tipo:
                tipo_lower = tipo.lower()
                filtrado = [r for r in result_list if tipo_lower in str(r.get("tipo", "")).lower()]
                if filtrado:
                    result_list = filtrado

            # Filtra por ativo
            if ativo:
                ativo_upper = ativo.upper()
                filtrado = [r for r in result_list if ativo_upper in str(r.get("ativo", "")).upper()]
                if filtrado:
                    result_list = filtrado

            logger.info(f"[COTACAO] Retornando {len(result_list)} registro(s)")
            return result_list

        except Exception as e:
            logger.error(f"[COTACAO] Erro ao consultar cotação: {e}")
            return f"Erro ao consultar cotação: {e}"

    def _criar_relatorio_agendado(
        self,
        descricao: str,
        frequencia: str,
        horario: str = "08:00",
        dia_semana: Optional[str] = None,
        dia_mes: Optional[int] = None,
        canal: str = "whatsapp",
    ) -> str:
        """
        Cria um relatório automático agendado no Supabase.

        Args:
            descricao: O que o relatório deve conter
            frequencia: 'diario', 'semanal' ou 'mensal'
            horario: Horário de envio HH:MM
            dia_semana: Dia da semana em português (para semanal)
            dia_mes: Número do dia do mês (para mensal)
            canal: Canal de envio — 'whatsapp', 'email' ou 'ambos'

        Returns:
            Mensagem de confirmação
        """
        from app.core.supabase_client import supabase_client
        from app.services.scheduler import calcular_next_run, DIAS_SEMANA

        try:
            # Valida frequência
            frequencia = frequencia.lower().strip()
            if frequencia not in ("diario", "dias_uteis", "semanal", "mensal", "unico"):
                return "Frequência inválida. Use: 'diario', 'dias_uteis', 'semanal', 'mensal' ou 'unico'."

            # Valida canal
            canal = canal.lower().strip()
            if canal not in ("whatsapp", "email", "ambos"):
                canal = "whatsapp"

            # Usa sempre o email do usuário autenticado
            email_destino = self.user.email or None
            if canal in ("email", "ambos") and not email_destino:
                return "Não encontrei email cadastrado para o seu usuário. Entre em contato com o suporte."

            # Valida horário
            if ":" not in horario:
                horario = f"{horario}:00"

            # Converte dia_semana texto → número
            dia_semana_num = None
            if frequencia == "semanal":
                if not dia_semana:
                    return "Para relatórios semanais, informe o dia da semana (ex: 'segunda', 'sexta')."
                dia_semana_lower = dia_semana.lower().strip()
                dia_semana_num = DIAS_SEMANA.get(dia_semana_lower)
                if dia_semana_num is None:
                    return f"Dia da semana inválido: '{dia_semana}'. Use: segunda, terça, quarta, quinta, sexta, sábado, domingo."

            if frequencia == "mensal" and not dia_mes:
                return "Para relatórios mensais, informe o dia do mês (ex: 1, 15, 30)."

            # Para frequência única, não precisa de dia_semana nem dia_mes
            if frequencia == "unico":
                dia_semana_num = None
                dia_mes = None

            # Calcula next_run
            next_run = calcular_next_run(
                frequencia=frequencia,
                horario=horario,
                dia_semana=dia_semana_num,
                dia_mes=dia_mes,
            )

            dados = {
                "telefone": self.user.telefone,
                "descricao": descricao,
                "frequencia": frequencia,
                "horario": horario,
                "dia_semana": dia_semana_num,
                "dia_mes": dia_mes,
                "canal": canal,
                "email_destino": email_destino,
                "next_run": next_run.isoformat(),
                "status": "ativo",
            }

            resultado = self._run_coroutine(supabase_client.criar_relatorio_agendado(dados))

            if resultado:
                freq_texto = {
                    "diario": "todos os dias corridos (incluindo sábado e domingo)",
                    "dias_uteis": "de segunda a sexta-feira",
                    "semanal": f"toda {dia_semana}",
                    "mensal": f"todo dia {dia_mes} do mês",
                    "unico": "uma única vez",
                }.get(frequencia, frequencia)

                canal_texto = {
                    "whatsapp": "WhatsApp",
                    "email": f"email ({email_destino})",
                    "ambos": f"WhatsApp e email ({email_destino})",
                }.get(canal, canal)

                return (
                    f"✅ Relatório agendado com sucesso!\n"
                    f"📋 *{descricao}*\n"
                    f"🗓️ Frequência: {freq_texto} às {horario}\n"
                    f"📤 Canal: {canal_texto}\n"
                    f"📅 Primeira entrega: {next_run.strftime('%d/%m/%Y às %H:%M')}\n\n"
                    f"Para cancelar, diga: 'cancela meus relatórios agendados'."
                )
            return "Não foi possível criar o agendamento. Tente novamente."

        except Exception as e:
            logger.error(f"[AGENDAMENTO] Erro ao criar relatório agendado: {e}")
            return f"Erro ao criar agendamento: {e}"

    def _listar_relatorios_agendados(self) -> str:
        """
        Lista os relatórios agendados ativos do usuário.

        Returns:
            Lista formatada dos relatórios agendados
        """
        from app.core.supabase_client import supabase_client

        try:
            relatorios = self._run_coroutine(
                supabase_client.listar_relatorios_agendados(self.user.telefone)
            )

            if not relatorios:
                return "Você não tem relatórios automáticos agendados no momento."

            DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

            linhas = ["📋 *Seus relatórios automáticos agendados:*\n"]
            for i, r in enumerate(relatorios, 1):
                freq = r.get("frequencia", "")
                horario = r.get("horario", "")
                dia_semana = r.get("dia_semana")
                dia_mes = r.get("dia_mes")
                next_run = r.get("next_run", "")

                if freq == "diario":
                    freq_texto = f"Todos os dias corridos às {horario}"
                elif freq == "dias_uteis":
                    freq_texto = f"De segunda a sexta-feira às {horario}"
                elif freq == "semanal" and dia_semana is not None:
                    freq_texto = f"Toda {DIAS[dia_semana]} às {horario}"
                elif freq == "mensal" and dia_mes:
                    freq_texto = f"Todo dia {dia_mes} às {horario}"
                else:
                    freq_texto = freq

                try:
                    from datetime import datetime
                    import pytz
                    dt = datetime.fromisoformat(next_run).astimezone(pytz.timezone("America/Sao_Paulo"))
                    proxima = dt.strftime("%d/%m/%Y às %H:%M")
                except Exception:
                    proxima = next_run

                linhas.append(
                    f"{i}. *{r.get('descricao', '')}*\n"
                    f"   🗓️ {freq_texto}\n"
                    f"   📅 Próximo envio: {proxima}\n"
                    f"   🔑 ID: `{r.get('id', '')}`"
                )

            return "\n\n".join(linhas)

        except Exception as e:
            logger.error(f"[AGENDAMENTO] Erro ao listar relatórios: {e}")
            return f"Erro ao listar agendamentos: {e}"

    def _cancelar_relatorio_agendado(self, relatorio_id: str) -> str:
        """
        Cancela um relatório agendado pelo ID.

        Args:
            relatorio_id: ID do relatório a cancelar

        Returns:
            Mensagem de confirmação
        """
        from app.core.supabase_client import supabase_client

        try:
            sucesso = self._run_coroutine(
                supabase_client.cancelar_relatorio_agendado(relatorio_id, self.user.telefone)
            )

            if sucesso:
                return "✅ Relatório automático cancelado com sucesso. Você não receberá mais esse envio."
            return "Não encontrei esse relatório agendado. Use 'listar relatórios agendados' para ver os IDs corretos."

        except Exception as e:
            logger.error(f"[AGENDAMENTO] Erro ao cancelar relatório {relatorio_id}: {e}")
            return f"Erro ao cancelar agendamento: {e}"

    def _cancelar_todos_relatorios_agendados(
        self,
        manter_descricao: Optional[str] = None,
    ) -> str:
        """Cancela todos os relatórios, opcionalmente preservando uma descrição."""
        from app.core.supabase_client import supabase_client

        try:
            relatorios = self._run_coroutine(
                supabase_client.listar_relatorios_agendados(self.user.telefone)
            )

            if not relatorios:
                return "Você não tem relatórios agendados ativos."

            manter_normalizado = self._remove_accents(
                str(manter_descricao or "").lower()
            ).strip()
            cancelados = 0
            mantidos = []
            for r in relatorios:
                descricao = str(r.get("descricao") or "").strip()
                descricao_normalizada = self._remove_accents(descricao.lower())
                if manter_normalizado and (
                    manter_normalizado in descricao_normalizada
                    or descricao_normalizada in manter_normalizado
                ):
                    mantidos.append(descricao)
                    continue
                sucesso = self._run_coroutine(
                    supabase_client.cancelar_relatorio_agendado(r["id"], self.user.telefone)
                )
                if sucesso:
                    cancelados += 1

            if mantidos:
                return (
                    f"✅ {cancelados} relatório(s) cancelado(s) com sucesso. "
                    f"Mantido(s): {', '.join(mantidos)}."
                )
            return f"✅ {cancelados} relatório(s) cancelado(s) com sucesso. Você não receberá mais envios automáticos."

        except Exception as e:
            logger.error(f"[AGENDAMENTO] Erro ao cancelar todos os relatórios: {e}")
            return f"Erro ao cancelar agendamentos: {e}"

    def _pesquisa_internet(self, query: str) -> str:
        """Pesquisa informações na internet usando Tavily."""
        try:
            from tavily import TavilyClient
            from app.core.config import settings

            if not settings.tavily_api_key:
                return "❌ Busca na internet não configurada. Chave Tavily ausente."

            logger.info(f"[INTERNET] Pesquisando: {query}")

            client = TavilyClient(api_key=settings.tavily_api_key)
            resposta = client.search(query, max_results=5, search_depth="basic")
            resultados = resposta.get("results", [])

            if not resultados:
                return f"Nenhum resultado encontrado para: {query}"

            linhas = [f"🌐 *Resultados da internet para:* {query}\n"]
            for i, r in enumerate(resultados, 1):
                titulo = r.get("title", "")
                conteudo = r.get("content", "")
                url = r.get("url", "")
                linhas.append(f"{i}. *{titulo}*")
                if conteudo:
                    linhas.append(f"   {conteudo[:350]}{'...' if len(conteudo) > 350 else ''}")
                if url:
                    linhas.append(f"   Fonte: {url}")
                linhas.append("")

            return "\n".join(linhas)

        except ImportError:
            return "❌ Busca na internet não disponível. Pacote tavily-python não instalado."
        except Exception as e:
            logger.error(f"[INTERNET] Erro na pesquisa: {e}")
            return f"Erro ao pesquisar na internet: {e}"

    def get_all_tools(self) -> list:
        """Retorna lista de todas as tools"""
        tools_list = [
            StructuredTool.from_function(
                func=self._pesquisa_vendas,
                name="pesquisa_vendas",
                description="""⚠️ APENAS PARA CONSULTAR VENDAS EXISTENTES - NÃO CRIA CONTRATOS! ⚠️

Para CRIAR/REGISTRAR novos contratos, use: criar_contrato_venda_exportacao
Para CONSULTAR dados de vendas existentes, use: pesquisa_vendas (esta ferramenta)

Consulta dados de CONTRATOS DE VENDA (vendas e embarques da empresa).

Argumentos específicos:
- data_emissao (opcional): data ou período em que a venda foi inserida, digitada,
  lançada, cadastrada ou emitida. É convertida para @EmisIni e @EmisFim no
  formato YYYYMMDD. Para "esta semana", considera domingo a sábado.
- contrato (opcional): número exato do contrato. Quando informado, é enviado à
  usp_IA_Vendas como @Contrato (ex.: contrato="032/26A").
- mes_fixacao (opcional): índice ou mês de fixação. Aceita H/K/N/U/Z com dois
  dígitos de ano e meses por extenso ou numéricos (ex.: U26, K27, julho/26,
  09/2026). É enviado como @MesFixIni e @MesFixFim.

SÉRIES MENSAIS:
- Faça exatamente UMA chamada para todo o intervalo solicitado.
- Nunca faça uma chamada separada para cada mês.
- Exemplo: "vendas mês a mês do segundo semestre de 2026" deve chamar
  pesquisa_vendas(periodo="segundo semestre de 2026") uma única vez.
- O código separará os resultados por mesEmbarque e declarará meses ausentes.

MESES/ÍNDICES DE FIXAÇÃO:
- H = março
- K = maio
- N = julho
- U = setembro
- Z = dezembro
- K27 → @MesFixIni='2027/05', @MesFixFim='2027/05'
- N26 → @MesFixIni='2026/07', @MesFixFim='2026/07'
- "Quais contratos não fixados temos contra bolsa U26?" → pesquisa_vendas(mes_fixacao="U26")
- Nunca trate esses índices como mês de embarque.

REGRA DE EMISSÃO/INCLUSÃO:
- Contratos inseridos, digitados, lançados, cadastrados ou emitidos em uma data
  usam data_emissao, nunca o período de embarque.
- "Quantas sacas de vendas foram vendidas hoje?" → pesquisa_vendas(data_emissao="hoje")
- "Quais contratos de exportação foram inseridos essa semana?" →
  pesquisa_vendas(data_emissao="essa semana")
- Sem filial específica, resumir por filial: 05=COBRA, 60=CUSA e 61=CEU.

REGRA DE FIXAÇÃO:
- Para saber se o contrato foi fixado, use somente valorFixado.
- valorFixado nulo ou igual a zero = não fixado.
- valorFixado acima de zero = já fixado.
- Nunca use precoFix para determinar o status de fixação.

🔄 REGRA DE CONTEXTO DE CONTRATO (NOVA!) 🔄
Se o usuário já mencionou um número de contrato anteriormente (ex: "228/25", "031/25") e agora faz perguntas de seguimento sem mencionar o contrato novamente (ex: "Qual o total de sacas?", "Qual o vendedor?", "Preciso dos dados completos"), você DEVE entender que ele está se referindo ao mesmo contrato.

IMPORTANTE: Use esta ferramenta SEM PASSAR PERIODO para consultas sobre o contrato específico já mencionado.
O sistema detectará automaticamente o contexto e aplicará o filtro pelo contrato.

Exemplos de perguntas de seguimento sobre contrato:
- Usuário: "Quem é o vendedor do contrato 228/25?" → pesquisa_vendas()
- Usuário: "Preciso do total e da quantidade de sacas" → pesquisa_vendas() (usa 228/25 automaticamente)
- Usuário: "Qual o cliente?" → pesquisa_vendas() (usa 228/25 automaticamente)
- Usuário: "Qual a qualidade?" → pesquisa_vendas() (usa 228/25 automaticamente)

⚠️⚠️⚠️ REGRA ABSOLUTA DE SELEÇÃO ⚠️⚠️⚠️
SEMPRE USE ESTA FERRAMENTA (pesquisa_vendas) QUANDO A PERGUNTA CONTÉM A PALAVRA "CONTRATOS"
Isso inclui queries como:
- "contratos baixados no contas a receber" → use ESTA ferramenta (pesquisa_vendas), NÃO use pesquisa_contas_a_receber
- "contratos de janeiro 2026" → use ESTA ferramenta
- "contratos que foram baixados" → use ESTA ferramenta
- Qualquer pergunta com a palavra "contrato" ou "contratos" → use ESTA ferramenta

IMPORTANTE - Use esta ferramenta quando o usuário perguntar sobre:
- "contratos" (contratos de venda de café)
- "vendas"
- "embarques"
- "contratos baixados" ou "contratos que foram baixados" (refere-se a contratos de venda quitados financeiramente, campo baixaReceber)
- campos como: sacas, clientes, diferencial, certificados, BL, peneiras, qualidade do café

⚠️⚠️⚠️ REGRA CRÍTICA PARA FILTRO DE PERÍODO ⚠️⚠️⚠️

⚠️ ATENÇÃO MÁXIMA - NÃO CONFUNDA MÊS DE EMBARQUE COM MÊS DE BAIXA! ⚠️

Quando o usuário diz "contratos EM [mês/ano]", pode significar DUAS COISAS:

1️⃣ Contratos COM EMBARQUE em [mês/ano] → PASSE periodo
2️⃣ Contratos QUE FORAM BAIXADOS/PAGOS em [mês/ano] → NÃO passe periodo

CASO 1 - NÃO PASSE PERIODO (deixe None ou omita):
→ APENAS quando a pergunta é sobre "BAIXADOS/PAGOS EM [MÊS/ANO]"
→ Palavras-chave: "baixados em", "foram baixados", "pagos em", "quitados em"
→ Exemplos:
  • "contratos baixados EM janeiro 2026" → pesquisa_vendas() SEM periodo
  • "contratos baixados no contas a receber EM janeiro 2026" → pesquisa_vendas() SEM periodo
  • "quais contratos foram baixados EM dezembro 2025" → pesquisa_vendas() SEM periodo
  • "contratos do FREY em novembro 2025 já foram baixados?" → pesquisa_vendas() SEM periodo
→ Razão: A agregação retorna campos específicos (contratos_baixados_jan2026, contratos_baixados_nov2025, etc.)
→ IMPORTANTE: Estes campos mostram quando o contrato foi PAGO, não quando embarcou!

CASO 2 - SEMPRE PASSE periodo='[mês] [ano]':
→ Para TODAS as outras perguntas que mencionam "EM [MÊS/ANO]", incluindo:
  ✓ "vendas EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "valor total EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "contratos do cliente X EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "sacas EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "contratos COM EMBARQUE em janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "embarques de fevereiro 2026" → pesquisa_vendas(periodo='fevereiro 2026')
→ Razão: Precisa filtrar a query SQL por mesEmbarque para retornar apenas o período solicitado

⚠️ RESUMO CRÍTICO:
- Se tem "baixados/pagos/quitados EM" → NÃO passe periodo (use campos contratos_baixados_*)
- Se NÃO tem essas palavras e menciona mês → PASSE periodo (filtra por mesEmbarque)

ARGUMENTOS PARA A STORED PROCEDURE:
- periodo (opcional): mês ou intervalo de embarque. O sistema converte para MesIni e MesFim no formato YYYY/MM.
- cliente (opcional): nome do cliente enviado para a stored procedure.
- limite (opcional): quantidade desejada quando a consulta for somente por cliente.
  - Sem período e sem limite informado, retorna os 10 primeiros registros.
  - Use limite=0 quando o usuário pedir todos os registros.

Exemplos:
- "Quais contratos de venda temos para esse mês?" → pesquisa_vendas(periodo="este mês")
- "Quais os últimos contratos para o cliente NESTRADE?" → pesquisa_vendas(cliente="NESTRADE")
- "Mostre os últimos 20 contratos para o cliente NESTRADE" → pesquisa_vendas(cliente="NESTRADE", limite=20)
- "Temos algum contrato para o MIORI esse ano?" → pesquisa_vendas(periodo="este ano", cliente="MIORI")
- "Temos algum contrato em janeiro/2025?" → pesquisa_vendas(periodo="janeiro/2025")
- "Quantos contratos temos para o MIORI nos últimos três meses?" → pesquisa_vendas(periodo="últimos três meses", cliente="MIORI")

Exemplos de periodo: 'este mês', 'este ano', 'últimos três meses', 'dezembro 2025', 'janeiro/2026'"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_compras,
                name="pesquisa_compras",
                description="""Consulta dados de COMPRAS e AQUISIÇÕES de café.

Esta ferramenta retorna informações sobre pedidos e contratos de compra, incluindo:
- Número do pedido/contrato
- Fornecedor (produtor/cooperativa)
- Quantidade (sacas e peso)
- Preço e valor total
- Safra
- Linha/qualidade: em compras, "qualidade" corresponde exatamente ao campo linha retornado pela procedure
- Diferencial
- Data de emissão e entrega
- Sacas entregues vs a entregar

REGRA CRÍTICA SOBRE LINHA/QUALIDADE:
- Sempre leia o conteúdo do campo linha retornado pela procedure.
- Linha não significa a posição ordinal do resultado. Um único registro não é "linha 1" nem "linha 01".
- Em pedidos "por qualidade em diferencial", agrupe pelo campo linha, calcule o diferencial médio ponderado pelas sacas e liste os pedidos que compõem cada média.

Argumentos:
- data_inicio (opcional): Data/período inicial (ex: "janeiro 2025", "2025", "05/12/2025", "últimos 7 dias")
- data_fim (opcional): Data/período final para range (ex: "outubro 2025", "dezembro 2025")
- fornecedor (opcional): Nome do fornecedor enviado para a stored procedure
- limite (opcional): Quantidade desejada quando a consulta for somente por fornecedor
  - Sem período e sem limite informado, retorna os 10 primeiros registros
  - Use limite=0 quando o usuário pedir todos os registros
  - Se NENHUM informado: retorna TODAS as compras
  - Se apenas data_inicio: filtra a partir daquela data
  - Se ambos: filtra o intervalo completo

⚠️ IMPORTANTE: NUNCA peça clarificação ao usuário — sempre chame esta ferramenta diretamente.
- "compras de 2025" → pesquisa_compras(data_inicio="2025") [retorna o ano inteiro]
- "todas as compras" → pesquisa_compras() [sem parâmetros]

Exemplos de uso:
- "Quais compras temos para esse mês?" → pesquisa_compras(data_inicio="este mês")
- "Quais os últimos contratos de compra para o fornecedor LIBRA?" → pesquisa_compras(fornecedor="LIBRA")
- "Mostre os últimos 20 contratos de compra para a LIBRA" → pesquisa_compras(fornecedor="LIBRA", limite=20)
- "Temos alguma compra para o LIBRA esse ano?" → pesquisa_compras(data_inicio="este ano", fornecedor="LIBRA")
- "Temos alguma compra em janeiro/2025?" → pesquisa_compras(data_inicio="janeiro/2025")
- "Quantas compras temos para a LIBRA nos últimos três meses?" → pesquisa_compras(data_inicio="últimos três meses", fornecedor="LIBRA")
- "Compras de 2025" → pesquisa_compras(data_inicio="2025")
- "Compras de janeiro a outubro de 2025" → pesquisa_compras(data_inicio="janeiro 2025", data_fim="outubro 2025")
- "Compras de dezembro de 2025" → pesquisa_compras(data_inicio="dezembro 2025")
- "Compras dos últimos 7 dias" → pesquisa_compras(data_inicio="últimos 7 dias")
- "Todas as compras" → pesquisa_compras()
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_contas_pagas,
                name="pesquisa_contas_pagas",
                description="""Consulta CONTAS JÁ PAGAS pela empresa (pagamentos financeiros efetuados).

Esta ferramenta retorna informações sobre pagamentos realizados, incluindo TODOS os campos:

📋 IDENTIFICAÇÃO:
- numero: Número do título/documento pago
- filial: Código da filial responsável
- fornecedor: Nome do fornecedor/beneficiário que recebeu o pagamento

💰 VALORES FINANCEIROS:
- valor: Valor principal pago (formato numérico)
- valorStr: Valor principal pago (formato string/texto)
- moeda: Tipo de moeda utilizada (BRL/USD/EUR)
- juros: Valor de juros pagos
- acrescimo: Valores adicionais/acréscimos
- decrescimo: Descontos/decréscimos aplicados

📅 DATAS:
- emissao: Data de emissão do título (formato: YYYYMMDD)
- vencimento: Data de vencimento original
- pagamento: Data efetiva do pagamento

🏦 CONTROLE FINANCEIRO:
- banco: Banco/conta utilizado para pagamento
- centroCusto: Centro de custo associado
- natureza: Natureza/tipo da despesa (ex: fornecedores, impostos, salários)

✅ APROVAÇÃO:
- aprovador: Primeiro aprovador do pagamento
- aprovador2: Segundo aprovador (quando aplicável)

⚠️ IMPORTANTE: Esta ferramenta é para PAGAMENTOS JÁ EFETUADOS (contas pagas).
Para contas pendentes/futuras, use pesquisa_contas_a_pagar.

Argumentos:
- data_inicio (opcional): Data ou período para filtro dos pagamentos
  - Formato flexível: "05/12/2025", "este mês", "últimos 30 dias", "janeiro/2025"
  - Se NÃO INFORMADO: retorna todas as contas pagas (sem filtro de data)
  - Se INFORMADO: envia o início e fim do período para a stored procedure
  - SEMPRE repasse a expressão temporal completa informada pelo usuário
  - Semana, mês/ano, ano, quinzena, trimestre e "últimos N meses" são convertidos em DataIni e DataFim
  - Regra de mês/ano: "janeiro/2025" ou "janeiro de 2025" envia DataIni=20250101 e DataFim=20251231

- fornecedor (opcional): Nome do fornecedor/beneficiário enviado para a stored procedure
  - Exemplos: "ATLAS", "JULIO CESAR", "Rodrigo"
  - Pode ser combinado com data_inicio
  - Se informado sem data, retorna os 10 primeiros registros por padrão

- limite (opcional): Quantidade de registros desejada em consultas somente por fornecedor
  - Use um número positivo quando o usuário pedir mais registros ou uma quantidade específica
  - Use limite=0 quando o usuário pedir todos os registros

Exemplos de uso:
- "Quais contas foram pagas este mês?" → pesquisa_contas_pagas(data_inicio="este mês")
- "Quanto pagamos para a ATLAS nesta semana?" → pesquisa_contas_pagas(data_inicio="esta semana", fornecedor="ATLAS")
- "Quais os últimos pagamentos para o JULIO CESAR?" → pesquisa_contas_pagas(fornecedor="JULIO CESAR")
- "Mostre os últimos 20 pagamentos para o JULIO CESAR" → pesquisa_contas_pagas(fornecedor="JULIO CESAR", limite=20)
- "Temos algo pago para o Rodrigo ontem?" → pesquisa_contas_pagas(data_inicio="ontem", fornecedor="Rodrigo")
- "Temos algo pago para o Rodrigo em janeiro/2025?" → pesquisa_contas_pagas(data_inicio="janeiro/2025", fornecedor="Rodrigo")
- "Quanto pagamos para a ATLAS nos últimos três meses?" → pesquisa_contas_pagas(data_inicio="últimos três meses", fornecedor="ATLAS")
- "Pagamentos da primeira quinzena de janeiro de 2025" → pesquisa_contas_pagas(data_inicio="primeira quinzena de janeiro de 2025")
- "Pagamentos desde 05/12/2025" → pesquisa_contas_pagas(data_inicio="05/12/2025")
- "Contas pagas no ano de 2025" → pesquisa_contas_pagas(data_inicio="2025")
- "Todas as contas pagas" → pesquisa_contas_pagas()
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_contas_a_receber_vencidas,
                name="pesquisa_contas_a_receber_vencidas",
                description="""Consulta exclusivamente CONTAS A RECEBER VENCIDAS/ATRASADAS.

REGRA PRIORITÁRIA: sempre use esta ferramenta quando a pergunta contiver, de forma conjunta, a intenção de "contas a receber" e "vencidas", "vencidos", "atrasadas" ou "em atraso". Também use para a expressão "contas a pagar vencidas", conforme a regra financeira específica deste sistema.

Exemplos:
- "Quais contas a receber estão vencidas?"
- "Temos contas a receber em atraso?"
- "Qual o total das contas a receber vencidas?"
- "Me diga todas as contas a receber em atraso"

A ferramenta aplica internamente e sem argumentos a data inicial 19990101, a data atual como final e tipo Receber. Ela soma o campo saldo separadamente para cada valor do campo moeda, incluindo valores negativos, que representam créditos do comprador. Nunca some moedas diferentes. Não passe datas e não use pesquisa_contas_a_receber para essas perguntas.

RESPOSTA E CONTINUIDADE:
- Na consulta geral, retorne TODOS os clientes fornecidos pela ferramenta, sem limitar aos maiores.
- Para cada cliente, informe exatamente: nome, saldo líquido por moeda e quantidade de contratos.
- Se o usuário continuar com "me diga os contratos do cliente X", "e do cliente X?" ou equivalente, preserve o contexto de contas vencidas e chame novamente esta ferramenta com cliente="X".
- Quando cliente for informado, a consulta adicionará WHERE cliente = 'X' e retornará TODOS os contratos desse cliente, com saldo por moeda e quantidade de títulos.
- Se o usuário pedir "contas negativas", "saldos negativos", "clientes com crédito" ou equivalente, chame com somente_negativas=true.
- Nesse caso a consulta adicionará saldo < 0 e os valores negativos devem permanecer negativos na soma.

Argumentos:
- cliente (opcional): nome exato do cliente citado pelo usuário em uma consulta ou pergunta de seguimento.
- somente_negativas (opcional): use true apenas para contas/saldos negativos ou créditos do comprador.

Exemplos de seguimento:
- Usuário: "Ok, me diga os contratos do cliente JDE" → pesquisa_contas_a_receber_vencidas(cliente="JDE")
- Usuário: "Agora mostre todas as contas negativas" → pesquisa_contas_a_receber_vencidas(somente_negativas=true)
- Usuário: "Quais clientes possuem crédito?" → pesquisa_contas_a_receber_vencidas(somente_negativas=true)
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_contas_a_pagar,
                name="pesquisa_contas_a_pagar",
                description="""Consulta CONTAS A PAGAR pela empresa (pagamentos pendentes/futuros).

Esta ferramenta retorna informações sobre contas pendentes de pagamento, incluindo TODOS os campos:

📋 IDENTIFICAÇÃO DO TÍTULO:
- tipo: Tipo do título (Realizado, etc.)
- filial: Código da filial responsável
- prefixo: Prefixo do título
- numero: Número do título/documento
- parcela: Parcela do título (se parcelado)
- pedido: Número do pedido relacionado
- loja: Código da loja do fornecedor

💰 VALORES FINANCEIROS:
- valor: Valor total a pagar (R$)
- rateio: Valor do rateio
- percrat: Percentual do rateio (%)

📅 DATAS:
- emissao: Data de emissão do título (formato: YYYYMMDD)
- vencimento: Data de vencimento (formato: YYYYMMDD)

🏦 CONTROLE FINANCEIRO:
- fornecedor: Nome do fornecedor/credor
- centroCusto: Centro de custo associado
- natureza: Natureza/tipo da despesa (ex: compra de café, fretes, despesas, etc.)

⚠️ IMPORTANTE: Esta ferramenta é somente para PAGAMENTOS PENDENTES/FUTUROS.
Ao consultar uma data passada, ela continua mostrando somente títulos que permanecem em aberto atualmente; não reconstrói a posição histórica daquele dia. Preserve obrigatoriamente o aviso de escopo retornado pela ferramenta e nunca conclua que eram os únicos títulos existentes naquela data.
Para contas vencidas, atrasadas ou em atraso, use obrigatoriamente pesquisa_contas_a_receber_vencidas.
Para pagamentos já efetuados, use pesquisa_contas_pagas.

Argumentos:
- data_vencimento (opcional): Data de vencimento para filtro
  - Formato flexível: "hoje", "próximos 7 dias", "este mês", "próxima semana", "20251212"
  - Preserve literalmente "dias úteis" ou "dias corridos" quando o usuário informar. O código calcula o intervalo e informa todos os dias sem registros.
  - Se NÃO INFORMADO: retorna todas as contas a pagar (sem filtro de data)
  - Se INFORMADO: filtra contas conforme período especificado
  - Use quando a pergunta menciona "vencimento", "pagar em", "vencer em"

- data_emissao (opcional): Data de emissão do título para filtro
  - Formato flexível: "06/02/2026", "este mês", "últimos 7 dias"
  - Filtra títulos pela data em que foram CRIADOS/EMITIDOS
  - Use quando a pergunta menciona "emissão", "emitido em", "criado em"
  - IMPORTANTE: Não pode ser usado junto com data_vencimento (escolha um)

- natureza (opcional): Filtro por natureza/tipo de despesa
  - Exemplos: "compra de café", "cafe", "INSS", "salário", "PLR", "tarifas bancárias"
  - O filtro é flexível: "cafe" encontra "COMPRA DE CAFE BENEFICIADO"
  - Se NÃO INFORMADO: retorna todas as naturezas
  - Se INFORMADO: filtra apenas contas com natureza correspondente

- fornecedor (opcional): Nome do fornecedor/credor enviado para a stored procedure
  - Exemplos: "ATLAS", "JULIO CESAR", "Rodrigo"
  - Pode ser combinado com data_vencimento
  - Se informado sem data, retorna os 10 primeiros registros por padrão

- limite (opcional): Quantidade de registros desejada em consultas somente por fornecedor
  - Use um número positivo quando o usuário pedir mais registros ou uma quantidade específica
  - Use limite=0 quando o usuário pedir todos os registros

Exemplos de uso:
- "Quais contas vou pagar hoje?" → pesquisa_contas_a_pagar(data_vencimento="hoje")
- "Contas a pagar vencidas" ou "Contas atrasadas" → NÃO use esta ferramenta; use pesquisa_contas_a_receber_vencidas()
- "Contas a pagar nos próximos 7 dias" → pesquisa_contas_a_pagar(data_vencimento="próximos 7 dias")
- "Quanto temos de contas a pagar para a ATLAS nesta semana?" → pesquisa_contas_a_pagar(data_vencimento="esta semana", fornecedor="ATLAS")
- "Quais os próximos pagamentos para o JULIO CESAR?" → pesquisa_contas_a_pagar(fornecedor="JULIO CESAR")
- "Mostre os próximos 20 pagamentos para o JULIO CESAR" → pesquisa_contas_a_pagar(fornecedor="JULIO CESAR", limite=20)
- "Temos algo para pagar para o Rodrigo amanhã?" → pesquisa_contas_a_pagar(data_vencimento="amanhã", fornecedor="Rodrigo")
- "Pagamentos deste mês" → pesquisa_contas_a_pagar(data_vencimento="este mês")
- "Todas as contas a pagar" → pesquisa_contas_a_pagar()
- "Contas com vencimento em 12/12/2025" → pesquisa_contas_a_pagar(data_vencimento="20251212")
- "Contas com emissão em 06/02/2026" → pesquisa_contas_a_pagar(data_emissao="06/02/2026")
- "Títulos emitidos este mês" → pesquisa_contas_a_pagar(data_emissao="este mês")
- "Quanto tenho a pagar de compra de café?" → pesquisa_contas_a_pagar(natureza="cafe")
- "Quanto devo de INSS?" → pesquisa_contas_a_pagar(natureza="INSS")
- "Pagamentos de salário nos próximos 7 dias" → pesquisa_contas_a_pagar(data_vencimento="próximos 7 dias", natureza="salario")
- "Contas vencidas de fumigação" → pesquisa_contas_a_receber_vencidas()
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_contas_a_receber,
                name="pesquisa_contas_a_receber",
                description="""Consulta CONTAS A RECEBER (títulos financeiros, recebimentos pendentes/futuros).

Esta ferramenta retorna informações sobre contas pendentes de recebimento, incluindo 27 campos:

📋 IDENTIFICAÇÃO:
- idProtheus: ID único do título
- tipo: Tipo do título (Receber, etc.)
- numero: Número do título/documento
- parcela: Parcela do título

💰 VALORES FINANCEIROS:
- valor: Valor total a receber (R$)
- saldo: Saldo pendente a receber (R$)

📅 DATAS:
- emissao: Data de emissão (YYYYMMDD)
- vencimentoReal: Data de vencimento real (YYYYMMDD)
- vencimentoOriginal: Data de vencimento original (YYYYMMDD)
- baixa: Data da baixa (YYYYMMDD)
- baixaPilha: Data da baixa em pilha (YYYYMMDD)

🏦 CONTROLE COMERCIAL:
- cliente: Nome do cliente/devedor
- contrato: Número do contrato relacionado
- banco: Banco onde será recebido
- consignee: Consignee/destinatário
- condicaoPagamento: Condição de pagamento

📦 EMBARQUE E DOCUMENTOS:
- mesEmbarque: Mês de embarque (MM/YYYY)
- embarqueReal: Data de embarque real (YYYYMMDD)
- previsaoEmbarque: Previsão de embarque (YYYYMMDD)
- embarqueEstimado: Embarque estimado (YYYYMMDD)
- recebimentoDoc: Recebimento de documentos (YYYYMMDD)
- envioDoc: Envio de documentos (YYYYMMDD)

🌍 OPERACIONAL:
- modalidade: Modalidade (INT, NAC, etc.)
- peso: Peso em kg
- sacas: Quantidade de sacas
- mesFixacao: Mês de fixação (MM/YYYY)
- diferencial: Diferencial de preço

⚠️ IMPORTANTE - QUANDO USAR ESTA FERRAMENTA:
- Ao consultar uma data passada, o resultado é a posição ATUAL dos títulos ainda abertos filtrada por aquela data, não o histórico completo. Preserve obrigatoriamente o aviso de escopo da ferramenta e não diga que os registros retornados eram os únicos existentes naquela data.
- Para contas a receber vencidas, atrasadas ou em atraso, NÃO use esta ferramenta; use pesquisa_contas_a_receber_vencidas().
- "Quanto temos a receber?" → USE ESTA FERRAMENTA
- "Quanto a NESTLE me deve?" → USE ESTA FERRAMENTA
⛔ NÃO USE para contratos de vendas ou embarques → use pesquisa_vendas

Argumentos:
- data_vencimento (opcional): Data de vencimento para filtro
  - Formato flexível: "hoje", "próximos 7 dias", "este mês", "20250112"
  - Preserve literalmente "dias úteis" ou "dias corridos" quando o usuário informar. O código calcula o intervalo e informa todos os dias sem registros.
  - Se NÃO INFORMADO sem "vencido": retorna todas as contas a receber

- cliente (opcional): Filtro por cliente
  - Exemplos: "NESTLE", "STARBUCKS", "UCC"
  - O filtro é flexível: "NESTLE" encontra "NESTLE ARARAS"

- contrato (opcional): Filtro por contrato específico
  - Exemplos: "256/25R", "031/25", "086/25B"
  - Quando INFORMADO: retorna DETALHES COMPLETOS dos títulos (sem agregar)

Exemplos de uso:
- "Há contas a receber vencidas?" → pesquisa_contas_a_receber_vencidas()
- "Algum contas a receber vencido?" → pesquisa_contas_a_receber_vencidas()
- "Contas a receber vencidas da NESTLE?" → pesquisa_contas_a_receber_vencidas()
- "Quanto tenho a receber hoje?" → pesquisa_contas_a_receber(data_vencimento="hoje")
- "Contas a receber nos próximos 7 dias" → pesquisa_contas_a_receber(data_vencimento="próximos 7 dias")
- "Recebimentos deste mês" → pesquisa_contas_a_receber(data_vencimento="este mês")
- "Quanto a NESTLE me deve?" → pesquisa_contas_a_receber(cliente="NESTLE")
- "Dados do contrato 256/25R no contas a receber" → pesquisa_contas_a_receber(contrato="256/25R")
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_saldo_bancario,
                name="pesquisa_saldo_bancario",
                description="""Consulta SALDO BANCÁRIO atual da empresa (snapshot do momento).

Esta ferramenta retorna informações sobre todas as contas bancárias, com 7 campos:

🏦 IDENTIFICAÇÃO:
- filial, banco, codigo (código do banco)
- agencia, conta

💰 SALDO:
- saldo: Saldo atual (R$) - pode ser NEGATIVO (saldo devedor)
- moeda: Reais, Dolares, Euros, Libras

Argumentos:
- banco (opcional): Filtro por banco (ex: "ITAU SANTOS", "BB", "BRADESCO")

IMPORTANTE:
- Saldo POSITIVO = dinheiro disponível
- Saldo NEGATIVO = saldo devedor (empréstimo do banco)
- Dados agregados por banco e moeda

⚠️ ATENÇÃO - USE para perguntas sobre CONTAS BANCÁRIAS e SALDOS FINANCEIROS:
- "Qual o saldo bancário?" → pesquisa_saldo_bancario()
- "Quanto tenho no banco?" → pesquisa_saldo_bancario()
- "Ativos em dólar / quanto temos em dólar?" → pesquisa_saldo_bancario()
- "Posição em moeda estrangeira (dólar, euro, libra)?" → pesquisa_saldo_bancario()
- "Saldo no Itaú Santos?" → pesquisa_saldo_bancario(banco="ITAU SANTOS")
- "Quanto tenho no BB?" → pesquisa_saldo_bancario(banco="BB")
- "Quanto temos disponível em dólar nos bancos?" → pesquisa_saldo_bancario()

❌ NÃO confundir com:
- Preço do café na bolsa → use pesquisa_cotacao
- Estoque físico de sacas → use pesquisa_estoque
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_estoque,
                name="pesquisa_estoque",
                description="""Consulta ESTOQUE FÍSICO de café (sacas armazenadas em armazéns/warehouses).

⚠️ ATENÇÃO - USE APENAS para perguntas sobre SACAS FÍSICAS DE CAFÉ em estoque:
- "Quanto café temos em estoque?"
- "Quantas sacas temos armazenadas?"
- "Qual o estoque de café?"
- "Temos café disponível no armazém?"
- "Posição de estoque físico"

❌ NÃO USE para:
- Cotações de preço (bolsa, NY, London) → use pesquisa_cotacao
- Saldo bancário ou ativos financeiros → use pesquisa_saldo_bancario
- Contratos de venda ou compra → use pesquisa_vendas ou pesquisa_compras

NÃO requer argumentos."""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_orcamento,
                name="pesquisa_orcamento",
                description="""Consulta orçamento vs realizado.

Argumentos:
- periodo (opcional): período desejado (ex: 'dezembro 2025', 'fevereiro 2026', '1TRIM 2026')
- filial (opcional): código ou nome da filial para filtrar (ex: 'Santos', '61')
- cc (opcional): código do centro de custo para filtrar (ex: 'TI', '0010', 'TECNOLOGIA')

Exemplos:
- "Qual o orçamento de fevereiro?" → pesquisa_orcamento(periodo="fevereiro 2026")
- "Orçamento da filial Santos em fevereiro?" → pesquisa_orcamento(periodo="fevereiro 2026", filial="Santos")
- "Orçamento do CC de TI?" → pesquisa_orcamento(cc="TI")
- "Orçamento de TI em fevereiro na filial Santos?" → pesquisa_orcamento(periodo="fevereiro 2026", filial="Santos", cc="TI")
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_longshort,
                name="pesquisa_longshort",
                description="""Consulta posição do Long/Short (LS) por filial.

🔍 DETECÇÃO AUTOMÁTICA DE FILIAL:
Esta ferramenta detecta automaticamente qual filial o usuário quer consultar:
- COBRA / "comexim brasil" / "brasil" → Filial COBRA
- CUSA / "comexim usa" / "usa" / "eua" → Filial CUSA
- CEU / "comexim europa" / "europa" → Filial CEU
- Sem especificação → FILIAIS (totalizador de todas as filiais)

📊 COLUNAS DISPONÍVEIS:
- netPosition: Posição líquida do LongShort
- totalEstoque: Total do estoque
- vendasExportacao: Total de vendas para exportação
- comprasConsumo: Total de compras de mercado interno/consumo

FORMATO OBRIGATÓRIO:
A ferramenta devolve sempre o quadro completo e pronto para envio, com Posição Net LS,
Estoque Total Exportação, Vendas Totais Exportação, Basis Saldo Sacas,
Vendas Mercado A fixar, Vendas Fixadas, Vendas A Fixar Embarcadas e Bolsa em lotes/sacas.
Reproduza integralmente os valores retornados; não omita linhas e não recalcule os indicadores.

📝 EXEMPLOS DE USO:
- "Qual a posição do LongShort?" → Retorna netPosition (FILIAIS)
- "Qual o total do estoque do longshort da CUSA?" → Retorna totalEstoque (CUSA)
- "Qual o total de vendas exportáveis da comexim europa?" → Retorna vendasExportacao (CEU)
- "Qual o total de compras de mercado interno?" → Retorna comprasConsumo (FILIAIS)

⚠️ NÃO requer argumentos - a filial é detectada automaticamente da pergunta do usuário."""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_despesa_venda,
                name="pesquisa_despesa_venda",
                description="""Consulta DESPESAS DE VENDA - pode consultar um contrato específico ou todas as despesas agregadas.

Esta ferramenta retorna despesas associadas a contratos de venda, incluindo:
- Desembaraço aduaneiro
- Taxas de laudo e certificados
- Despesas com fumigação
- Outras despesas operacionais

MODO 1 - Contrato específico (se número informado):
Para cada despesa do contrato, retorna:
- Tipo/descrição da despesa
- Fornecedor
- Valor em reais (despesaRea)
- Valor em dólar (despesaDolar)
- Quantidade
- Observações

MODO 2 - Agregação por tipo (se número NÃO informado):
Retorna todas as despesas agregadas por tipo, com:
- Tipo de despesa
- Total em reais
- Total em dólar
- Quantidade de ocorrências
- Número de contratos

⚠️ DETECÇÃO AUTOMÁTICA DE TIPO:
Se o usuário perguntar sobre tipo específico sem informar contrato:
- "Quanto gastei com desembaraço?" → Soma TODAS as despesas de desembaraço
- "Quanto gastei com fumigação?" → Soma TODAS as despesas de fumigação
- "Quanto gastei com taxas?" → Soma TODAS as taxas e laudos

Argumentos:
- contrato (opcional): Número do contrato (ex: "235/25", "400/25A")
  - Se INFORMADO: retorna despesas daquele contrato
  - Se NÃO INFORMADO: retorna agregação por tipo ou tipo específico

Exemplos de uso:
- "Quais as despesas do contrato 235/25?" → pesquisa_despesa_venda(contrato="235/25")
- "Quanto gastei com desembaraço em todos os contratos?" → pesquisa_despesa_venda()
- "Quanto gastei com fumigação?" → pesquisa_despesa_venda()
- "Quais os tipos de despesa?" → pesquisa_despesa_venda()
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_cotacao,
                name="pesquisa_cotacao",
                description="""Consulta cotações de moedas, câmbio, café, bolsa e outros ativos via banco de dados interno.

Use SEMPRE esta ferramenta PRIMEIRO quando o usuário perguntar sobre dólar, euro, café, bolsa, câmbio, ativo futuro ou qualquer cotação.
Só use pesquisa_internet se esta ferramenta não retornar resultado.

Exemplos de perguntas que devem usar esta ferramenta:
- "Qual a cotação do dólar hoje?" → tipo="Dolar", retorne o campo COTACAO
- "Ajuste dólar futuro DOLM26 em 15/05/2026" → tipo="Dolar", ativo="DOLM26", data="15/05/2026", retorne o campo AJUSTE
- "Abertura café KCK6 em 15/05/2026" → tipo="Café", ativo="KCK6", data="15/05/2026", retorne o campo ABERTURA
- "Qual o fechamento do EURO hoje?" → tipo="Euro", retorne o campo FECHAMENTO
- "Situação do dólar comercial em 15/05/2026" → tipo="Dólar Comercial", data="15/05/2026", retorne o campo SITUACAO
- "Como está o euro?" → tipo="Euro"
- "Cotação das moedas" → sem filtros, retorna tudo

Campos disponíveis no retorno: COTACAO, AJUSTE, ABERTURA, FECHAMENTO, SITUACAO, tipo, ativo.
Mostre apenas o(s) campo(s) relevante(s) para a pergunta do usuário.

Argumentos:
- data (opcional): Data desejada em qualquer formato (ex: "hoje", "15/05/2026", "20260515"). Padrão: hoje.
- tipo (opcional): Tipo do ativo (ex: "Dolar", "Euro", "Café", "Dólar Comercial").
- ativo (opcional): Código do instrumento específico (ex: "DOLM26", "KCK6", "DOLN26").
"""
            ),
            StructuredTool.from_function(
                func=self._criar_relatorio_agendado,
                name="criar_relatorio_agendado",
                description="""Cria um relatório agendado para ser enviado via WhatsApp ou email.

Use esta ferramenta quando o usuário pedir para receber um relatório — tanto uma única vez em horário específico quanto de forma recorrente.

REGRA DE EXECUÇÃO IMEDIATA:
- Se descrição, frequência, horário e canal já estiverem informados, chame esta ferramenta IMEDIATAMENTE.
- NÃO peça confirmação, NÃO repita os dados em forma de pergunta e NÃO espere o usuário responder "sim".
- A própria mensagem de sucesso da ferramenta é a confirmação final.
- Esta regra vale para TODOS os tipos de relatório, incluindo compras, vendas, contratos, estoque, Long/Short, financeiro, despesas e cotações.

REGRA OBRIGATÓRIA PARA "TODOS OS DIAS":
- Se o usuário disser "todos os dias", "todo dia", "diariamente" ou expressão equivalente sem esclarecer os dias da semana, NÃO chame esta ferramenta ainda.
- Pergunte: "Você quer receber de segunda a sexta-feira ou todos os dias corridos, incluindo sábado e domingo?"
- Preserve na conversa o relatório, horário e canal já informados. Depois da resposta, crie o agendamento sem perguntar novamente esses dados.
- Se responder segunda a sexta/dias úteis, use frequencia='dias_uteis'.
- Se responder todos os dias corridos/incluindo fim de semana, use frequencia='diario'.
- Não faça essa pergunta quando o usuário já tiver especificado uma dessas duas opções.

Exemplos de intenção:
- "Me manda um email às 11:40 com as cotações" → unico, horario="11:40", canal="email"
- "Me encaminha por email às 10:50 as informações do contrato" → unico, horario="10:50", canal="email"
- "Quero receber o saldo bancário toda sexta às 9h" → semanal
- "Me manda o estoque todo dia às 8h" → primeiro pergunte se é de segunda a sexta ou todos os dias corridos
- "Relatório de vendas todo dia 1 do mês" → mensal

Argumentos:
- descricao (obrigatório): Descrição clara do que o relatório deve conter.
  Exemplos: "cotações do dia", "informações do contrato 402/25R", "saldo bancário", "contas a pagar"
  ⚠️ A descrição será usada como instrução para gerar o relatório. Seja preciso.

- frequencia (obrigatório): 'unico', 'diario', 'dias_uteis', 'semanal' ou 'mensal'
  - 'unico': envia uma única vez no horário informado e cancela automaticamente
  - 'diario': envia todos os dias corridos, incluindo sábado e domingo
  - 'dias_uteis': envia de segunda a sexta-feira
  - 'semanal': envia uma vez por semana (requer dia_semana)
  - 'mensal': envia uma vez por mês (requer dia_mes)

- horario (obrigatório): Horário de envio no formato HH:MM (24h).
  Se o usuário não informar, use '08:00' como padrão.

- dia_semana (opcional, apenas para frequencia='semanal'): Dia da semana em português.
  Valores aceitos: 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo'

- dia_mes (opcional, apenas para frequencia='mensal'): Número do dia do mês (1-31).

- canal (opcional): Canal de envio. Valores aceitos: 'whatsapp', 'email', 'ambos'.
  - Se o usuário mencionar email → 'email'
  - Se o usuário mencionar WhatsApp → 'whatsapp'
  - Se mencionar os dois → 'ambos'
  - Se não mencionar canal e for recorrente, pergunte antes de criar
  - Default: 'whatsapp'
  - O email é obtido automaticamente do cadastro do usuário — não pergunte o email.

Exemplos de chamada:
- "Me manda por email às 11:40 as cotações" → criar_relatorio_agendado(descricao="cotações do dia", frequencia="unico", horario="11:40", canal="email")
- Após o usuário confirmar "segunda a sexta": criar_relatorio_agendado(descricao="saldo bancário atual", frequencia="dias_uteis", horario="07:30", canal="email")
- Após o usuário confirmar "incluindo sábado e domingo": criar_relatorio_agendado(descricao="saldo bancário atual", frequencia="diario", horario="07:30", canal="email")
- "Relatório financeiro toda segunda às 8h pelo WhatsApp" → criar_relatorio_agendado(descricao="relatório financeiro completo", frequencia="semanal", dia_semana="segunda", horario="08:00", canal="whatsapp")
- "Estoque todo dia 1 às 9h nos dois" → criar_relatorio_agendado(descricao="estoque atual de sacas", frequencia="mensal", dia_mes=1, horario="09:00", canal="ambos")
"""
            ),
            StructuredTool.from_function(
                func=self._listar_relatorios_agendados,
                name="listar_relatorios_agendados",
                description="""Lista os relatórios automáticos agendados do usuário.

Use quando o usuário perguntar sobre seus agendamentos ativos.
Exemplos:
- "Quais relatórios tenho agendados?"
- "Quais os meus relatórios automáticos?"
- "O que está agendado para mim?"
"""
            ),
            StructuredTool.from_function(
                func=self._cancelar_relatorio_agendado,
                name="cancelar_relatorio_agendado",
                description="""Cancela UM relatório automático agendado específico.

Use quando o usuário quiser cancelar um relatório específico (não todos).
⚠️ Sempre liste os relatórios primeiro (listar_relatorios_agendados) para obter o ID UUID correto.
⚠️ NÃO use os números 1, 2, 3 da listagem — use o ID UUID completo.

Exemplos:
- "Cancela o relatório financeiro" → liste primeiro, pegue o ID, cancele
- "Quero cancelar o relatório de estoque" → liste primeiro, pegue o ID, cancele

Argumentos:
- relatorio_id (obrigatório): ID UUID do relatório (ex: "a1b2c3d4-...").
"""
            ),
            StructuredTool.from_function(
                func=self._cancelar_todos_relatorios_agendados,
                name="cancelar_todos_relatorios_agendados",
                description="""Cancela TODOS os relatórios automáticos agendados do usuário de uma vez.

Use quando o usuário quiser cancelar todos os agendamentos.
Também use quando ele quiser cancelar todos EXCETO um tipo específico; nesse caso,
preencha manter_descricao com a descrição que deve permanecer ativa.
Exemplos:
- "Cancela todos os relatórios"
- "Remove todos os meus agendamentos"
- "Não quero mais receber nenhum relatório automático"
- "Para todos os envios automáticos"
- "Exclua todos menos contas a receber vencidas" → manter_descricao="contas a receber vencidas"

Argumentos:
- manter_descricao (opcional): relatório que deve ser preservado. Não informe quando todos devem ser cancelados.
"""
            ),
            StructuredTool.from_function(
                func=self._pesquisa_internet,
                name="pesquisa_internet",
                description="""Pesquisa informações na internet (notícias, clima, eventos, informações gerais).

⚠️ Para cotações de dólar, euro, café, bolsa e ativos futuros: use PRIMEIRO pesquisa_cotacao.
Só use esta ferramenta para cotações se pesquisa_cotacao não retornar resultado.

Use para:
- "Como está o clima em Santos?" / "Vai chover amanhã?"
- "Quais são as notícias de hoje sobre café?"
- "Notícias sobre exportação de café no Brasil"
- Qualquer pergunta sobre eventos ou informações gerais do mundo

❌ NÃO USE para dados internos da empresa (vendas, estoque, financeiro) — use as ferramentas específicas.

Argumentos:
- query (obrigatório): O que pesquisar (em português ou inglês)

Exemplos:
- "Notícias café exportação Brasil" → pesquisa_internet(query="notícias café exportação Brasil")
- "Clima em Santos amanhã" → pesquisa_internet(query="previsão do tempo Santos SP amanhã")
"""
            ),

            StructuredTool.from_function(
                func=self._pesquisa_despesa_venda_par,
                name="pesquisa_despesa_venda_par",
                description="""Consulta DESPESAS DE VENDA de um contrato específico passando contrato e letra como parâmetros diretos ao banco de dados.

Use esta ferramenta quando o usuário perguntar sobre despesas de um contrato específico E informar o número do contrato. Esta é a versão otimizada de pesquisa_despesa_venda — os filtros são passados diretamente ao SQL, tornando a busca mais precisa e eficiente.

QUANDO USAR:
- Usuário menciona um número de contrato específico E quer ver as despesas daquele contrato
- Usuário quer saber quanto gastou em um contrato específico (desembaraço, fumigação, taxas, etc.)
- Quando o número do contrato estiver disponível, SEMPRE prefira esta tool sobre pesquisa_despesa_venda

DIFERENÇA de pesquisa_despesa_venda:
- pesquisa_despesa_venda_par → passa contrato e letra diretamente ao SQL (mais eficiente e preciso)
- pesquisa_despesa_venda → versão genérica, sem suporte à letra, filtra no resultado

PARÂMETROS:
- contrato (obrigatório): Número do contrato exatamente como informado pelo usuário
  Ex: "235/25", "400/25A", "100/24"
- letra (opcional): Letra ou parcela do contrato — informe APENAS se o usuário mencionar explicitamente
  Ex: "A", "B", "C"

EXEMPLOS DE USO:
- "Quais as despesas do contrato 235/25?" → pesquisa_despesa_venda_par(contrato="235/25")
- "Despesas do contrato 400/25A letra B" → pesquisa_despesa_venda_par(contrato="400/25A", letra="B")
- "Quanto custou o desembaraço do contrato 100/24?" → pesquisa_despesa_venda_par(contrato="100/24")
- "Mostre todas as despesas do contrato 310/25" → pesquisa_despesa_venda_par(contrato="310/25")

⚠️ NÃO USE sem número de contrato — se o usuário não informou o contrato, use pesquisa_despesa_venda.""",
            ),

        ]
        
        # Adiciona tool de criação de contratos ADA
        tools_list.append(self.get_ada_tool())
        if self.user.has_permission("Fixacao"):
            from app.agents.fixacao_tools import create_fixacao_tool
            tools_list.append(create_fixacao_tool(
                self.session_id or "default",
                has_permission=True,
            ))
        else:
            logger.info(
                "Tool de fixação não disponibilizada para %s: permissão Fixacao ausente",
                self.user.telefone,
            )
        
        return tools_list
    
    def get_ada_tool(self):
        """Retorna tool de criação de contratos ADA (session-aware)"""
        from app.agents.ada_tools import create_ada_tools
        ada = create_ada_tools(session_id=self.session_id or "default")
        return ada.get_tool()
