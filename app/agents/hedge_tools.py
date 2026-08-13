"""Estado e regras determinísticas do fluxo de Hedge de bolsa."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Optional, Tuple

import redis

from app.core.config import settings


class HedgeTools:
    MONTHS = {
        "mar": "MAR", "marco": "MAR",
        "mai": "MAI", "maio": "MAI",
        "jul": "JUL", "julho": "JUL",
        "set": "SET", "setembro": "SET",
        "dez": "DEZ", "dezembro": "DEZ",
    }
    ACCOUNTS = {
        "a13": ("A13", "Adm13"), "adm13": ("A13", "Adm13"),
        "rjo": ("RJO", "RJObrien"), "rjobrien": ("RJO", "RJObrien"),
        "ndf": ("NDF", "NDF"), "a14": ("A14", "Adm14"), "adm14": ("A14", "Adm14"),
        "scd": ("SCD", "Sucden"), "sucden": ("SCD", "Sucden"),
        "hed": ("HED", "HedgePoint"), "hedgepoint": ("HED", "HedgePoint"),
        "mar": ("MAR", "Marex Fut"), "marexfut": ("MAR", "Marex Fut"),
        "mao": ("MAO", "Marex OTC"), "marexotc": ("MAO", "Marex OTC"),
        "fcs": ("FCS", "FCStone"), "fcstone": ("FCS", "FCStone"),
        "ice": ("ICE", "BTGPactual"), "btgpactual": ("ICE", "BTGPactual"),
    }
    REQUIRED = ("mesfix", "anofix", "lotes", "corret", "account", "lancaa")

    def __init__(self, session_id: str):
        self.key = f"hedge_pendente:{session_id}"

    @staticmethod
    def normalize(text: Any) -> str:
        value = unicodedata.normalize("NFKD", str(text or "").lower())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return re.sub(r'\s+', ' ', value).strip()

    def _redis(self):
        return redis.from_url(settings.redis_url, decode_responses=True)

    def load(self) -> Dict[str, Any]:
        raw = self._redis().get(self.key)
        return json.loads(raw) if raw else {}

    def save(self, data: Dict[str, Any]):
        self._redis().setex(self.key, 3600, json.dumps(data, ensure_ascii=False))

    def clear(self):
        self._redis().delete(self.key)

    def prepare_offer(self, contract: str, value: float):
        self.save({"stage": "offered", "tipo": "C", "operac": "FV", "valor": float(value), "ctrex": str(contract)})

    def start_collecting(self):
        data = self.load()
        data["stage"] = "collecting"
        self.save(data)

    def next_missing(self, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        current = data or self.load()
        return next((field for field in self.REQUIRED if field not in current), None)

    def parse_month(self, text: str) -> Optional[str]:
        normalized = self.normalize(text)
        for word, code in self.MONTHS.items():
            if re.search(rf'\b{re.escape(word)}\b', normalized):
                return code
        return None

    def parse_account(self, text: str, allow_descriptions: bool = False) -> Optional[Tuple[str, str]]:
        """Identifica a conta sem confundir mes ou corretora com uma conta."""
        normalized = self.normalize(text)
        compact = re.sub(r'[^a-z0-9]', '', normalized)

        codes = {value[0].lower(): value for value in self.ACCOUNTS.values()}
        for code, account in codes.items():
            if re.search(rf'(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])', normalized):
                return account

        has_account_context = bool(re.search(r'\b(?:conta|account)\b', normalized))
        safe_without_context = {
            "adm13", "rjobrien", "ndf", "adm14", "hedgepoint",
            "marexfut", "marexotc", "fcstone", "btgpactual",
        }
        for alias, account in self.ACCOUNTS.items():
            if alias == account[0].lower():
                continue
            if not (allow_descriptions or has_account_context or alias in safe_without_context):
                continue
            if alias == compact or alias in compact:
                return account
        return None

    def parse_known_broker(self, text: str) -> Optional[Tuple[str, str]]:
        """Resolve corretora exclusivamente pela lista fixa ACCOUNTS."""
        return self.parse_account(text, allow_descriptions=True)

    def remember_from_text(
        self,
        data: Dict[str, Any],
        text: str,
        expected: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Guarda campos de Hedge já mencionados, sem consultar API externa."""
        normalized = self.normalize(text)
        mentions_lots = bool(re.search(r'\b\d+\s*lotes?\b', normalized))
        mentions_fixation_month = bool(
            re.search(
                r'\bmes\s+(?:de\s+)?(?:marco|maio|julho|setembro|dezembro)\b',
                normalized,
            )
        )
        hedge_details_context = (
            "hedge" in normalized or mentions_lots or mentions_fixation_month
        )

        month = self.parse_month(text)
        if month and (
            expected == "mesfix"
            or hedge_details_context
            or re.search(r'\bmes(?:\s+da)?\s+fixacao\b', normalized)
        ):
            data["mesfix"] = month

        year_match = re.search(r'\b(20\d{2})\b', normalized)
        if year_match and (
            expected == "anofix"
            or hedge_details_context
            or re.search(r'\bano(?:\s+da)?\s+fixacao\b', normalized)
        ):
            data["anofix"] = year_match.group(1)

        lots_match = re.search(r'\b(\d+)\s*lotes?\b', normalized)
        if lots_match:
            data["lotes"] = int(lots_match.group(1))
        elif expected == "lotes" and re.fullmatch(r'\d+', normalized):
            data["lotes"] = int(normalized)

        account_context = re.search(r'\b(?:conta|account)\b', normalized)
        if expected == "account" or account_context:
            account_text = account_context.string[account_context.start():] if account_context else text
            account = self.parse_account(account_text, allow_descriptions=True)
            if account:
                data["account"], data["accountDescricao"] = account

        broker_context = re.search(r'\bcorret(?:ora)?\b', normalized)
        known_broker_hint = re.search(
            r'\b(?:na|pela|via)\s+'
            r'(?:adm13|rjobrien|ndf|adm14|sucden|hedgepoint|marex\s+fut|'
            r'marex\s+otc|fcstone|btgpactual|a13|rjo|a14|scd|hed|mar|mao|fcs|ice)\b',
            normalized,
        )
        if expected == "corret" or broker_context or known_broker_hint:
            context_match = broker_context or known_broker_hint
            broker_text = context_match.string[context_match.start():] if context_match else text
            broker_text = re.split(r'\b(?:conta|account)\b', broker_text, maxsplit=1)[0]
            broker = self.parse_known_broker(broker_text)
            if broker:
                data["corret"], data["corretDescricao"] = broker

        if "aa" in normalized:
            if re.search(r'\b(?:sim|com|s)\b', normalized):
                data["lancaa"] = "Sim"
            elif re.search(r'\b(?:nao|sem|n)\b', normalized):
                data["lancaa"] = "Nao"
        elif expected == "lancaa" and normalized in {"sim", "s", "nao", "n"}:
            data["lancaa"] = "Sim" if normalized in {"sim", "s"} else "Nao"

        return data

    def resolve_broker_from_message(self, informed: str, records: list) -> Optional[Tuple[str, str]]:
        """Encontra uma descricao ou codigo de corretora dentro de uma frase."""
        normalized = self.normalize(informed)
        compact = re.sub(r'[^a-z0-9]', '', normalized)
        matches = []
        for record in records:
            code = str(record.get("codigo") or "").strip()
            description = str(record.get("descricao") or "").strip()
            if not code or not description:
                continue
            normalized_code = self.normalize(code)
            normalized_description = self.normalize(description)
            compact_description = re.sub(r'[^a-z0-9]', '', normalized_description)
            code_found = bool(re.search(
                rf'(?<![a-z0-9]){re.escape(normalized_code)}(?![a-z0-9])', normalized
            ))
            description_found = (
                normalized_description in normalized
                or (len(compact_description) >= 4 and compact_description in compact)
            )
            if code_found or description_found:
                matches.append((len(normalized_description), code, description))
        if not matches:
            return None
        _, code, description = max(matches)
        return code, description

    def resolve_broker(self, informed: str, records: list) -> Optional[Tuple[str, str]]:
        target = self.normalize(informed)
        best = None
        best_score = 0.0
        for record in records:
            code = str(record.get("codigo") or "").strip()
            description = str(record.get("descricao") or "").strip()
            if not code or not description:
                continue
            normalized_description = self.normalize(description)
            score = SequenceMatcher(None, target, normalized_description).ratio()
            if target in normalized_description or normalized_description in target:
                score = max(score, 0.95)
            if score > best_score:
                best_score = score
                best = (code, description)
        return best if best_score >= 0.55 else None

    def build_body(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        current = data or self.load()
        return {key: current[key] for key in ("tipo", "mesfix", "anofix", "lotes", "valor", "corret", "operac", "account", "lancaa", "ctrex")}

    def format_summary(self, data: Optional[Dict[str, Any]] = None) -> str:
        current = data or self.load()
        value = f"{float(current['valor']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return (
            "Resumo do Hedge:\n\n"
            f"Contrato: {current['ctrex']}\nValor: {value}\nTipo: C\n"
            f"Mês: {current['mesfix']}\nAno: {current['anofix']}\nLotes: {current['lotes']}\n"
            f"Corretora: {current.get('corretDescricao', current['corret'])} ({current['corret']})\n"
            f"Operação: FV\nConta: {current.get('accountDescricao', current['account'])} ({current['account']})\n"
            f"Lançamento com AA: {current['lancaa']}\n\nConfirma o envio do Hedge para a API?"
        )

    @staticmethod
    def question_for(field: str) -> str:
        questions = {
            "mesfix": "Qual é o mês da fixação do Hedge? Opções: março, maio, julho, setembro ou dezembro.",
            "anofix": "Qual é o ano da fixação do Hedge?",
            "lotes": "Quantos lotes deseja lançar no Hedge?",
            "corret": "Qual é a corretora da bolsa?",
            "account": "Qual conta deseja usar? Opções: Adm13, RJObrien, NDF, Adm14, Sucden, HedgePoint, Marex Fut, Marex OTC, FCStone ou BTGPactual.",
            "lancaa": "O lançamento será com AA? Responda sim ou não.",
        }
        return questions[field]
