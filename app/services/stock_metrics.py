"""Regras determinísticas para métricas e filtros de estoque."""

from typing import Any


CERTIFICATE_ALIASES = {
    "RAINFOREST": "RF",
    "RF": "RF",
    "4 C": "4C",
    "4C": "4C",
    "GC": "GC",
    "GCP": "GCP",
    "GT": "GT",
    "CP": "CP",
    "FT": "FT",
}


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
