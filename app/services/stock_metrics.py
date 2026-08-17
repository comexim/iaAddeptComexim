"""Regras determinísticas para métricas e snapshots de estoque e Long/Short."""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Tuple


CERTIFICATE_ALIASES = {
    "RF": "RF",
    "4 C": "4C",
    "4C": "4C",
    "GC": "GC",
    "GCP": "GCP",
    "GT": "GT",
    "CP": "CP",
    "FT": "FT",
}

DEFAULT_KG_PER_SACK = Decimal("60")


def normalize_certificate(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = " ".join(text.split())
    return CERTIFICATE_ALIASES.get(text, text or "SEM CERTIFICADO")


def certificate_matches(row_value: Any, requested: str) -> bool:
    return normalize_certificate(row_value) == normalize_certificate(requested)


def detect_certificate_from_query(query: str) -> str | None:
    text = f" {str(query or '').upper()} "
    if "RAINFOREST" in text:
        return "RF"

    normalized = text.replace("-", " ").replace("_", " ")
    tokens = set(normalized.split())
    for certificate in ("RF", "4C", "GC", "GCP", "GT", "CP", "FT"):
        if certificate in tokens:
            return certificate
    if "4 C" in normalized:
        return "4C"
    return None


def metric_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def snapshot_fingerprint(rows: Iterable[Dict[str, Any]]) -> str:
    """Assinatura estável do retorno bruto para comparar execuções próximas."""
    payload = json.dumps(
        list(rows),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def deduplicate_stock_rows(
    rows: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Remove apenas linhas integralmente idênticas retornadas no mesmo snapshot."""
    unique = []
    seen = set()
    duplicates = 0
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(row)
    return unique, duplicates


def analyze_stock_weight_composition(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Distingue peso real de conversão e identifica fatores/unidades mistos."""
    compositions = defaultdict(lambda: {
        "registros": 0, "sacas": Decimal("0"), "peso_kg": Decimal("0")
    })
    real_weight = Decimal("0")
    sacks_with_real_weight = Decimal("0")
    sacks_without_weight = Decimal("0")
    rows_with_real_weight = 0
    rows_without_weight = 0

    for row in rows:
        weight = metric_decimal(row.get("peso"))
        sacks = metric_decimal(row.get("sacas"))
        explicit_unit = next(
            (
                str(value).strip()
                for field, value in row.items()
                if str(field).replace("_", "").lower()
                in {"unidade", "embalagem", "tipoembalagem", "unidademedida"}
                and value not in (None, "")
            ),
            "",
        )
        if weight > 0:
            rows_with_real_weight += 1
            real_weight += weight
            sacks_with_real_weight += sacks
            if sacks > 0:
                ratio = weight / sacks
                nearest = min(
                    (Decimal("50"), Decimal("59"), Decimal("60"), Decimal("1000")),
                    key=lambda candidate: abs(candidate - ratio),
                )
                tolerance = Decimal("10") if nearest == 1000 else Decimal("0.75")
                factor_label = (
                    f"aprox. {nearest} kg/{'unidade' if explicit_unit and nearest == 1000 else 'saca'}"
                    if abs(nearest - ratio) <= tolerance
                    else "peso real variável"
                )
            else:
                factor_label = "peso real sem quantidade de sacas"
            label = f"{explicit_unit} — {factor_label}" if explicit_unit else factor_label
            compositions[label]["registros"] += 1
            compositions[label]["sacas"] += sacks
            compositions[label]["peso_kg"] += weight
        else:
            rows_without_weight += 1
            sacks_without_weight += sacks
            label = f"{explicit_unit} — sem peso real" if explicit_unit else "sem peso real"
            compositions[label]["registros"] += 1
            compositions[label]["sacas"] += sacks

    effective_factor = real_weight / sacks_with_real_weight if sacks_with_real_weight > 0 else None
    return {
        "peso_real_kg": real_weight,
        "sacas_com_peso_real": sacks_with_real_weight,
        "sacas_sem_peso_real": sacks_without_weight,
        "peso_estimado_kg": sacks_without_weight * DEFAULT_KG_PER_SACK,
        "fator_padrao_kg_por_saca": DEFAULT_KG_PER_SACK,
        "fator_efetivo_kg_por_saca": effective_factor,
        "registros_com_peso_real": rows_with_real_weight,
        "registros_sem_peso_real": rows_without_weight,
        "misto": len(compositions) > 1,
        "itens": [
            {"tipo": label, **values}
            for label, values in sorted(compositions.items())
        ],
    }


def convert_weight_sacks(
    value: Any,
    *,
    from_unit: str,
    kg_per_sack: Decimal = DEFAULT_KG_PER_SACK,
) -> Dict[str, Any]:
    """Conversão padrão explícita para quando não há peso real disponível."""
    quantity = metric_decimal(value)
    normalized_unit = str(from_unit).strip().lower()
    if normalized_unit in {"saca", "sacas", "sc"}:
        return {
            "origem": "sacas", "destino": "kg", "entrada": quantity,
            "resultado": quantity * kg_per_sack,
            "fator_kg_por_saca": kg_per_sack,
        }
    if normalized_unit in {"kg", "quilo", "quilos", "quilograma", "quilogramas"}:
        return {
            "origem": "kg", "destino": "sacas", "entrada": quantity,
            "resultado": quantity / kg_per_sack if kg_per_sack else Decimal("0"),
            "fator_kg_por_saca": kg_per_sack,
        }
    raise ValueError(f"Unidade de origem não suportada: {from_unit}")


def format_standard_weight_conversion(query: str) -> str | None:
    """Reconhece conversões numéricas explícitas e sempre declara o fator."""
    normalized = unicodedata.normalize("NFKD", str(query or "").lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    match = re.search(
        r"(?<!\d)(\d[\d.,]*)\s*(sacas?|sc|kg|quilos?|quilogramas?)\b",
        normalized,
    )
    if not match:
        return None
    source_unit = match.group(2)
    asks_conversion = any(
        term in normalized
        for term in ("equivale", "equivalem", "converter", "converta", "em kg", "em quilo", "em saca")
    )
    if not asks_conversion:
        return None
    number_text = match.group(1)
    if "," in number_text and "." in number_text:
        number_text = number_text.replace(".", "").replace(",", ".")
    elif "," in number_text:
        number_text = number_text.replace(",", ".")
    conversion = convert_weight_sacks(number_text, from_unit=source_unit)
    def pt_br(value: Any) -> str:
        formatted = f"{metric_decimal(value):,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    if conversion["destino"] == "kg":
        return (
            f"{pt_br(conversion['entrada'])} sacas equivalem a "
            f"{pt_br(conversion['resultado'])} kg usando o fator padrão de "
            f"{conversion['fator_kg_por_saca']} kg por saca. "
            "Esse cálculo é uma conversão padrão; se houver peso real do lote no banco, "
            "o peso real deve prevalecer."
        )
    return (
        f"{pt_br(conversion['entrada'])} kg equivalem a "
        f"{pt_br(conversion['resultado'])} sacas usando o fator padrão de "
        f"{conversion['fator_kg_por_saca']} kg por saca. "
        "Esse cálculo é uma conversão padrão; se houver peso real do lote no banco, "
        "o peso real deve prevalecer."
    )


def build_stock_snapshot(rows: Iterable[Dict[str, Any]], group_by: str = "linha") -> Dict[str, Any]:
    """Calcula totais e grupos de estoque a partir de um único retorno SQL."""
    source_rows = list(rows)
    unique_rows, duplicates = deduplicate_stock_rows(source_rows)
    groups = defaultdict(lambda: {
        "sacas_total": Decimal("0"),
        "sacas_consumo": Decimal("0"),
        "sacas_exportacao": Decimal("0"),
        "peso_kg": Decimal("0"),
        "lotes": set(),
        "filiais": set(),
        "armazens": set(),
        "registros": 0,
    })
    global_lots = set()
    rows_with_lot = 0

    for row in unique_rows:
        if group_by == "certificado":
            key = normalize_certificate(row.get("certificado"))
        else:
            key = str(row.get("linha") or "SEM LINHA").strip() or "SEM LINHA"
        item = groups[key]
        item["sacas_total"] += metric_decimal(row.get("sacas"))
        item["sacas_consumo"] += metric_decimal(row.get("sacasConsumo"))
        item["sacas_exportacao"] += metric_decimal(row.get("sacasExportacao"))
        item["peso_kg"] += metric_decimal(row.get("peso"))
        item["registros"] += 1

        filial = str(row.get("filial") or "").strip()
        warehouse = str(row.get("armazem") or "").strip()
        lot = str(row.get("lote") or "").strip()
        if filial:
            item["filiais"].add(filial)
        if warehouse:
            item["armazens"].add(warehouse)
        if lot:
            rows_with_lot += 1
            lot_key = (filial, warehouse, lot)
            item["lotes"].add(lot_key)
            global_lots.add(lot_key)

    formatted_groups = []
    for key, item in groups.items():
        formatted_groups.append({
            group_by: key,
            "sacas_total": item["sacas_total"],
            "sacas_consumo": item["sacas_consumo"],
            "sacas_exportacao": item["sacas_exportacao"],
            "peso_kg": item["peso_kg"],
            "qtd_lotes": len(item["lotes"]),
            "qtd_registros": item["registros"],
            "filiais": ", ".join(sorted(item["filiais"])) or "N/A",
            "armazens": ", ".join(sorted(item["armazens"])) or "N/A",
        })
    formatted_groups.sort(key=lambda item: item["sacas_total"], reverse=True)

    return {
        "linhas_recebidas": len(source_rows),
        "linhas_unicas": len(unique_rows),
        "duplicatas_exatas": duplicates,
        "repeticoes_chave_lote": rows_with_lot - len(global_lots),
        "total_sacas": sum((metric_decimal(row.get("sacas")) for row in unique_rows), Decimal("0")),
        "sacas_consumo": sum((metric_decimal(row.get("sacasConsumo")) for row in unique_rows), Decimal("0")),
        "sacas_exportacao": sum((metric_decimal(row.get("sacasExportacao")) for row in unique_rows), Decimal("0")),
        "peso_kg": sum((metric_decimal(row.get("peso")) for row in unique_rows), Decimal("0")),
        "total_lotes": len(global_lots),
        "grupos": formatted_groups,
        "composicao_peso": analyze_stock_weight_composition(unique_rows),
    }


def _normalize_field(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text)


LONGSHORT_FIELDS = {
    "net_position": ("netPosition",),
    "total_estoque_exportacao": (
        "totalEstoqueExportacao", "totalEstoque", "estoqueTotalExportacao", "estoqueExportacao"
    ),
    "vendas_exportacao": ("vendasExportacao", "vendasTotaisExportacao", "totalVendasExportacao"),
    "basis_exportacao": ("basisExportacao", "basisSaldoSacas", "basisSaldo", "saldoBasisSacas", "basisSacas"),
    "mercado_a_fixar": ("mercadoAFixar", "vendasMercadoAFixar", "vendasMercadoFixar", "vendaMercadoAFixar"),
    "mercado_fixadas": ("mercadoFixadas", "vendasFixadas", "totalVendasFixadas", "vendaFixada"),
    "mercado_a_fixar_embarcadas": (
        "mercadoAfixarEmbarcadas", "vendasAFixarEmbarcadas", "vendasFixarEmbarcadas", "vendaAFixarEmbarcada"
    ),
    "bolsa_lotes": ("bolsaLotes", "lotesBolsa", "totalLotesBolsa"),
    "bolsa_sacas": ("bolsaSacas", "sacasBolsa", "totalSacasBolsa"),
}


def build_longshort_snapshot(row: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai todos os componentes exclusivamente da mesma linha SQL."""
    normalized = {_normalize_field(key): value for key, value in row.items()}
    snapshot = {}
    for output_field, aliases in LONGSHORT_FIELDS.items():
        snapshot[output_field] = next(
            (
                normalized[_normalize_field(alias)]
                for alias in aliases
                if _normalize_field(alias) in normalized
                and normalized[_normalize_field(alias)] is not None
            ),
            None,
        )
    return snapshot


def format_longshort_snapshot(snapshot: Dict[str, Any]) -> str:
    """Aplica o quadro comercial oficial sem participação do modelo."""
    def number(value: Any, decimals: int = 0) -> str:
        if value is None:
            return "Não informado"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        formatted = f"{numeric:,.{decimals}f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return (
        "Claro! Segue a posição Long/Short atual:\n\n"
        f"Posição Net LS = {number(snapshot['net_position'])} sacas\n"
        f"Estoque Total Exportação: {number(snapshot['total_estoque_exportacao'])}\n"
        f"Vendas Totais Exportação: {number(snapshot['vendas_exportacao'])}\n\n"
        f"Basis Saldo Sacas: {number(snapshot['basis_exportacao'])}\n"
        f"Vendas Mercado A fixar: {number(snapshot['mercado_a_fixar'])}\n"
        f"Vendas Fixadas: {number(snapshot['mercado_fixadas'])}\n"
        f"Vendas A Fixar Embarcadas: {number(snapshot['mercado_a_fixar_embarcadas'])}\n"
        f"Bolsa Lotes: {number(snapshot['bolsa_lotes'])} lotes / "
        f"{number(snapshot['bolsa_sacas'])} Sacas\n\n"
        "Se quiser, também posso detalhar essa posição por filial: COBRA, CUSA ou CEU."
    )
