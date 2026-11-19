"""Períodos e apresentação da consulta de pagamentos de café."""

import asyncio
from datetime import datetime
from decimal import Decimal
import json
import logging
import re

from app.services.applications_loans import amount, decimal_value, display_date, normalize


logger = logging.getLogger(__name__)
HEADING = "*Contas a pagar de café"
PERIOD_QUESTION = "Qual período de vencimento você quer consultar?"
LIST_QUESTION = "Deseja que eu exiba uma lista com os títulos?"
FIELDS = {
    "FILIAL": "Filial",
    "SOLICITACAO": "Solicitação",
    "PEDIDO": "Pedido",
    "EMISSAO": "Emissão",
    "VENCIMENTO": "Vencimento",
    "NOME_FORNECEDOR": "Fornecedor",
    "SACAS": "Sacas",
    "VALOR_TOTAL": "Valor a Pagar",
}
EXTRA_LABELS = {
    "ESTAGIO": "Estágio", "CONTRATO_CAFE": "Contrato de café",
    "COD_FORNECEDOR": "Código do fornecedor", "LOJA": "Loja", "KILOS": "Quilos",
    "PRECO_MEDIO": "Preço médio", "CONSUMO_SACAS": "Sacas para consumo",
    "EXPORTAVEL_SACAS": "Sacas exportáveis", "DOLAR": "Cotação do dólar",
    "PERC_QUEBRA": "% de quebra", "PERC_PVA": "% de PVA",
    "PERC_FUNDO": "% de fundo", "PERC_IMPUREZA": "% de impureza", "RENDA": "Renda",
    "CONSIGNADO": "Consignado", "STATUS": "Status", "DT_CANCELAMENTO": "Data de cancelamento",
    "PAGADORA": "Pagadora",
}
DECIMAL_FIELDS = {
    "SACAS", "KILOS", "CONSUMO_SACAS", "EXPORTAVEL_SACAS", "DOLAR",
    "PERC_QUEBRA", "PERC_PVA", "PERC_FUNDO", "PERC_IMPUREZA", "RENDA",
}
DAY_COUNTS = dict(zip(
    ("um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez"),
    range(1, 11),
))
DATE_TOKEN = r"\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{8})\b"
RELATIVE_DAY = r"hoje|amanha|ontem"
RANGE_END = rf"(?:{DATE_TOKEN}|\b(?:{RELATIVE_DAY})\b)"
IDENTIFIER = r"[a-z]*[0-9][a-z0-9/-]*\b"
TITLE_REFERENCE = re.compile(
    rf"\b(titulos?|pedidos?|solicitac(?:ao|oes))\s+(?:(?:n(?:umero)?\.?|#)\s*)?"
    rf"({IDENTIFIER}(?:(?:\s*,\s*|\s+e\s+){IDENTIFIER})*)"
)
REFERENCE_FIELDS = {"titulos": "titulo", "pedidos": "pedido", "solicitacoes": "solicitacao"}
CHOICE_HEADING = "Há mais de um registro para"


def title_references(text):
    references = []
    for field, identifiers in TITLE_REFERENCE.findall(text):
        field = REFERENCE_FIELDS.get(field, field)
        references.extend((field, identifier) for identifier in re.findall(IDENTIFIER, identifiers))
    return list(dict.fromkeys(references))
PERIOD_REPLY = re.compile(
    r"^(?:para |de |do dia |entre |no dia |dia |ness[ae] |dest[ae] )?"
    r"(?:\d|hoje\b|amanha\b|ontem\b|est[ae]\b|ess[ae]\b|proxim\w*\b|"
    r"ultim\w*\b|mes\b|semana\b|segunda\b|terca\b|quarta\b|quinta\b|sexta\b|sabado\b|domingo\b|"
    r"janeiro\b|fevereiro\b|marco\b|abril\b|maio\b|junho\b|julho\b|agosto\b|"
    r"setembro\b|outubro\b|novembro\b|dezembro\b)"
)
NATURAL_PERIOD = re.compile(
    r"\b(?:hoje|amanha|ontem|semana|mes|trimestre|semestre|"
    r"janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b"
    r"|\b(?:proximos?|ultimos?)\s+\d+\s+dias?\b"
)


