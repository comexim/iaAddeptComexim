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
            # Campos logísticos e administrativos
            "contratos_com_bl": [],
            "contratos_embarcados": [],
            "contratos_amostra_enviada": [],
            "contratos_amostra_aprovada": [],
            "contratos_amostra_pendente": [],  # enviada mas NÃO aprovada
            "contratos_baixados": [],
            "contratos_baixados_por_mes": defaultdict(list),  # agrupa por YYYYMM
            "vendedores": set(),
            "filiais": set(),
            "grupos_venda": set(),
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

            # Contratos com BL
            if row.get("numeroBL") and str(row["numeroBL"]).strip():
                data["contratos_com_bl"].append(contrato)

            # Contratos embarcados (com data de saída do navio)
            if row.get("saidaNavio") and str(row["saidaNavio"]).strip():
                data["contratos_embarcados"].append(contrato)

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

                # Agrupa por mês (YYYYMM)
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
                "contratos_com_bl": ", ".join(data["contratos_com_bl"][:20]) if data["contratos_com_bl"] else "",
                "total_contratos_com_bl": len(data["contratos_com_bl"]),
                "contratos_embarcados": ", ".join(data["contratos_embarcados"][:20]) if data["contratos_embarcados"] else "",
                "total_contratos_embarcados": len(data["contratos_embarcados"]),
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
                "vendedores": sorted(list(data["vendedores"])) if data["vendedores"] else [],
                "filiais": sorted(list(data["filiais"])) if data["filiais"] else [],
                "grupos_venda": sorted(list(data["grupos_venda"])) if data["grupos_venda"] else [],
            })

        # OTIMIZAÇÃO ESPECIAL 1: Query sobre "baixados EM [mês]"
        if self.user_query and re.search(r'baixad[oa]s?\s+(no\s+contas\s+a\s+receber\s+)?em\s+', self.user_query.lower()):
            # Filtra apenas clientes com baixados em jan/2026 ou dez/2025
            filtered_list = [
                r for r in result_list
                if r.get("total_baixados_jan2026", 0) > 0 or r.get("total_baixados_dez2025", 0) > 0
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
                })

            logger.info(f"[OTIMIZAÇÃO BAIXADOS] Retornando {len(minimal_list)} clientes com campos mínimos (jan2026/dez2025)")
            return minimal_list

        # OTIMIZAÇÃO ESPECIAL 2: Query sobre período específico (ex: "em janeiro", "por grupo em 2026")
        # Detecta queries com menção a mês/ano e retorna campos resumidos
        if self.user_query and re.search(r'\b(em|no|de)\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b', self.user_query.lower()):

            # OTIMIZAÇÃO ESPECIAL 2.1: Se a query menciona "por grupo", agregar por grupo de venda
            if re.search(r'\bpor\s+grupo', self.user_query.lower()):
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
            if re.search(r'\bfixad[oa]s?|importador|exportador', self.user_query.lower()):
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
            if re.search(r'\bvendedor[ea]?s?', self.user_query.lower()):
                from collections import defaultdict

                por_vendedor = defaultdict(lambda: {"valor": 0, "sacas": 0, "contratos": 0, "clientes": set()})

                for r in result_list:
                    vendedores = r.get("vendedores", [])
                    valor = r["total_valor"]
                    sacas = r["total_sacas"]
                    num_contratos = r["total_contratos"]
                    cliente = r["cliente"]

                    # Se não tem vendedor, categoriza como "SEM VENDEDOR"
                    if not vendedores or len(vendedores) == 0:
                        vendedores = ["SEM VENDEDOR"]

                    # Cada cliente pode ter múltiplos vendedores
                    for vendedor in vendedores:
                        por_vendedor[vendedor]["valor"] += valor
                        por_vendedor[vendedor]["sacas"] += sacas
                        por_vendedor[vendedor]["contratos"] += num_contratos
                        por_vendedor[vendedor]["clientes"].add(cliente)

                # Converte para lista ordenada por sacas
                vendedores_list = []
                for vendedor, totais in sorted(por_vendedor.items(), key=lambda x: x[1]["sacas"], reverse=True):
                    vendedores_list.append({
                        "vendedor": vendedor,
                        "sacas_total": round(totais["sacas"], 2),
                        "valor_total": round(totais["valor"], 2),
                        "numero_contratos": totais["contratos"],
                        "numero_clientes": len(totais["clientes"])
                    })

                logger.info(f"[AGREGAÇÃO POR VENDEDOR] Retornando {len(vendedores_list)} vendedores agregados")
                return vendedores_list

            # Se não menciona "por grupo" nem "fixado" nem "vendedor", retorna por cliente
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

        Args:
            results: Lista de resultados SQL de IA_Orcamento()

        Returns:
            Lista agregada por grupo com orcado, realizado, saldo
        """
        from collections import defaultdict

        aggregated = defaultdict(lambda: {
            "orcado": 0,
            "realizado": 0,
            "saldo": 0,
            "registros": 0
        })

        for row in results:
            grupo = row.get("grupo", "SEM GRUPO")
            descricao = row.get("descricao", "").strip()

            # Usa descrição como chave (mais legível que código)
            key = descricao if descricao else grupo

            aggregated[key]["orcado"] += row.get("orcado", 0) or 0
            aggregated[key]["realizado"] += row.get("realizado", 0) or 0
            aggregated[key]["saldo"] += row.get("saldo", 0) or 0
            aggregated[key]["registros"] += 1

        # Converte para lista
        result_list = []
        for categoria, data in aggregated.items():
            # Calcula percentual realizado
            percentual = 0
            if data["orcado"] > 0:
                percentual = round((data["realizado"] / data["orcado"]) * 100, 2)

            result_list.append({
                "categoria": categoria,
                "orcado": round(data["orcado"], 2),
                "realizado": round(data["realizado"], 2),
                "saldo": round(data["saldo"], 2),
                "percentual_realizado": percentual,
                "meses_incluidos": data["registros"]
            })

        # Ordena por valor orçado (maior primeiro)
        result_list.sort(key=lambda x: x["orcado"], reverse=True)

        logger.info(f"Agregados {len(results)} registros de orçamento em {len(result_list)} categorias")
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
            def convert_decimals(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            # ORÇAMENTO: Agrega por categoria/grupo
            if function_name == "IA_Orcamento":
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
- categoria: nome da categoria/grupo orçamentário
- orcado: valor orçado desta categoria (R$)
- realizado: valor realizado desta categoria (R$)
- saldo: saldo desta categoria (R$)
- percentual_realizado: percentual realizado desta categoria (%)
- meses_incluidos: quantidade de registros agregados

IMPORTANTE:
1. Orçamento NÃO tem contratos, sacas ou clientes. É uma previsão financeira.
2. Para totais gerais, USE OS VALORES PRÉ-CALCULADOS acima. NÃO some manualmente.
3. Os "TOTAIS GERAIS" já incluem TODAS as categorias somadas.

Exemplos de perguntas:
- "Qual o orçado total?" → Use "Total Orçado" dos TOTAIS GERAIS
- "Quanto foi realizado?" → Use "Total Realizado" dos TOTAIS GERAIS
- "Qual categoria teve maior gasto?" → Ordene as categorias por "realizado"
- "Qual o percentual realizado?" → Use "Percentual Realizado" dos TOTAIS GERAIS"""

            # VENDAS: Agrega por cliente
            else:
                logger.info(f"[AGREGAÇÃO] {len(results)} registros, agregando por cliente...")
                aggregated = self._aggregate_by_client(results)
                formatted = json.dumps(aggregated, ensure_ascii=False, indent=2, default=convert_decimals)

                return f"""Resultados da consulta {function_name} (AGREGADOS POR CLIENTE):

Total de registros SQL: {original_count}
Total de clientes: {len(aggregated)}

Dados agregados:
{formatted}

Instruções: Os dados acima estão AGREGADOS por cliente. Cada linha mostra:

TOTAIS (PRÉ-CALCULADOS):
- total_contratos: quantidade de contratos daquele cliente
- total_sacas: soma de sacas de todos os contratos
- total_valor: soma do valor total de todos os contratos (em R$)

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
- contratos_amostra_enviada: lista de contratos que enviaram amostra (até 20 primeiros)
- total_contratos_amostra_enviada: quantidade de contratos que enviaram amostra
- contratos_amostra_aprovada: lista de contratos com amostra aprovada (até 20 primeiros)
- total_contratos_amostra_aprovada: quantidade de contratos com amostra aprovada
- contratos_amostra_pendente: lista de contratos que ENVIARAM amostra mas NÃO APROVARAM ainda (até 20 primeiros)
- total_contratos_amostra_pendente: quantidade de contratos com amostra pendente de aprovação
- contratos_baixados: lista de contratos baixados financeiramente no formato "CONTRATO (YYYYMMDD)" onde YYYYMMDD é a data de baixa (até 100 primeiros)
- total_contratos_baixados: quantidade de contratos baixados (TODAS as datas)

CONTRATOS BAIXADOS POR MÊS ESPECÍFICO (use estes campos para queries com data):
- contratos_baixados_jan2026: lista de contratos baixados EM janeiro/2026 (até 100)
- total_baixados_jan2026: quantidade de contratos baixados em janeiro/2026
- contratos_baixados_dez2025: lista de contratos baixados EM dezembro/2025 (até 100)
- total_baixados_dez2025: quantidade de contratos baixados em dezembro/2025

  IMPORTANTE - COMO USAR:
  - Para perguntas como "contratos baixados EM janeiro 2026" → use contratos_baixados_jan2026 e total_baixados_jan2026
  - Para perguntas como "contratos baixados EM dezembro 2025" → use contratos_baixados_dez2025 e total_baixados_dez2025
  - NÃO use total_contratos_baixados para queries com data específica (ele conta TODOS os meses)

IMPORTANTE - REGRAS CRÍTICAS:
1. TODAS as médias acima estão PRÉ-CALCULADAS. USE OS VALORES DIRETAMENTE.
2. NÃO tente recalcular médias manualmente.
3. Cada campo de média (ex: diferencial_medio) já considera TODOS os contratos daquele cliente.
4. Para perguntas sobre médias, use SEMPRE os campos _medio/_media fornecidos.
5. PENEIRAS: Use apenas peneira_mtgb_media, peneira_grauda_media, peneira_grinder_media.
   NÃO extraia tamanhos de peneira das descrições de qualidade (ex: "13 UP", "17/18").

Exemplos corretos de uso:
- "Qual o diferencial médio?" → Use o campo diferencial_medio DIRETAMENTE
- "Quais certificados?" → Use o campo certificados
- "Qual o preço médio?" → Use valor_unitario_medio ou valor_fixado_medio DIRETAMENTE
- "Quais qualidades de café?" → Use o campo qualidades
- "Para quais países?" → Use o campo paises
- "Quais as peneiras?" → Use peneira_mtgb_media/peneira_grauda_media/peneira_grinder_media
- "Quais contratos têm BL?" → Use contratos_com_bl e total_contratos_com_bl
- "Quais contratos já embarcaram?" → Use contratos_embarcados e total_contratos_embarcados
- "Quais contratos enviaram amostra?" → Use contratos_amostra_enviada e total_contratos_amostra_enviada
- "Quais contratos aprovaram amostra?" → Use contratos_amostra_aprovada e total_contratos_amostra_aprovada
- "Quais contratos enviaram mas não aprovaram amostra?" → Use contratos_amostra_pendente e total_contratos_amostra_pendente
- "Quais vendedores?" → Use o campo vendedores
- "Quantos contratos foram baixados?" → Use total_contratos_baixados"""

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

            "IA_Vendas": """
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
- valorTotal: valor total do contrato em R$ (valorUnitario * sacas)
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
COLUNAS DISPONÍVEIS EM ESTOQUE:
Verifique os campos retornados nos registros acima.
Campos comuns: produto, descricao, quantidade, filial, etc.""",

            "IA_SaldoBancario": """
COLUNAS DISPONÍVEIS EM SALDO BANCÁRIO:
Verifique os campos retornados nos registros acima.
Campos comuns: banco, agencia, conta, saldo, moeda, etc.""",

            "IA_Cotacao": """
COLUNAS DISPONÍVEIS EM COTAÇÃO:
Verifique os campos retornados nos registros acima.
Campos comuns: data, produto, bolsa, preco, variacao, etc.""",

            "IA_DespesaVenda": """
COLUNAS DISPONÍVEIS EM DESPESA DE VENDA:
Verifique os campos retornados nos registros acima.
Campos comuns: contrato, despesa, valor, fornecedor, etc."""
        }

        # Pega instrução específica ou genérica
        specific_instructions = FUNCTION_INSTRUCTIONS.get(function_name,
            "Analise TODOS os campos disponíveis nos registros acima e responda com base nos dados reais.")

        return f"""Resultados da consulta {function_name}:

Total de registros retornados pelo SQL: {original_count}
Registros nesta resposta: {len(results)}

Dados:
{formatted}{warning}

{specific_instructions}

Analise TODOS os {len(results)} registros acima e responda com base nos campos disponíveis."""

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

        # PROTEÇÃO: Detecta queries sobre "baixados EM [data]" e força periodo=None
        if periodo and self.user_query:
            query_lower = self.user_query.lower()
            # Padrões que indicam query sobre DATA DE BAIXA (não embarque)
            if re.search(r'baixad[oa]s?\s+(no\s+contas\s+a\s+receber\s+)?em\s+', query_lower):
                logger.warning(f"[PROTEÇÃO] Query sobre 'baixados EM [data]' detectada - IGNORANDO periodo={periodo}")
                logger.warning(f"[PROTEÇÃO] Query original: {self.user_query}")
                logger.warning(f"[PROTEÇÃO] Usando periodo=None para buscar TODOS os contratos e filtrar por campos específicos")
                periodo = None  # Força periodo=None

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
            # PERMITIDO: periodo=None para queries que filtram por outros campos
            # Exemplo: "contratos baixados EM janeiro 2026" usa campos contratos_baixados_jan2026
            logger.info("[DEBUG] periodo=None - buscando TODOS os contratos (agregação irá filtrar)")
            filters = None  # Sem filtro de data

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
            periodo: Período desejado (ex: "dezembro 2025", "2025/12", "2TRIM 2025")

        Returns:
            Dados de orçamento
        """
        filters = None
        if periodo:
            parsed = date_parser.parse_natural_date(periodo)
            if parsed:
                # PRIORIDADE 1: Se tem lista de meses (trimestre/semestre)
                if "meses" in parsed and "ano" in parsed:
                    filters = {
                        "ano": int(parsed["ano"]),
                        "mes": parsed["meses"]  # Lista de meses ['04','05','06']
                    }
                    logger.info(f"[ORÇAMENTO] Trimestre/Semestre detectado: ano={parsed['ano']}, meses={parsed['meses']}")
                # PRIORIDADE 2: Mês único
                elif "ano" in parsed and "mes" in parsed:
                    filters = {
                        "ano": int(parsed["ano"]),
                        "mes": parsed["mes"]
                    }
                    logger.info(f"[ORÇAMENTO] Mês único: ano={parsed['ano']}, mes={parsed['mes']}")

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
            StructuredTool.from_function(
                func=self._pesquisa_vendas,
                name="pesquisa_vendas",
                description="""Consulta dados de CONTRATOS DE VENDA (vendas e embarques da empresa).

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

