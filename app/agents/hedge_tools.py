"""Estado e regras determinísticas do fluxo de Hedge de bolsa."""
import json
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import Any, Dict, Optional, Tuple

import redis

from app.core.config import settings
from app.core.database import sql_client


logger = logging.getLogger(__name__)


class HedgeTools:
    MONTHS = {
        "mar": "MAR", "marco": "MAR",
        "mai": "MAI", "maio": "MAI",
        "jul": "JUL", "julho": "JUL",
        "set": "SET", "setembro": "SET",
        "dez": "DEZ", "dezembro": "DEZ",
    }
    MONTH_NUMBERS = {
        "03": "MAR", "05": "MAI", "07": "JUL", "09": "SET", "12": "DEZ",
    }
    MONTH_NAMES = {
        "MAR": "março", "MAI": "maio", "JUL": "julho",
        "SET": "setembro", "DEZ": "dezembro",
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
        data = {
            "stage": "offered", "tipo": "C", "operac": "FV",
            "valor": float(value), "ctrex": str(contract),
        }
        recommendation = self.recommend_lots(contract)
        if recommendation:
            data.update(recommendation)
        self.save(data)

    @staticmethod
    def recommend_lots(contract: str) -> Optional[Dict[str, Any]]:
        """Sugere lotes e mês/ano usando a mesma consulta do contrato."""
        try:
            rows = sql_client.execute_procedure(
                "usp_IA_Vendas", {"Contrato": str(contract).strip()}
            )
            candidates = []
            for row in rows or []:
                raw = next(
                    (value for key, value in row.items() if str(key).lower() == "sacas"),
                    None,
                )
                if raw is None:
                    continue
                quantity = Decimal(str(raw).replace(",", "."))
                if quantity > 0:
                    candidates.append((quantity, row))
            if not candidates:
                logger.warning(
                    "[HEDGE] Contrato %s sem quantidade de sacas para recomendacao",
                    contract,
                )
                return None

            # A procedure pode repetir o total do contrato em mais de uma linha;
            # por isso usamos a maior quantidade encontrada, sem somar duplicatas.
            sacks, reference_row = max(candidates, key=lambda item: item[0])
            lots = int(
                (sacks / Decimal("288.300235169045")).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            result = {"sacasContrato": float(sacks), "lotesRecomendados": lots}

            raw_fixation_month = next(
                (
                    value for key, value in reference_row.items()
                    if str(key).lower() in {
                        "mesfixacao", "mesfix", "mesfixacaobolsa", "mesanofixacao"
                    }
                    and value not in (None, "")
                ),
                None,
            )
            fixation_digits = re.sub(r'\D', '', str(raw_fixation_month or ""))
            if len(fixation_digits) == 6:
                if fixation_digits[:4].startswith("20"):
                    year, month_number = fixation_digits[:4], fixation_digits[4:]
                else:
                    month_number, year = fixation_digits[:2], fixation_digits[2:]
                month_code = HedgeTools.MONTH_NUMBERS.get(month_number)
                if month_code:
                    result.update({
                        "mesfixRecomendado": month_code,
                        "anofixRecomendado": year,
                    })

            logger.info(
                "[HEDGE] Recomendacao para contrato %s: %s sacas = %s lotes; "
                "vencimento=%s/%s",
                contract, sacks, lots,
                result.get("mesfixRecomendado"), result.get("anofixRecomendado"),
            )
            return result
        except (InvalidOperation, TypeError, ValueError) as exc:
            logger.warning("[HEDGE] Quantidade invalida no contrato %s: %s", contract, exc)
        except Exception as exc:
            # A consulta auxiliar nunca deve transformar uma fixacao bem-sucedida
            # em erro; o fluxo apenas segue sem a recomendacao.
            logger.exception("[HEDGE] Falha ao calcular lotes para %s: %s", contract, exc)
        return None

    @staticmethod
    def recommendation_message(data: Dict[str, Any]) -> str:
        lots = data.get("lotesRecomendados")
        month = data.get("mesfixRecomendado")
        year = data.get("anofixRecomendado")
        if lots is None and not (month and year):
            return ""
        suggestions = []
        if lots is not None:
            suggestions.append(f"Quantidade de lotes recomendada: {lots} lotes")
        if month and year:
            month_name = HedgeTools.MONTH_NAMES.get(month, month)
            suggestions.append(f"Mês/ano de fixação recomendado: {month_name}/{year}")
        return (
            "\n\n" + "\n".join(suggestions) + ". "
            "Você pode informar outros dados; nos campos que não informar, usarei essas recomendações."
        )

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
        if not year_match and month:
            short_year_match = re.search(
                r'\b(?:mar(?:co)?|mai(?:o)?|jul(?:ho)?|set(?:embro)?|dez(?:embro)?)'
                r'\s*(?:/|-|de)?\s*(\d{2})\b',
                normalized,
            )
            if short_year_match:
                year_match = short_year_match
        if year_match and (
            expected == "anofix"
            or hedge_details_context
            or re.search(r'\bano(?:\s+da)?\s+fixacao\b', normalized)
        ):
            informed_year = year_match.group(1)
            data["anofix"] = informed_year if len(informed_year) == 4 else f"20{informed_year}"

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
                data["corret"], data["corretDescricao"] = account

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
                # Regra do fluxo Z03: a opção escolhida como corretora também
                # deve ser enviada no campo account.
                data["account"], data["accountDescricao"] = broker

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
        broker_options = (
            "Adm13, RJObrien, NDF, Adm14, Sucden, HedgePoint, "
            "Marex Fut, Marex OTC, FCStone ou BTGPactual"
        )
        questions = {
            "mesfix": "Qual é o mês da fixação do Hedge? Opções: março, maio, julho, setembro ou dezembro.",
            "anofix": "Qual é o ano da fixação do Hedge?",
            "lotes": "Quantos lotes deseja lançar no Hedge?",
            "corret": f"Qual é a corretora da bolsa? Opções: {broker_options}.",
            # Compatibilidade com estados antigos que possam ter corretora sem
            # account: pergunta novamente pela corretora e sincroniza ambos.
            "account": f"Qual é a corretora da bolsa? Opções: {broker_options}.",
            "lancaa": "O lançamento será com AA? Responda sim ou não.",
        }
        return questions[field]