def is_coffee_payment_query(text):
    plain = normalize(text)
    return bool(re.search(r"\bcafe\b", plain) and re.search(
        r"\b(?:pagamentos?|contas?\s+a\s+pagar|pagar|titulos?\s+a\s+pagar)\b", plain
    ))


def payment_period(text):
    """Retorna os limites inclusivos em YYYYMMDD ou None se faltarem datas."""
    from app.utils.date_parser import date_parser

    plain = normalize(text)
    plain = re.sub(
        r"\b(proximos?|ultimos?)\s+(" + "|".join(DAY_COUNTS) + r")\s+(dias?)\b",
        lambda match: f"{match[1]} {DAY_COUNTS[match[2]]} {match[3]}",
        plain,
    )
    # A SP recebe um intervalo corrido. Evite ampliar silenciosamente dias úteis.
    if re.search(r"\bdias?\s+ute(?:l|is)\b", plain):
        raise ValueError("Informe um intervalo de datas corridas, por exemplo, de 18/11/2026 a 20/11/2026.")
    if re.search(r"\b(?:proximos?|ultimos?)\s+0\s+dias?\b", plain):
        raise ValueError("Informe uma quantidade de dias maior que zero.")

    def parse_day(token):
        if re.fullmatch(RELATIVE_DAY, token):
            return date_parser.parse_natural_date(token)["data_inicio"]
        pattern = "%d/%m/%Y" if "/" in token else "%Y-%m-%d" if "-" in token else "%Y%m%d"
        return datetime.strptime(token, pattern).strftime("%Y%m%d")

    interval = re.search(rf"({RANGE_END})\s*(?:ate|a|e|[-–])\s*({RANGE_END})", plain)
    dates = re.findall(DATE_TOKEN, plain)
    try:
        if interval:
            start, end = map(parse_day, interval.groups())
        elif len(dates) > 1:
            return None
        elif dates:
            if re.search(r"\b(?:desde|a partir de|ate|entre)\b|\bde\s+" + DATE_TOKEN, plain):
                return None
            start = end = parse_day(dates[0])
        else:
            if not NATURAL_PERIOD.search(plain) or re.search(r"\b(?:desde|a partir de|ate|entre)\b", plain):
                return None
            parsed = date_parser.parse_natural_date(plain) or {}
            start, end = parsed.get("data_inicio"), parsed.get("data_fim")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Informe um período de vencimento válido.") from exc
    if start and end:
        if start > end:
            raise ValueError("A data inicial de vencimento deve ser anterior ou igual à final.")
        return start, end
    return None


def normalize_rows(rows):
    return [{str(key).strip().upper(): value for key, value in row.items()} for row in rows]


def summary(rows, start, end):
    dates = display_date(start) if start == end else f"{display_date(start)} a {display_date(end)}"
    lines = [f"{HEADING}*", f"Vencimentos: {dates}"]
    if not rows:
        lines.append("Nenhum título encontrado no período.")
    else:
        total = sum((decimal_value(row.get("VALOR_TOTAL")) for row in rows), Decimal(0))
        lines.extend([f"• Total de títulos: {len(rows)}", f"• Total a pagar: R$ {amount(total)}"])
    return "\n".join(lines)