CASO 1 - NÃO PASSE PERIODO (deixe None ou omita):
→ APENAS quando a pergunta é sobre "BAIXADOS EM [MÊS/ANO]"
→ Exemplos:
  • "contratos baixados EM janeiro 2026" → pesquisa_vendas() SEM periodo
  • "contratos baixados no contas a receber EM janeiro 2026" → pesquisa_vendas() SEM periodo
  • "quais contratos foram baixados EM dezembro 2025" → pesquisa_vendas() SEM periodo
→ Razão: A agregação já retorna campos específicos (contratos_baixados_jan2026, total_baixados_jan2026)

CASO 2 - SEMPRE PASSE periodo='[mês] [ano]':
→ Para TODAS as outras perguntas que mencionam "EM [MÊS/ANO]", incluindo:
  ✓ "vendas EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "valor total EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "por grupo de venda EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "por cliente EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "sacas EM janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "contratos COM EMBARQUE em janeiro 2026" → pesquisa_vendas(periodo='janeiro 2026')
  ✓ "embarques de fevereiro 2026" → pesquisa_vendas(periodo='fevereiro 2026')
→ Razão: Precisa filtrar a query SQL por mesEmbarque para retornar apenas o período solicitado

⚠️ RESUMO: Se a pergunta NÃO é sobre "baixados EM", mas menciona um mês/período, SEMPRE passe o periodo!

