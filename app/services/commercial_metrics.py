"""Métricas determinísticas para consultas comerciais.

Este módulo não conhece LLM nem WhatsApp. Ele recebe linhas retornadas pelo
banco e calcula totais sem misturar o esquema de vendas com o de compras.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

SALES_BRANCHES = {
    "05": "COBRA",
    "60": "CUSA",
    "61": "CEU",
}

WEEKDAYS_PT = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}


def parse_last_weekday_date(expression: Any, today: date | datetime) -> Optional[str]:
    """Resolve 'última quinta-feira' como a ocorrência anterior, em YYYYMMDD."""
    text = normalize_text(expression).replace("-", " ")
    if not any(term in text for term in ("ultima", "ultimo", "passada", "passado")):
        return None
    current = today.date() if isinstance(today, datetime) else today
    for weekday_name, weekday_number in WEEKDAYS_PT.items():
        if weekday_name not in text:
            continue
        days_back = (current.weekday() - weekday_number) % 7
        if days_back == 0:
            days_back = 7
        return (current - timedelta(days=days_back)).strftime("%Y%m%d")
    return None


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def format_pt_br(value: Any, decimals: int = 2) -> str:
    number = _decimal(value)
    formatted = f"{number:,.{decimals}f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


def normalize_currency(value: Any) -> str:
    text = str(value or "").strip().upper()
    aliases = {
        "R$": "BRL",
        "REAL": "BRL",
        "REAIS": "BRL",
        "US$": "USD",
        "DOLAR": "USD",
        "DÓLAR": "USD",
        "DOLARES": "USD",
        "DÓLARES": "USD",
        "€": "EUR",
        "EURO": "EUR",
        "EUROS": "EUR",
    }
    return aliases.get(text, text if text in {"BRL", "USD", "EUR"} else "N/I")


def row_currency(row: Dict[str, Any]) -> str:
    for field in ("moeda", "currency", "moedaContrato", "moedaFixacao"):
        if row.get(field) not in (None, ""):
            return normalize_currency(row[field])
    # Regra de negócio das compras: quando a origem não envia a moeda,
    # os valores devem ser tratados como reais.
    return "BRL"


def normalize_text(value: Any) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def sales_branch_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return digits.zfill(2)[-2:]

    normalized = normalize_text(text)
    for code, name in SALES_BRANCHES.items():
        if normalized == normalize_text(name):
            return code
    return text or "N/I"


def sales_branch_name(value: Any) -> str:
    code = sales_branch_code(value)
    return SALES_BRANCHES.get(code, f"FILIAL {code}" if code != "N/I" else "SEM FILIAL")


def detect_sales_branch_from_query(query: str) -> str | None:
    normalized = f" {normalize_text(query)} "
    for code, name in SALES_BRANCHES.items():
        if normalize_text(name) in normalized:
            return code
        if f" filial {int(code)} " in normalized or f" filial {code} " in normalized:
            return code
    return None


def filter_sales_by_branch(rows: Iterable[Dict[str, Any]], branch_code: str) -> List[Dict[str, Any]]:
    normalized_code = sales_branch_code(branch_code)
    return [row for row in rows if sales_branch_code(row.get("filial")) == normalized_code]


def row_market(row: Dict[str, Any]) -> str:
    for field in ("MERCADO", "mercado", "Mercado"):
        if row.get(field) not in (None, ""):
            return normalize_text(row[field]).upper()
    return ""


def filter_sales_by_market(rows: Iterable[Dict[str, Any]], market: str) -> List[Dict[str, Any]]:
    market_normalized = normalize_text(market).upper()
    if market_normalized == "INTERNO":
        return [
            row for row in rows
            if row_market(row) == "INTERNO"
        ]
    if market_normalized == "EXTERNO":
        return [
            row for row in rows
            if row_market(row) == "EXTERNO"
        ]
    return list(rows)


def aggregate_sales_by_branch(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrega vendas por filial/empresa usando linhas de contrato, com valorTotal em USD."""
    unique: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        contract = str(row.get("contrato") or index).strip()
        branch = sales_branch_code(row.get("filial"))
        client = str(row.get("cliente") or "").strip()
        key = f"{contract}|{branch}|{client}"
        unique.setdefault(key, row)

    totals = defaultdict(lambda: {
        "contratos": 0,
        "sacas": Decimal("0"),
        "valor_usd": Decimal("0"),
        "clientes": set(),
    })

    for row in unique.values():
        code = sales_branch_code(row.get("filial"))
        item = totals[code]
        item["contratos"] += 1
        item["sacas"] += _decimal(row.get("sacas"))
        item["valor_usd"] += _decimal(row.get("valorTotal"))
        if row.get("cliente"):
            item["clientes"].add(str(row["cliente"]).strip())

    result = []
    for code, values in totals.items():
        result.append({
            "filial": code,
            "empresa": SALES_BRANCHES.get(code, f"FILIAL {code}" if code != "N/I" else "SEM FILIAL"),
            "contratos": values["contratos"],
            "sacas": float(values["sacas"]),
            "valor_usd": float(values["valor_usd"]),
            "clientes": len(values["clientes"]),
        })

    result.sort(key=lambda item: item["sacas"], reverse=True)
    return result