def display_field(field, value):
    if value is None or str(value).strip() == "":
        return "Não informado"
    if field in {"EMISSAO", "VENCIMENTO", "DT_CANCELAMENTO"}:
        return display_date(value)
    if field == "VALOR_TOTAL":
        return f"R$ {amount(value)}"
    if field in DECIMAL_FIELDS or field == "PRECO_MEDIO":
        try:
            number = decimal_value(value)
        except ValueError:
            return str(value).strip()
        if field == "PRECO_MEDIO":
            return amount(number)
        integer, _, fraction = format(number, ",f").partition(".")
        whole = integer.replace(",", ".")
        fraction = fraction.rstrip("0")
        return f"{whole},{fraction}" if fraction else whole
    return str(value).strip()


def title_block(index, row, *, extra=False):
    lines = [f"*Título {index}*"]
    for field, label in FIELDS.items():
        lines.append(f"• {label}: {display_field(field, row.get(field))}")
    if extra:
        additional = [f"• {EXTRA_LABELS.get(field, field)}: {display_field(field, value)}"
                      for field, value in row.items() if field not in FIELDS]
        lines.extend(additional or ["A consulta não retornou outros campos para este título."])
    return "\n".join(lines)


def matching_titles(rows, field, identifier):
    if field == "titulo":
        index = int(identifier) if identifier.isascii() and identifier.isdigit() else 0
        return [(index, rows[index - 1])] if 1 <= index <= len(rows) else []
    column = {"pedido": "PEDIDO", "solicitacao": "SOLICITACAO"}[field]
    key = identifier.lstrip("0")
    return [(index, row) for index, row in enumerate(rows, 1)
            if row.get(column) not in (None, "") and normalize(row[column]).lstrip("0") == key]


def title_details(rows, references):
    blocks = [f"{HEADING} — detalhes*"]
    shown = set()
    for field, identifier in references:
        matches = matching_titles(rows, field, identifier)
        label = {"titulo": "título", "pedido": "pedido", "solicitacao": "solicitação"}[field]
        if len(matches) == 1:
            index, row = matches[0]
            if index not in shown:
                blocks.append(title_block(index, row, extra=True))
                shown.add(index)
        elif matches:
            choices = []
            for index, row in matches:
                filial = display_field("FILIAL", row.get("FILIAL"))
                solicitacao = display_field("SOLICITACAO", row.get("SOLICITACAO"))
                fornecedor = display_field("NOME_FORNECEDOR", row.get("NOME_FORNECEDOR"))
                amount_due = display_field("VALOR_TOTAL", row.get("VALOR_TOTAL"))
                choices.append(f"• Título {index} — filial {filial} | solicitação {solicitacao} | {fornecedor} | {amount_due}")
            blocks.append(f"{CHOICE_HEADING} o {label} {identifier}. Informe o número do título da lista.\n"
                          + "\n".join(choices))
        else:
            blocks.append(f"{label.capitalize()} {identifier} não encontrado na última consulta de pagamentos de café.")
    return "\n\n".join(blocks)