Exemplos de periodo: 'sexta-feira passada', 'hoje', 'últimos 7 dias', 'dezembro 2025', 'janeiro 2026'"""
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
                description="""Consulta TÍTULOS FINANCEIROS a receber (boletos, duplicatas, recebimentos futuros).

⚠️⚠️⚠️ REGRA ABSOLUTA DE EXCLUSÃO ⚠️⚠️⚠️
NUNCA USE ESTA FERRAMENTA SE A PERGUNTA CONTÉM A PALAVRA "CONTRATOS"
Se a pergunta menciona "contratos" (contratos de venda), SEMPRE use pesquisa_vendas,
mesmo que a pergunta também mencione "contas a receber".

Exemplos de quando NÃO usar esta ferramenta:
- "contratos baixados no contas a receber" → use pesquisa_vendas
- "contratos que foram baixados" → use pesquisa_vendas
- "quais contratos..." → use pesquisa_vendas

IMPORTANTE - Esta ferramenta é para TÍTULOS FINANCEIROS, NÃO para contratos de venda.
Use esta ferramenta SOMENTE quando o usuário perguntar sobre:
- "títulos a receber"
- "boletos a receber"
- "duplicatas"
- "recebimentos futuros"
- "vencimentos de recebimentos"

Para CONTRATOS DE VENDA (mesmo que baixados financeiramente), use pesquisa_vendas.

Argumentos: data_vencimento (opcional, ex: 'próximos 7 dias')"""
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