def aggregate_sales_totals(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega totais de vendas por contrato, com valorTotal em USD."""
    unique: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        contract = str(row.get("contrato") or index).strip()
        branch = sales_branch_code(row.get("filial"))
        client = str(row.get("cliente") or "").strip()
        key = f"{contract}|{branch}|{client}"
        unique.setdefault(key, row)

    total_sacas = Decimal("0")
    total_value_usd = Decimal("0")
    clients = set()

    for row in unique.values():
        total_sacas += _decimal(row.get("sacas"))
        total_value_usd += _decimal(row.get("valorTotal"))
        if row.get("cliente"):
            clients.add(str(row["cliente"]).strip())

    return {
        "contratos": len(unique),
        "sacas": float(total_sacas),
        "valor_usd": float(total_value_usd),
        "clientes": len(clients),
    }


def aggregate_purchases(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega cada registro retornado pelo esquema de compras.

    O número do pedido não é uma chave única confiável: a procedure pode
    devolver várias linhas legítimas com o mesmo ``numero``. Portanto, uma
    linha só poderia ser eliminada se a fonte fornecesse uma chave técnica
    inequívoca; na ausência dela, todos os registros devem ser preservados.
    """
    source_rows = list(rows)

    totals_by_currency = defaultdict(lambda: {"value": Decimal("0"), "quantity": Decimal("0")})
    suppliers = defaultdict(lambda: {
        "value": Decimal("0"), "quantity": Decimal("0"),
        "weight": Decimal("0"), "contracts": 0,
    })
    total_weight = Decimal("0")

    for row in source_rows:
        currency = row_currency(row)
        value = _decimal(row.get("valor") or row.get("valorTotal") or row.get("valorContrato"))
        quantity = _decimal(row.get("sacas") or row.get("quantidade") or row.get("qtd"))
        weight = _decimal(row.get("peso") or row.get("pesoKg") or row.get("peso_kg"))
        supplier = str(row.get("fornecedor") or row.get("produtor") or "SEM FORNECEDOR").strip()

        totals_by_currency[currency]["value"] += value
        totals_by_currency[currency]["quantity"] += quantity
        suppliers[supplier]["value"] += value
        suppliers[supplier]["quantity"] += quantity
        suppliers[supplier]["weight"] += weight
        suppliers[supplier]["contracts"] += 1
        total_weight += weight

    currency_totals: List[Dict[str, Any]] = []
    for currency in sorted(totals_by_currency):
        item = totals_by_currency[currency]
        weighted_average = item["value"] / item["quantity"] if item["quantity"] else None
        currency_totals.append(
            {
                "moeda": currency,
                "valor_total": float(item["value"]),
                "quantidade_total": float(item["quantity"]),
                "media_ponderada": float(weighted_average) if weighted_average is not None else None,
            }
        )

    supplier_totals = [
        {
            "fornecedor": supplier,
            "contratos": values["contracts"],
            "quantidade": float(values["quantity"]),
            "peso_kg": float(values["weight"]),
            "valor": float(values["value"]),
        }
        for supplier, values in suppliers.items()
    ]
    supplier_totals.sort(key=lambda item: abs(item["valor"]), reverse=True)

    return {
        "total_contratos": len(source_rows),
        "peso_total_kg": float(total_weight),
        "kg_por_saca_real": (
            float(total_weight / sum(
                (item["quantity"] for item in totals_by_currency.values()),
                Decimal("0"),
            ))
            if total_weight and any(item["quantity"] for item in totals_by_currency.values())
            else None
        ),
        "totais_por_moeda": currency_totals,
        "fornecedores": supplier_totals,
    }


def aggregate_purchases_by_quality(
    rows: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Agrupa compras por ``linha`` e pondera o diferencial pelas sacas.

    Em compras, "qualidade" e "linha" são o mesmo critério de negócio para
    esta consulta. ``linha`` nunca representa a posição ordinal do registro.
    Cada registro permanece listado em ``contratos`` para que a composição da
    média possa ser conferida.
    """
    grouped = defaultdict(lambda: {
        "pedidos": 0,
        "sacas": Decimal("0"),
        "peso_kg": Decimal("0"),
        "sacas_consumo": Decimal("0"),
        "sacas_exportacao": Decimal("0"),
        "diferencial_vezes_sacas": Decimal("0"),
        "sacas_com_diferencial": Decimal("0"),
        "contratos": [],
    })

    for row in rows:
        quality = str(row.get("linha") or "NÃO INFORMADA").strip() or "NÃO INFORMADA"
        quantity = _decimal(row.get("sacas") or row.get("quantidade") or row.get("qtd"))
        weight = _decimal(row.get("peso") or row.get("pesoKg") or row.get("peso_kg"))
        raw_differential = row.get("diferencial")
        differential = None if raw_differential in (None, "") else _decimal(raw_differential)
        values = grouped[quality]
        values["pedidos"] += 1
        values["sacas"] += quantity
        values["peso_kg"] += weight
        values["sacas_consumo"] += _decimal(row.get("sacasConsumo"))
        values["sacas_exportacao"] += _decimal(row.get("sacasExportacao"))
        if differential is not None and quantity > 0:
            values["diferencial_vezes_sacas"] += differential * quantity
            values["sacas_com_diferencial"] += quantity

        identifier = str(
            row.get("numero") or row.get("solicitacao") or row.get("contrato") or "SEM IDENTIFICADOR"
        ).strip() or "SEM IDENTIFICADOR"
        values["contratos"].append({
            "identificador": identifier,
            "fornecedor": str(row.get("fornecedor") or "").strip(),
            "diferencial": float(differential) if differential is not None else None,
            "sacas": float(quantity),
            "peso_kg": float(weight),
        })

    result = []
    for quality, totals in grouped.items():
        weighted_average = (
            totals["diferencial_vezes_sacas"] / totals["sacas_com_diferencial"]
            if totals["sacas_com_diferencial"]
            else None
        )
        result.append({
            "linha": quality,
            "diferencial_medio_ponderado": (
                float(weighted_average) if weighted_average is not None else None
            ),
            "pedidos": totals["pedidos"],
            "sacas": float(totals["sacas"]),
            "peso_kg": float(totals["peso_kg"]),
            "sacas_consumo": float(totals["sacas_consumo"]),
            "sacas_exportacao": float(totals["sacas_exportacao"]),
            "contratos": totals["contratos"],
        })

    result.sort(key=lambda item: str(item["linha"]).casefold())
    return result


def normalize_month_key(value: Any) -> Optional[str]:
    """Normaliza datas usuais do Protheus para YYYY/MM, sem inferir valores."""
    if value in (None, ""):
        return None
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y/%m")

    import re

    text = str(value).strip()
    patterns = (
        r"^(20\d{2})[/-](0[1-9]|1[0-2])$",
        r"^(20\d{2})(0[1-9]|1[0-2])(?:[0-3]\d)?$",
        r"^(20\d{2})[/-](0[1-9]|1[0-2])[/-][0-3]\d$",
    )
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return None


def month_keys_between(start: Any, end: Any) -> List[str]:
    """Gera apenas os meses do intervalo explicitamente solicitado."""
    start_key = normalize_month_key(start)
    end_key = normalize_month_key(end)
    if not start_key or not end_key:
        return []

    year, month = map(int, start_key.split("/"))
    end_year, end_month = map(int, end_key.split("/"))
    if (year, month) > (end_year, end_month):
        return []

    result = []
    while (year, month) <= (end_year, end_month):
        result.append(f"{year:04d}/{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return result


def build_monthly_commercial_series(
    rows: Iterable[Dict[str, Any]],
    kind: str,
    expected_months: Optional[Iterable[str]] = None,
    date_fields: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Agrega somente meses existentes no banco e declara os meses ausentes."""
    rows_by_month: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    selected_date_fields = tuple(date_fields or (
        ("mesEmbarque", "mesembarque", "emissao")
        if kind == "sales"
        else ("emissao", "dataEmissao", "dataemissao")
    ))

    for row in rows:
        raw_date = next(
            (row.get(field) for field in selected_date_fields if row.get(field) not in (None, "")),
            None,
        )
        month = normalize_month_key(raw_date)
        if month:
            rows_by_month[month].append(row)

    months = []
    for month in sorted(rows_by_month):
        month_rows = rows_by_month[month]
        metrics = (
            aggregate_sales_totals(month_rows)
            if kind == "sales"
            else aggregate_purchases(month_rows)
        )
        months.append({"mes": month, **metrics})

    expected = list(dict.fromkeys(expected_months or []))
    present = set(rows_by_month)
    return {
        "meses_com_dados": months,
        "meses_sem_registros": [month for month in expected if month not in present],
    }


def reconcile_monthly_commercial_series(
    rows: Iterable[Dict[str, Any]],
    kind: str,
    series: Dict[str, Any],
    quantity_tolerance: Decimal = Decimal("0.01"),
    value_tolerance: Decimal = Decimal("0.01"),
) -> Dict[str, Any]:
    """Reconcilia total do conjunto com a soma da decomposição mensal."""
    source_rows = list(rows)
    months = series.get("meses_com_dados", [])

    if kind == "sales":
        aggregate = aggregate_sales_totals(source_rows)
        monthly = {
            "contratos": sum(int(item.get("contratos") or 0) for item in months),
            "sacas": sum((_decimal(item.get("sacas")) for item in months), Decimal("0")),
            "valor_usd": sum((_decimal(item.get("valor_usd")) for item in months), Decimal("0")),
        }
        aggregate_decimal = {
            "contratos": int(aggregate["contratos"]),
            "sacas": _decimal(aggregate["sacas"]),
            "valor_usd": _decimal(aggregate["valor_usd"]),
        }
        differences = {
            key: monthly[key] - aggregate_decimal[key]
            for key in ("contratos", "sacas", "valor_usd")
        }
        violations = []
        if differences["contratos"] != 0:
            violations.append("contratos")
        if abs(differences["sacas"]) > quantity_tolerance:
            violations.append("sacas")
        if abs(differences["valor_usd"]) > value_tolerance:
            violations.append("valor_usd")

        for item in months:
            if int(item.get("contratos") or 0) > aggregate_decimal["contratos"]:
                violations.append(f"mes_maior_contratos:{item['mes']}")
            if _decimal(item.get("sacas")) - aggregate_decimal["sacas"] > quantity_tolerance:
                violations.append(f"mes_maior_sacas:{item['mes']}")
            if _decimal(item.get("valor_usd")) - aggregate_decimal["valor_usd"] > value_tolerance:
                violations.append(f"mes_maior_valor:{item['mes']}")

        return {
            "valido": not violations,
            "agregado": aggregate_decimal,
            "soma_meses": monthly,
            "diferencas": differences,
            "violacoes": violations,
        }

    aggregate = aggregate_purchases(source_rows)
    aggregate_by_currency = {
        item["moeda"]: {
            "valor": _decimal(item["valor_total"]),
            "quantidade": _decimal(item["quantidade_total"]),
        }
        for item in aggregate["totais_por_moeda"]
    }
    monthly_by_currency = defaultdict(lambda: {
        "valor": Decimal("0"), "quantidade": Decimal("0")
    })
    monthly_contracts = 0
    for month in months:
        monthly_contracts += int(month.get("total_contratos") or 0)
        for item in month.get("totais_por_moeda", []):
            currency = item["moeda"]
            monthly_by_currency[currency]["valor"] += _decimal(item["valor_total"])
            monthly_by_currency[currency]["quantidade"] += _decimal(item["quantidade_total"])

    differences_by_currency = {}
    violations = []
    for currency in sorted(set(aggregate_by_currency) | set(monthly_by_currency)):
        aggregate_item = aggregate_by_currency.get(
            currency, {"valor": Decimal("0"), "quantidade": Decimal("0")}
        )
        monthly_item = monthly_by_currency.get(
            currency, {"valor": Decimal("0"), "quantidade": Decimal("0")}
        )
        differences_by_currency[currency] = {
            "valor": monthly_item["valor"] - aggregate_item["valor"],
            "quantidade": monthly_item["quantidade"] - aggregate_item["quantidade"],
        }
        if abs(differences_by_currency[currency]["valor"]) > value_tolerance:
            violations.append(f"valor:{currency}")
        if abs(differences_by_currency[currency]["quantidade"]) > quantity_tolerance:
            violations.append(f"quantidade:{currency}")

    contract_difference = monthly_contracts - int(aggregate["total_contratos"])
    if contract_difference != 0:
        violations.append("contratos")

    aggregate_contracts = int(aggregate["total_contratos"])
    for month in months:
        month_key = month.get("mes", "N/I")
        if int(month.get("total_contratos") or 0) > aggregate_contracts:
            violations.append(f"mes_maior_contratos:{month_key}")
        for item in month.get("totais_por_moeda", []):
            currency = item["moeda"]
            aggregate_item = aggregate_by_currency.get(
                currency, {"valor": Decimal("0"), "quantidade": Decimal("0")}
            )
            if _decimal(item.get("valor_total")) - aggregate_item["valor"] > value_tolerance:
                violations.append(f"mes_maior_valor:{month_key}:{currency}")
            if (
                _decimal(item.get("quantidade_total")) - aggregate_item["quantidade"]
                > quantity_tolerance
            ):
                violations.append(f"mes_maior_quantidade:{month_key}:{currency}")

    return {
        "valido": not violations,
        "agregado": {
            "contratos": int(aggregate["total_contratos"]),
            "por_moeda": aggregate_by_currency,
        },
        "soma_meses": {
            "contratos": monthly_contracts,
            "por_moeda": dict(monthly_by_currency),
        },
        "diferencas": {
            "contratos": contract_difference,
            "por_moeda": differences_by_currency,
        },
        "violacoes": violations,
    }