async def handle_query(orchestrator, message, *, read_only=False):
    text = normalize(message).rstrip(".!?")
    if read_only:
        # A data e os exemplos acrescentados pelo agendador não são filtros.
        scheduled = re.search(
            r"seguinte relatório completo: (.*?)\. Execute diretamente",
            message, re.IGNORECASE | re.DOTALL,
        )
        if scheduled:
            message = scheduled[1]
            text = normalize(message)
    elif re.search(r"\b(?:agend\w*|program\w*|diariamente|semanalmente|mensalmente)\b", text):
        return None

    explicit = is_coffee_payment_query(text)
    references = title_references(text)
    bare_number = re.fullmatch(r"[0-9]{1,8}", text)
    list_requested = bool(re.fullmatch(
        r"(?:sim(?:[, ]+(?:pode (?:exibir|mostrar|listar)|por favor))?|"
        r"(?:exiba|mostre|liste) (?:a lista(?: de titulos)?|os titulos)|pode (?:exibir|mostrar|listar))", text
    ))
    declined = text in {"nao", "n"}
    previous = ""
    period_reply = PERIOD_REPLY.match(text)
    if not read_only and (references or (not explicit and (period_reply or list_requested or declined))):
        previous = next((str(item.content) for item in reversed(orchestrator.message_history.messages)
                         if getattr(item, "type", None) == "ai"), "")
    contextual = previous.startswith(HEADING)
    awaiting_period = contextual and PERIOD_QUESTION in previous
    has_titles = contextual and (LIST_QUESTION in previous or previous.startswith(
        (f"{HEADING} — lista*", f"{HEADING} — detalhes*")
    ))
    pending_choices = [block for block in previous.split("\n\n") if block.startswith(CHOICE_HEADING)]
    choices = {int(index) for index in re.findall(r"(?m)^• Título ([0-9]+) — filial ", "\n".join(pending_choices))}
    selecting_title = has_titles and bare_number is not None and bool(choices)
    if selecting_title:
        references = [("titulo", text)]

    if not explicit and not awaiting_period and not (has_titles and (references or list_requested or declined)):
        return None
    if not explicit and awaiting_period and not period_reply:
        return None

    from app.agents.sql_tools import SQLTools
    from app.core.config import settings
    from app.core.redis_client import redis_client
    from app.utils.sql_validator import sql_validator

    allowed, denial = sql_validator.validate_permission(orchestrator.user, "usp_IA_PagamentoCafe")
    if not allowed:
        return denial
    if selecting_title and int(text) not in choices:
        return "\n\n".join([f"{HEADING} — detalhes*", "Escolha um dos títulos apresentados.", *pending_choices])
    key = f"pagamentos_cafe:{settings.app_env}:{orchestrator.session_id or orchestrator.user.telefone}"
    try:
        if not read_only and has_titles and (references or (not explicit and (list_requested or declined))):
            if declined:
                return "Certo. Quando precisar, peça uma nova consulta de pagamentos de café."
            snapshot = await redis_client.get(key)
            if not snapshot:
                return "A consulta anterior expirou. Informe novamente o período de vencimento dos pagamentos de café."
            rows = snapshot["rows"]
            if references:
                output = title_details(rows, references)
                if selecting_title:
                    # Ainda permite escolher para os demais pedidos ambíguos.
                    chosen = f"• Título {int(text)} — filial "
                    remaining = [block for block in pending_choices if not any(
                        line.startswith(chosen) for line in block.splitlines()
                    )]
                    if remaining:
                        output += "\n\n" + "\n\n".join(remaining)
                return output
            blocks = [title_block(index, row) for index, row in enumerate(rows, 1)]
            return f"{HEADING} — lista*\n\n" + "\n-----------------------------------------\n\n".join(blocks)

        try:
            period = payment_period(message)
        except ValueError as exc:
            return f"{HEADING} — período*\n{exc}\n{PERIOD_QUESTION}"
        if not period:
            if read_only:
                return f"{HEADING} — período*\nO relatório precisa de um intervalo de vencimentos."
            return f"{HEADING} — período*\n{PERIOD_QUESTION} Pode dizer hoje, essa semana ou informar as datas."

        start, end = period
        tools = SQLTools(orchestrator.user, orchestrator.session_id)
        raw_rows = await asyncio.to_thread(tools._consultar_pagamentos_cafe, start, end)
        rows = normalize_rows(raw_rows)
        output = summary(rows, start, end)
        if read_only:
            orchestrator.last_report_rows = raw_rows
        elif rows:
            try:
                await redis_client.set(key, json.dumps({"rows": rows}, ensure_ascii=False, default=str), ttl=3600)
            except Exception:
                logger.warning("Não foi possível guardar a lista de pagamentos de café.", exc_info=True)
                return output + "\n\nA lista está indisponível no momento. Tente uma nova consulta."
            output += f"\n\n{LIST_QUESTION}"
        return output
    except Exception:
        logger.exception("Erro ao consultar pagamentos de café.")
        return "Não foi possível consultar os pagamentos de café. Tente novamente em instantes."
