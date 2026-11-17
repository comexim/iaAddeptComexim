"""Resumo e detalhamento de aplicações/empréstimos, sem cálculos pelo LLM."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import re
import unicodedata


TITLES = {"APL": "Aplicações", "EMP": "Empréstimos"}
DETAIL_QUESTION = "Deseja detalhar os totais em lançamentos? Responda Sim ou indique uma moeda."
SEPARATOR = "-----------------------------------------"


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "").lower())
                   if not unicodedata.combining(c)).strip()


def requested_types(message):
    text = normalize(message)
    return [kind for kind, pattern in (("APL", r"\baplicac(?:ao|oes)\b"), ("EMP", r"\bemprestimos?\b"))
            if re.search(pattern, text)]


def detail_requested(message):
    return bool(re.search(r"\b(?:detalh\w*|lancamentos?|registros?)\b", normalize(message)))


def currency_name(value):
    text = normalize(value)
    aliases = {
        "BRL": ("brl", "real", "reais", "r$"),
        "USD": ("usd", "dolar", "dolares", "us$"),
        "EUR": ("eur", "euro", "euros", "€"),
        "GBP": ("gbp", "libra", "libras", "£"),
    }
    return next((code for code, names in aliases.items() if text in names), str(value or "Não informada").strip())


def currency_filter(message):
    text = normalize(message)
    for token, code in ((r"\b(?:brl|real|reais)\b|r\$", "BRL"),
                        (r"\b(?:usd|dolar|dolares)\b|us\$", "USD"),
                        (r"\b(?:eur|euros?)\b|€", "EUR"), (r"\b(?:gbp|libras?)\b|£", "GBP")):
        if re.search(token, text):
            return code
    return None


def decimal_value(value):
    if value is None or str(value).strip() == "":
        raise ValueError("Campo monetário ausente no retorno da SP.")
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Campo monetário inválido no retorno da SP.") from exc
    if not number.is_finite():
        raise ValueError("Campo monetário inválido no retorno da SP.")
    return number


def amount(value):
    return f"{decimal_value(value):,.2f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def display_date(value):
    if value in (None, ""):
        return "Não informada"
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    for pattern in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value)[:10], pattern).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return str(value)


def format_position(snapshot, detail=False, currency=None):
    blocks = []
    found = False
    for kind, source in snapshot.items():
        rows = [{str(key).strip().lower(): value for key, value in row.items()} for row in source]
        rows = [row for row in rows if not currency or currency_name(row.get("moeda")) == currency_name(currency)]
        totals, counts = defaultdict(lambda: Decimal("0")), defaultdict(int)
        for row in rows:
            code = currency_name(row.get("moeda"))
            # Total é exclusivamente o retornado pela SP; nunca Saldo + Juros.
            totals[code] += decimal_value(row.get("total"))
            counts[code] += 1
        lines = [f"*{TITLES[kind]} — {'lançamentos' if detail else 'resumo por moeda'}*"]
        if not rows:
            lines.append("Nenhum lançamento encontrado" + (f" em {currency}." if currency else "."))
        for code in sorted(totals):
            found = True
            lines.extend(["", f"*Moeda: {code}*", f"• Total: {amount(totals[code])}", f"• Lançamentos: {counts[code]}"])
            if not detail:
                continue
            for index, row in enumerate((row for row in rows if currency_name(row.get("moeda")) == code), 1):
                lines.extend(["", f"*Lançamento {index}*", f"• Número: {row.get('numero') or 'Não informado'}",
                              f"• Filial: {row.get('filial') or 'Não informada'}",
                              f"• Banco: {row.get('banco') or 'Não informado'}",
                              f"• Inclusão: {display_date(row.get('datainc'))}",
                              f"• Tipo: {row.get('tipo') or kind}", f"• Moeda: {code}"])
                for field, label in (("valor", "Valor"), ("saldo", "Saldo")):
                    lines.append(f"• {label}: {amount(row[field]) if row.get(field) not in (None, '') else 'Não informado'}")
                lines.extend([f"• Vencimento: {display_date(row.get('vencimento'))}",
                              f"• Taxa: {str(row['taxa']).replace('.', ',') if row.get('taxa') is not None else 'Não informada'}",
                              f"• Dias: {row.get('dias') if row.get('dias') is not None else 'Não informado'}",
                              f"• Juros: {amount(row['juros']) if row.get('juros') not in (None, '') else 'Não informado'}",
                              f"• Total: {amount(row['total'])}", SEPARATOR])
        blocks.append("\n".join(lines))
    if not detail and found:
        blocks.append(DETAIL_QUESTION)
    return "\n\n".join(blocks)


def snapshot_key(session_id):
    return f"apl_emp_consulta:{session_id}"


def snapshot_cache():
    import redis
    from app.core.config import settings
    return redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)


def save_snapshot(session_id, snapshot):
    if session_id:
        snapshot_cache().setex(snapshot_key(session_id), 3600, json.dumps(snapshot, ensure_ascii=False, default=str))


def load_snapshot(session_id):
    raw = snapshot_cache().get(snapshot_key(session_id)) if session_id else None
    return json.loads(raw) if raw else None
