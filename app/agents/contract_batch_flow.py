"""Fluxo persistente de fixação e Hedge em lote, sem decisões financeiras do LLM."""
import asyncio
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import logging
import math
import re
import time
import unicodedata
import uuid

import redis

from app.core.config import settings
from app.core.fixacao_api_client import fixacao_api_client, OperationNotSent, OperationRejected

logger = logging.getLogger(__name__)
_timers = set()
_process_id = uuid.uuid4().hex
_operations = {}
_exits = {}


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text).lower())
                   if not unicodedata.combining(c)).strip().rstrip(".! ")


def identifier(value, letter=None):
    """Não aceita código interno nem anos incompletos; conserva zeros e letra."""
    match = re.fullmatch(r"\s*([0-9]{1,3})\s*/\s*([0-9]{2})\s*([A-Z]?)\s*", str(value).strip().upper())
    if not match:
        raise ValueError("Informe numeroVenda no formato 999/99 e, se existir, uma letra maiúscula. Não informe contratodeVenda.")
    suffix = match[3]
    if letter is not None:
        letter = str(letter).strip().upper()
        if not re.fullmatch(r"[A-Z]?", letter) or (suffix and suffix != letter):
            raise ValueError("Confirme a letraVenda: deve ser uma única letra maiúscula ou vazia.")
        suffix = str(letter)
    return match[1].zfill(3) + "/" + match[2], suffix


def identity(item):
    if "numeroVenda" in item:
        number, letter = identifier(item["numeroVenda"], item.get("letraVenda"))
    elif "venda" in item:
        number, letter = identifier(item["venda"], item.get("letra", ""))
    else:
        number, letter = identifier(item.get("ctrex", item.get("contrato", "")))
    return number + letter


class ContractBatchFlow:
    SEPARATOR = "-----------------------------------------"
    LABELS = {"valorFixacao": "Valor da Fixação", "numeroVenda": "Venda", "letraVenda": "Letra",
              "fixacaoContrato": "Fixação do Contrato", "tipoValor": "Tipo Valor",
              "fixadorPreco": "Fixador do Preço", "diferencial": "Diferencial",
              "mesfix": "Mes Fix", "anofix": "Ano Fix", "lotes": "Lotes",
              "valor": "Valor", "corret": "Corretora", "lancaa": "Lanc. AA"}
    UNITS = {"C": "CTS/LB", "K": "KG", "5": "50 KG", "6": "59 KG", "T": "TON"}
    FIXERS = {"E": "Exportador", "I": "Importador", "F": "Fixador"}
    BLOCKED = {"sending_fix", "sending_hedge", "uncertain", "result_error"}
    RESULT_ERROR_MESSAGE = ("A CMX respondeu, mas houve um erro ao interpretar o retorno. "
                            "A resposta foi preservada para recuperação; nenhum item será reenviado. "
                            "Digite sair para encerrar a espera.")
    EXIT_MESSAGE = ("Espera encerrada. Você pode informar novamente os contratos para fixação. "
                    "A solicitação anterior pode ter sido processada no Protheus; confira antes de confirmar um novo envio.")
    YES = {"sim", "s", "ok", "confirmo", "sim confirmo", "sim, confirmo", "pode enviar"}
    NO = {"nao", "n", "agora nao", "nao quero"}
    FIX_FIELDS = ("valorFixacao", "diferencial", "tipoValor", "fixadorPreco")
    MOV_FIELDS = ("mesfix", "anofix", "lotes", "valor", "corret", "operac", "account", "ctrex", "tipo", "lancaa")

    def __init__(self, session_id, has_permission=False, notify=None):
        self.key = f"contratos_lote:{session_id}"
        self.has_permission = has_permission
        self.notify = notify

    def _redis(self):
        return redis.from_url(settings.redis_url, decode_responses=True)

    def load(self):
        raw = self._redis().get(self.key)
        return json.loads(raw) if raw else {}

    def save(self, data):
        # Mantém também o resultado consolidado para consulta no restante da conversa.
        self._redis().setex(self.key, 86400, json.dumps(data, ensure_ascii=False))

    def operation_key(self, operation_id):
        return f"{self.key}:operacao:{operation_id}"

    def read_operation(self, operation_id):
        raw = self._redis().get(self.operation_key(operation_id)) if operation_id else None
        return json.loads(raw) if raw else {}

    def save_operation(self, operation_id, record):
        self._redis().setex(self.operation_key(operation_id), 7 * 86400,
                            json.dumps(record, ensure_ascii=False))

    def release_lock(self, operation_id):
        # Uma resposta antiga nunca pode apagar a trava de uma nova tentativa.
        self._redis().eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1, self.key + ":envio", operation_id)

    def is_current(self, operation_id):
        current = self.load()
        return current.get("operation_id") == operation_id and current.get("stage") in self.BLOCKED

    def abandon(self, data):
        operation_id = data.get("operation_id")
        record = self.read_operation(operation_id)
        record.update(status="discarded", abandoned_at=time.time())
        data = deepcopy(data)
        data.update(stage="done", confirmation_id=uuid.uuid4().hex)
        data.pop("operation_id", None)
        if operation_id:
            if not self.commit_operation(operation_id, data, record):
                return "A operação já foi atualizada. Confira o resultado antes de iniciar uma nova fixação."
        else:
            self.save(data)
            self.release_lock("1")  # Compatibilidade com travas anteriores.
        event = _exits.get((self.key, operation_id))
        if event:
            event.set()
        return self.EXIT_MESSAGE

    @classmethod
    def is_pending_message(cls, message):
        value = normalized(message)
        # Consultas continuam disponíveis, inclusive as que citam contratos.
        if re.search(r"\b(?:qual|quais|consultar|consulte|consulta|listar|liste|mostre|mostrar|verificar)\b", value):
            return bool(re.search(r"\b(?:resultado|status|pendencia)\b.*\b(?:fixacao|hedge|operacao|envio)\b", value))
        return (value in cls.YES | cls.NO or cls.is_request(message)
                or bool(re.search(r"\b(?:hedge|enviar|envie|reenviar|reenvio|resultado|pendencia)\b", value))
                or value == "status"
                or bool(re.search(r"[0-9]+\s*/\s*[0-9]+", value)))

    async def recover(self, data):
        """Recupera somente evidência persistida; nunca consulta nem reenvia à CMX."""
        operation_id = data.get("operation_id")
        record = self.read_operation(operation_id)
        if record.get("status") in {"received", "applied"} and "result" in record:
            return await self.complete_operation(data, record["result"], record.get("hedge", False))
        if record.get("status") == "not_sent":
            data["stage"] = "confirm_hedge" if record.get("hedge") else "confirm_fix"
            data["confirmation_id"] = uuid.uuid4().hex
            if not self.commit_operation(operation_id, data, record):
                return ""
            return "A operação não foi efetivada. Confirme novamente para realizar uma nova tentativa."
        if data.get("stage", "").startswith("sending_") and data.get("process_id") != _process_id:
            data["stage"] = "uncertain"
            if operation_id:
                self.commit_operation(operation_id, data, record)
            else:
                self.save(data)
        return None

    async def complete_operation(self, data, result, hedge):
        operation_id = data["operation_id"]
        if not self.is_current(operation_id):
            return ""
        # Trabalha numa cópia: erros de interpretação não corrompem os acumulados.
        updated = deepcopy(data)
        try:
            output = await self.apply_result(updated, result, hedge, persist=False)
        except Exception as exc:
            logger.exception("Resposta do lote recebida, mas não pôde ser interpretada")
            record = self.read_operation(operation_id)
            record["processing_error"] = str(exc)
            failed = deepcopy(data)
            failed["stage"] = "result_error"
            if not self.commit_operation(operation_id, failed, record):
                return ""
            return self.RESULT_ERROR_MESSAGE
        record = self.read_operation(operation_id)
        record.update(status="applied")
        record.pop("processing_error", None)
        # Confere e grava atomicamente, inclusive se "sair" chegar em outro worker.
        committed = self.commit_operation(operation_id, updated, record)
        if not committed:
            return ""
        if updated["stage"] in {"list_fix", "list_hedge"}:
            self.schedule_list_timeout(updated, hedge)
        return output

    def commit_operation(self, operation_id, updated, record):
        return self._redis().eval(
            "local raw = redis.call('get', KEYS[1]); if not raw then return 0 end; "
            "local current = cjson.decode(raw); "
            "if current.operation_id ~= ARGV[1] or "
            "(current.stage ~= 'sending_fix' and current.stage ~= 'sending_hedge' "
            "and current.stage ~= 'uncertain' and current.stage ~= 'result_error') "
            "then return 0 end; "
            "redis.call('setex', KEYS[1], 86400, ARGV[2]); "
            "redis.call('setex', KEYS[3], 604800, ARGV[3]); "
            "if ARGV[4] == 'release' and redis.call('get', KEYS[2]) == ARGV[1] "
            "then redis.call('del', KEYS[2]) end; return 1",
            3, self.key, self.key + ":envio", self.operation_key(operation_id), operation_id,
            json.dumps(updated, ensure_ascii=False), json.dumps(record, ensure_ascii=False),
            "keep" if updated["stage"] in self.BLOCKED else "release")

    @staticmethod
    def is_request(text):
        value = normalized(text)
        return bool(re.search(r"\b(?:fixa|fixe|fixar|fixacao|fixacoes)\b", value)
                    and not re.search(r"\b(?:qual|quais|consultar|consulta|status|verificar|criar|novo)\b", value)) or bool(
            re.search(r"\b(?:cadastrar|inserir|adicionar)\b.*\bvalor\b.*\bcontrato", value))

    @staticmethod
    def parse_contracts(text):
        # Captura o token completo antes de validar, sem truncar 1234/26 ou 1/2026.
        pattern = r"(?<![\w/])([0-9]+\s*/\s*[0-9]+(?:[A-Za-z]+|\s+[A-Z](?![A-Za-z]))?)(?![\w/])"
        found = list(re.finditer(pattern, text))
        values = []
        for match in found:
            number, letter = identifier(match[1])
            ref = number + letter
            if ref in values:
                raise ValueError(f"O contrato {ref} foi informado mais de uma vez. Quais dados deseja manter?")
            values.append(ref)
        return found, values

    @staticmethod
    def fields_from_text(text, hedge=False):
        from app.agents.fixacao_tools import FixacaoTools
        from app.agents.hedge_tools import HedgeTools

        plain = normalized(text)
        fields = {}
        broker = re.search(r"\b(?:corretora|corret)\s*(?:[:=]|e\b)?\s*([\w]+(?:\s+(?:fut|otc))?)", plain)
        if broker:
            known = HedgeTools("parser").parse_known_broker(broker[1])
            fields["corret"] = known[0] if known else broker[1].upper()
        lots = re.search(r"(?<![\w.,])([+-]?[0-9]+(?:[.,][0-9]+)?)\s*lotes?\b", plain)
        if lots:
            value = float(lots[1].replace(",", "."))
            if not value.is_integer() or value <= 0:
                raise ValueError("Lotes deve ser um número inteiro e positivo.")
            fields["lotes"] = int(value)
        if hedge:
            if re.search(r"\b(?:mes|ano|nivel|valor|tipo|operac|account|conta|ctrex)\b", plain):
                raise ValueError("Após a montagem do Hedge, somente corretora, lotes e AA podem ser alterados.")
            aa = re.search(r"\b(?:lancaa|(?:lanc\.?\s*)?aa)\s*(?:[:=]|para\b|e\b)?\s*(sim|nao|s|n)\b", plain)
            if aa:
                fields["lancaa"] = "Sim" if aa[1] in {"sim", "s"} else "Nao"
            elif re.search(r"\b(?:lancaa|aa)\b", plain):
                raise ValueError("Informe AA Sim ou AA Nao.")
            return fields
        value = FixacaoTools.extract_fixation_value(text)
        if value is None:
            abbreviated = re.search(r"\b(?:a|por)\s+([+-]?[0-9]+(?:[.,][0-9]+)?)(?![0-9.,])", plain)
            if abbreviated:
                value = float(abbreviated[1].replace(",", "."))
        if value is not None:
            fields["valorFixacao"] = value
        diff = re.search(r"\bdiferencial\s*(?:[:=]|de\b|e\b)?\s*([+-]?[0-9]+(?:[.,][0-9]+)?)", plain)
        if diff:
            fields["diferencial"] = float(diff[1].replace(",", "."))
        short = re.fullmatch(r"([+-]?[0-9]+(?:[.,][0-9]+)?)(?:\s+com\s+([+-]?[0-9]+(?:[.,][0-9]+)?))?", plain)
        if short:
            fields["valorFixacao"] = float(short[1].replace(",", "."))
            if short[2]:
                fields["diferencial"] = float(short[2].replace(",", "."))
        kind = re.search(r"\btipo(?:\s+(?:(?:do|de)\s+)?valor)?\s*[:=]?\s*(.+)", plain)
        if kind:
            description = re.split(r"[,;]|\b(?:fixador|diferencial|corretora)\b", kind[1], maxsplit=1)[0].strip()
            code = FixacaoTools.normalize_tipo_valor(description)
            if not code:
                raise ValueError("Informe um tipo de valor válido: C, K, 5, 6 ou T.")
            fields["tipoValor"] = code
        fixer = re.search(r"\bfixador(?:\s+(?:do\s+)?preco)?\s*(?:[:=]|como\b|e\b)?\s*(fixador|importador|exportador|[fie])\b", plain)
        if fixer:
            fields["fixadorPreco"] = fixer[1][0].upper()
        # Estes metadados seguem o contrato; não fazem parte do payload Z24.
        metadata = {}
        HedgeTools("parser").remember_from_text(metadata, text)
        for field in ("mesfix", "anofix", "lancaa"):
            if field in metadata:
                fields[field] = metadata[field]
        return fields

    def parse_updates(self, text, hedge=False):
        if re.search(r"contratode[_ ]?venda", text, re.I):
            raise ValueError("Não informe contratodeVenda. Utilize numeroVenda e letraVenda.")
        matches, refs = self.parse_contracts(text)
        if not matches:
            return [], self.fields_from_text(text, hedge)
        # Grupos consecutivos compartilham os dados até o próximo grupo com dados próprios.
        updates, group = [], []
        prefix = text[:matches[0].start()]
        for index, (match, ref) in enumerate(zip(matches, refs)):
            group.append(ref)
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            segment = text[match.end():end]
            fields = self.fields_from_text(segment, hedge)
            if fields or index == len(matches) - 1:
                if not fields and prefix.strip():
                    fields = self.fields_from_text(prefix, hedge)
                updates.extend((key, deepcopy(fields)) for key in group)
                group = []
        return updates, {}

    @staticmethod
    def validate_fields(fields, hedge=False):
        from app.agents.fixacao_tools import FixacaoTools
        result = deepcopy(fields)
        for key in ("valorFixacao", "diferencial"):
            if key in result:
                if isinstance(result[key], bool) or not math.isfinite(float(result[key])):
                    raise ValueError(f"{key} deve ser numérico e finito.")
                result[key] = float(result[key])
        if "tipoValor" in result:
            result["tipoValor"] = FixacaoTools.normalize_tipo_valor(result["tipoValor"])
            if result["tipoValor"] is None:
                raise ValueError("Tipo do valor inválido.")
        if "fixadorPreco" in result:
            raw = normalized(result["fixadorPreco"])
            codes = {"f": "F", "fixador": "F", "i": "I", "importador": "I", "e": "E", "exportador": "E"}
            if raw not in codes:
                raise ValueError("Fixador deve ser F, I ou E.")
            result["fixadorPreco"] = codes[raw]
        if "lotes" in result:
            number = float(result["lotes"])
            if isinstance(result["lotes"], bool) or not math.isfinite(number) or not number.is_integer() or number <= 0:
                raise ValueError("Lotes deve ser um número inteiro e positivo.")
            result["lotes"] = int(number)
        if hedge and set(result) - {"corret", "lotes", "lancaa"}:
            raise ValueError("Somente corretora, lotes e AA podem ser alterados no Hedge.")
        if hedge and "lancaa" in result:
            aa = normalized(result["lancaa"])
            if aa not in {"sim", "s", "nao", "n"}:
                raise ValueError("Informe AA Sim ou AA Nao.")
            result["lancaa"] = "Sim" if aa in {"sim", "s"} else "Nao"
        if "corret" in result:
            result["corret"] = str(result["corret"]).strip()
            if not result["corret"]:
                raise ValueError("Informe a corretora.")
        return result

    def prepare_fixation(self, updates, common=None):
        """Prepara apenas; qualquer alteração sempre exige confirmação posterior."""
        data = self.load()
        if data.get("stage") in self.BLOCKED:
            if data.get("stage") == "result_error":
                raise ValueError(self.RESULT_ERROR_MESSAGE)
            raise ValueError("A operação enviada ainda aguarda resultado. Verifique no Protheus; não será reenviada.")
        if not data or data.get("stage") == "done":
            data = {"stage": "collect_fix", "contratosIniciais": [], "contratosFixadosAcumulado": [],
                    "contratosAindaNaoFixados": [], "contratos": [], "contratosFixados": [], "contratosNaoFixados": []}
        if data.get("stage", "").endswith("hedge") or data.get("stage") == "offer":
            raise ValueError("Conclua o fluxo atual antes de iniciar outra fixação.")
        pending = deepcopy(data["contratosAindaNaoFixados"])
        initial = not data["contratosIniciais"]
        seen = set()
        for ref, raw_fields in updates:
            number, letter = identifier(ref)
            key = number + letter
            if key in seen:
                raise ValueError(f"Contrato {key} repetido. Confirme os dados corretos.")
            seen.add(key)
            fields = self.validate_fields(raw_fields)
            target = next((item for item in pending if identity(item) == key), None)
            if target is None:
                if not initial:
                    raise ValueError(f"{key} não está entre os contratos pendentes. Contratos concluídos não podem ser reenviados.")
                target = {"numeroVenda": number, "letraVenda": letter}
                pending.append(target)
            target.update({**data.get("unassigned_fields", {}), **fields} if initial else fields)
        common = self.validate_fields(common or {})
        if not updates and common:
            current = {identity(i) for i in data.get("contratos", [])}
            for item in pending:
                if data["stage"] == "edit_fix" or not current or identity(item) in current:
                    if data["stage"] == "collect_fix" and "valorFixacao" in item and "valorFixacao" in common:
                        continue
                    item.update(common)
        if not pending:
            data["unassigned_fields"] = {**data.get("unassigned_fields", {}), **common}
            self.save(data)
            raise ValueError("Informe ao menos um numeroVenda no formato 999/99, com a letra quando existir.")
        data["contratosAindaNaoFixados"] = pending
        if initial:
            data["contratosIniciais"] = deepcopy(pending)
            data.pop("unassigned_fields", None)
        chosen = seen or {identity(item) for item in pending}
        if not initial and data["stage"] in {"collect_fix", "confirm_fix"}:
            chosen = {identity(i) for i in data["contratos"]}
        data["contratos"] = [deepcopy(item) for item in pending if identity(item) in chosen]
        data["stage"] = "confirm_fix" if all("valorFixacao" in i for i in data["contratos"]) else "collect_fix"
        data["confirmation_id"] = uuid.uuid4().hex
        self.save(data)
        return self.fix_summary(data)

    @staticmethod
    def display_number(value):
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                return str(value)
            text = format(number, "f")
            return (text.rstrip("0").rstrip(".") if "." in text else text).replace(".", ",")
        except InvalidOperation:
            return str(value)

    @classmethod
    def display_value(cls, value, source=None):
        unit = cls.UNITS.get(str((source or {}).get("tipoValor", "")).strip().upper())
        return cls.display_number(value) + (f" {unit}" if unit else "")

    @staticmethod
    def reasons(item):
        reasons = item.get("motivos") or item.get("motivo") or []
        return [str(reason) for reason in reasons] if isinstance(reasons, list) else [str(reasons)]

    @classmethod
    def reason_lines(cls, item, prefix=""):
        reasons = cls.reasons(item)
        if len(reasons) <= 1:
            return [prefix + "Motivo: " + (reasons[0] if reasons else "Não informado.")]
        return [prefix + "Motivos:"] + [f"\t{index}. {reason}" for index, reason in enumerate(reasons, 1)]

    @classmethod
    def result_report(cls, data, result, successes, failures, hedge=False):
        sources = {identity(item): item for item in data.get("contratosDados", []) + data.get("contratos", [])}
        lines = [str(result.get("message", "")),
                 f"Quantidade de {'movimentos registrados' if hedge else 'contratos fixados'}: {len(successes)}",
                 f"Quantidade de {'movimentos não registrados' if hedge else 'contratos não fixados'}: {len(failures)}",
                 cls.SEPARATOR]
        for label, records in (("Movimentos registrados" if hedge else "Contratos fixados", successes),
                               ("Movimentos não registrados" if hedge else "Contratos não fixados", failures)):
            lines.append(label + ":")
            if not records:
                lines.extend(["Nenhum", cls.SEPARATOR])
            for item in records:
                key = identity(item)
                if hedge:
                    lines.append(f"- Contrato: {key}")
                    for field, title in (("lotes", "Lotes"), ("valor", "Valor"), ("corretora", "Corretora")):
                        if field in item:
                            value = item[field] if field == "corretora" else cls.display_number(item[field])
                            lines.append(f"- {title}: {value}")
                else:
                    contract = str(item.get("contrato") or "").strip() or '""'
                    lines.extend([f"- Contrato: {contract}", f"- Venda: {key}"])
                    if "nivel" in item:
                        lines.append(f"- Nível: {cls.display_value(item['nivel'], sources.get(key))}")
                if records is failures:
                    lines.extend(cls.reason_lines(item, prefix="- "))
                lines.append(cls.SEPARATOR)
        return "\n".join(lines)

    @classmethod
    def fix_summary(cls, data):
        missing = [identity(i) for i in data["contratos"] if "valorFixacao" not in i]
        if missing:
            return ("Informe o valor da fixação para: " + ", ".join(missing)
                    + ". Se quiser, informe também diferencial, tipo do valor e fixador do preço; são opcionais.")
        lines = ["Resumo para confirmação da fixação:"]
        for item in data["contratos"]:
            lines.extend([f"- {identity(item)}", f"\t- Valor da Fixação: {cls.display_value(item['valorFixacao'], item)}"])
            if "fixadorPreco" in item:
                lines.append(f"\t- Fixador do Preço: {cls.FIXERS.get(item['fixadorPreco'], item['fixadorPreco'])}")
            if "diferencial" in item:
                lines.append(f"\t- Diferencial: {cls.display_number(item['diferencial'])}")
            lines.append(cls.SEPARATOR)
        return "\n".join(lines + ["Confirma o envio destes contratos?"])

    @staticmethod
    def options(hedge=False):
        return ("Escolha uma opção:\n1 — Descartar novas tentativas" + (" de Hedge" if hedge else " de fixação")
                + "\n2 — Corrigir informações e realizar nova tentativa\n3 — Realizar nova tentativa sem alterar informações")

    def final_report(self, data, hedge=False):
        lines = ["Relatório final de fixação e Hedge:" if hedge else "Relatório sintético da fixação:", "", "Contratos Fixados:"]
        registered = {identity(i): i for i in data.get("movimentosRegistradosAcumulado", [])}
        pending = {identity(i) for i in data.get("movimentosAindaNaoRegistrados", [])}
        selected = {identity(i) for i in data.get("movimentosIniciais", [])}
        for item in data["contratosFixadosAcumulado"]:
            key = identity(item)
            suffix = ""
            if hedge:
                status = "SIM" if key in registered and key not in pending else "NAO" if key in pending or key not in selected else "VERIFICAR"
                suffix = f" — Hedge = {status}"
                if status == "SIM" and "lotes" in registered[key]:
                    suffix += f" - Lotes: {self.display_number(registered[key]['lotes'])}"
            lines.append(f"- {key} = Nível: {self.display_number(item['nivel'])}{suffix}")
            lines.append(self.SEPARATOR)
        if not data["contratosFixadosAcumulado"]:
            lines.append("- Nenhum")
        lines.append("Contratos não Fixados:")
        for item in data["contratosAindaNaoFixados"]:
            reasons = self.reason_lines(item)
            lines.extend([f"- {identity(item)} = {reasons[0]}", *reasons[1:], self.SEPARATOR])
        if not data["contratosAindaNaoFixados"]:
            lines.append("- Nenhum")
        return "\n".join(lines)

    def finish_fixation(self, data, persist=True):
        if data["contratosFixadosAcumulado"]:
            data["stage"] = "offer"
            if persist:
                self.save(data)
            return "Gostaria que eu fizesse o Hedge da bolsa para os contratos fixados? Você pode selecionar todos ou parte deles."
        data["stage"] = "done"
        if persist:
            self.save(data)
        return "Nenhum contrato elegível para o Hedge\n\n" + self.final_report(data)

    def finish_hedge(self, data, persist=True):
        data["stage"] = "done"
        if persist:
            self.save(data)
        return self.final_report(data, hedge=True)

    async def ask_failure(self, data, hedge=False, persist=True):
        data["stage"] = "list_hedge" if hedge else "list_fix"
        data["list_deadline"] = time.time() + 300
        data["list_token"] = uuid.uuid4().hex
        if persist:
            self.save(data)
            self.schedule_list_timeout(data, hedge)
        return "Deseja uma listagem detalhada apenas dos " + ("movimentos não registrados?" if hedge else "contratos não fixados?")

    def schedule_list_timeout(self, data, hedge):
        if self.notify:
            task = asyncio.create_task(self._list_timeout(data["list_token"], hedge))
            _timers.add(task)
            task.add_done_callback(_timers.discard)

    async def _list_timeout(self, token, hedge):
        await asyncio.sleep(300)
        data = self.load()
        if data.get("list_token") == token and data.get("stage") == ("list_hedge" if hedge else "list_fix"):
            data["stage"] = "retry_hedge" if hedge else "retry_fix"
            self.save(data)
            await self.notify(self.options(hedge))

    @classmethod
    def failure_report(cls, data, hedge=False):
        items = data["movimentosAindaNaoRegistrados" if hedge else "contratosAindaNaoFixados"]
        lines = ["Movimentos não registrados:" if hedge else "Contratos não fixados:"]
        for item in items:
            lines.append(f"- {identity(item)}:")
            if hedge:
                for field in ("lotes", "valor", "corret"):
                    if field in item:
                        value = item[field] if field == "corret" else cls.display_number(item[field])
                        lines.append(f"{cls.LABELS[field]}: {value}")
            elif "valorFixacao" in item:
                lines.append(f"Nível: {cls.display_value(item['valorFixacao'], item)}")
            lines.extend(cls.reason_lines(item))
            lines.append(cls.SEPARATOR)
        return "\n".join(lines)

    async def start_hedge(self, data, message):
        from app.agents.hedge_tools import HedgeTools
        _, refs = self.parse_contracts(message)
        eligible = {identity(item): item for item in data["contratosFixadosAcumulado"]}
        if set(refs) - eligible.keys():
            raise ValueError("Selecione apenas contratos efetivamente fixados.")
        updates, common = self.parse_updates(message, hedge=True)
        per_contract = {ref: self.validate_fields(fields, hedge=True) for ref, fields in updates}
        common = self.validate_fields(common, hedge=True)
        selected = refs or list(eligible)
        movements = []
        for key in selected:
            source = next(i for i in data["contratosDados"] if identity(i) == key)
            movement = {"ctrex": key, "valor": eligible[key]["nivel"], "tipo": "C", "operac": "FV", "lancaa": "Nao"}
            recommendation = await asyncio.to_thread(HedgeTools.recommend_lots, key) or {}
            for field, recommended in (("mesfix", "mesfixRecomendado"), ("anofix", "anofixRecomendado"), ("lotes", "lotesRecomendados")):
                value = source.get(field, recommendation.get(recommended))
                if value is not None:
                    movement[field] = value
            if "corret" in source:
                movement["corret"] = source["corret"]
            movement.update(per_contract.get(key, common))
            if "corret" in movement:
                movement["account"] = movement["corret"]
            movements.append(movement)
        data.update({"movimentosIniciais": deepcopy(movements), "movimentosAindaNaoRegistrados": movements,
                     "movimentosRegistradosAcumulado": [], "movimentos": deepcopy(movements),
                     "hedge_submitted": False, "stage": "collect_hedge"})
        self.save(data)
        return self.hedge_summary(data)

    @staticmethod
    def hedge_has_been_submitted(data):
        # Compatibilidade com sessões persistidas antes desta versão.
        return data.get("hedge_submitted", "movimentosRegistrados" in data or "movimentosNaoRegistrados" in data)

    def hedge_summary(self, data):
        from app.agents.hedge_tools import HedgeTools
        for item in data["movimentos"]:
            for field in HedgeTools.REQUIRED:
                if field not in item or (field == "lotes" and item[field] <= 0):
                    data["stage"] = "collect_hedge"
                    data["missing"] = [identity(item), field]
                    self.save(data)
                    return HedgeTools.question_for(field, contract=identity(item))
        data.pop("missing", None)
        data["stage"] = "confirm_hedge"
        # Antes do primeiro envio, a base do Hedge reflete a proposta atual.
        # Após o envio, ela permanece imutável durante as tentativas existentes.
        if not self.hedge_has_been_submitted(data):
            data["movimentosIniciais"] = deepcopy(data["movimentos"])
        data["confirmation_id"] = uuid.uuid4().hex
        self.save(data)
        lines = ["Resumo do Hedge:", ""]
        for item in data["movimentos"]:
            lines.append(f"Contrato {identity(item)}:")
            for field in ("mesfix", "anofix", "lotes", "valor", "corret", "lancaa"):
                if field in item:
                    value = self.display_number(item[field]) if field in {"lotes", "valor"} else item[field]
                    if field == "valor":
                        # Completa centavos sem arredondar níveis mais precisos.
                        integer, _, decimals = value.partition(",")
                        value = integer + "," + decimals.ljust(2, "0")
                    lines.append(f"- {self.LABELS[field]}: {value}")
            lines.append(self.SEPARATOR)
        return "\n".join(lines + ["Confirma o envio destes movimentos?"])

    def update_hedge(self, data, message):
        from app.agents.hedge_tools import HedgeTools
        # Uma correção inválida não deve aplicar parcialmente exclusões ou dados.
        data = deepcopy(data)
        excluded = set()
        clauses = re.split(r"\b(exclua|excluir|remova|remover|retire|retirar|corrija|corrigir|altere|alterar|ajuste|ajustar)\b", message, flags=re.I)
        remaining = [clauses[0]]
        for index in range(1, len(clauses), 2):
            command, content = clauses[index:index + 2]
            if normalized(command) in {"exclua", "excluir", "remova", "remover", "retire", "retirar"}:
                if self.hedge_has_been_submitted(data):
                    raise ValueError("A exclusão da proposta é permitida somente antes do primeiro envio do Hedge.")
                _, refs = self.parse_contracts(content)
                if not refs:
                    raise ValueError("Informe quais contratos deseja excluir da proposta de Hedge.")
                if self.fields_from_text(content, hedge=True):
                    raise ValueError("Separe a exclusão das correções usando, por exemplo, 'exclua 374/26D e corrija 375/26 para 2 lotes'.")
                excluded.update(refs)
            else:
                remaining.append(content)
        message = " ".join(remaining)
        current_selection = {identity(i) for i in data["movimentos"]}
        if excluded - current_selection:
            raise ValueError("Exclua somente contratos presentes no resumo atual do Hedge.")
        selecting_retry = data.get("stage") == "edit_hedge"
        updates, common = [], {}
        if data.get("stage") == "collect_hedge" and data.get("missing") and not excluded:
            ref, field = data["missing"]
            if field not in {"corret", "account", "lotes"}:
                # Somente coleta inicial de campos obrigatórios ainda desconhecidos.
                helper = HedgeTools("parser")
                values = {}
                helper.remember_from_text(values, message, expected=field)
                if field not in values:
                    return f"Contrato {ref}: " + helper.question_for(field)
                updates = [(ref, {k: v for k, v in values.items() if k in {"mesfix", "anofix", "lancaa"}})]
            else:
                updates, common = self.parse_updates(message, hedge=True)
            if field in {"corret", "account", "lotes"} and not updates and not common:
                values = {}
                HedgeTools("parser").remember_from_text(values, message, expected=field)
                common = {k: values[k] for k in ("corret", "lotes") if k in values}
                common = self.validate_fields(common, hedge=True)
                updates = [(ref, common)]
                common = {}
        else:
            updates, common = self.parse_updates(message, hedge=True)
        allowed = {identity(i) for i in data["movimentosAindaNaoRegistrados"]}
        if any(ref not in allowed for ref, _ in updates):
            raise ValueError("Selecione apenas movimentos pendentes. Movimentos registrados não podem ser reenviados.")
        if not updates and not common and not excluded:
            raise ValueError("Informe a corretora, a quantidade de lotes ou AA, por contrato ou para o grupo.")
        if excluded & {ref for ref, _ in updates}:
            raise ValueError("Não corrija e exclua o mesmo contrato na mesma mensagem.")
        targets = {ref for ref, _ in updates} or {identity(i) for i in data["movimentos"]}
        for item in data["movimentosAindaNaoRegistrados"]:
            ref = identity(item)
            if ref in targets:
                values = next((fields for key, fields in updates if key == ref), common)
                item.update(values)
                if "corret" in item:
                    item["account"] = item["corret"]
        selection = targets if selecting_retry else current_selection
        if excluded:
            data["movimentosAindaNaoRegistrados"] = [i for i in data["movimentosAindaNaoRegistrados"] if identity(i) not in excluded]
            data["movimentosIniciais"] = [i for i in data["movimentosIniciais"] if identity(i) not in excluded]
            selection -= excluded
        data["movimentos"] = [deepcopy(i) for i in data["movimentosAindaNaoRegistrados"] if identity(i) in selection]
        if not data["movimentos"]:
            return self.finish_hedge(data)
        return self.hedge_summary(data)

    async def send(self, data, hedge=False):
        data = deepcopy(data)
        items = data["movimentos" if hedge else "contratos"]
        if not items:
            raise ValueError("Selecione ao menos um item antes do envio.")
        registered = {identity(i) for i in data["movimentosRegistradosAcumulado" if hedge else "contratosFixadosAcumulado"]}
        if any(identity(i) in registered for i in items):
            raise ValueError("Itens já concluídos não podem ser reenviados.")
        body = {"movimentos": [{k: item[k] for k in self.MOV_FIELDS if k in item} for item in items]} if hedge else {
            "contratos": [{"numeroVenda": i["numeroVenda"], "letraVenda": i.get("letraVenda", ""),
                           "fixacaoContrato": [{k: i[k] for k in self.FIX_FIELDS if k in i}]} for i in items]}
        operation_id = uuid.uuid4().hex
        lock_key = self.key + ":envio"
        # Não expira durante uma chamada tardia: evita repetir transações de resultado incerto.
        if not self._redis().set(lock_key, operation_id, nx=True):
            return "A requisição já está em processamento. Aguarde o resultado."
        current = self.load()
        if current.get("stage") != ("confirm_hedge" if hedge else "confirm_fix") or current.get("confirmation_id") != data.get("confirmation_id"):
            self.release_lock(operation_id)
            return "O resumo foi alterado ou já foi processado. Confira a confirmação atual antes de enviar."
        data["stage"] = "sending_hedge" if hedge else "sending_fix"
        if hedge:
            data["hedge_submitted"] = True
        data.update(operation_id=operation_id, process_id=_process_id)
        try:
            self.save_operation(operation_id, {"status": "started", "hedge": hedge, "snapshot": data})
            self.save(data)
        except Exception:
            self.release_lock(operation_id)
            raise
        task_key = (self.key, operation_id)
        event = _exits[task_key] = asyncio.Event()
        request = asyncio.create_task(self.run_operation(data, body, hedge))
        _operations[task_key] = request
        def cleanup(task):
            _operations.pop(task_key, None)
            _exits.pop(task_key, None)
            if not task.cancelled():
                task.exception()  # Consome exceções mesmo se a conversa foi encerrada.
        request.add_done_callback(cleanup)
        exit_wait = asyncio.create_task(event.wait())
        try:
            done, _ = await asyncio.wait({request, exit_wait}, timeout=len(items) * 30,
                                         return_when=asyncio.FIRST_COMPLETED)
            if not done:
                warning = "ATENÇÃO - Não obtivemos resposta do processo de " + ("Hedge" if hedge else "fixação de contratos") + ". Verifique no Protheus!"
                if self.notify and self.is_current(operation_id):
                    try:
                        await self.notify(warning)
                    except Exception:
                        logger.exception("Não foi possível entregar o aviso de prazo; aguardando o mesmo resultado")
                else:
                    logger.warning(warning)
                await asyncio.wait({request, exit_wait}, return_when=asyncio.FIRST_COMPLETED)
            if event.is_set() or not self.is_current(operation_id) and not request.done():
                return ""
            return await asyncio.shield(request)
        finally:
            exit_wait.cancel()

    async def run_operation(self, data, body, hedge):
        operation_id = data["operation_id"]
        operation = fixacao_api_client.cadastrar_hedge if hedge else fixacao_api_client.cadastrar_fixacao
        try:
            result = await operation(body)
            if not self.is_current(operation_id):
                return ""
            record = self.read_operation(operation_id)
            record.update(status="received", result=result)
            if not self.commit_operation(operation_id, data, record):
                return ""
            return await self.complete_operation(data, result, hedge)
        except (OperationNotSent, OperationRejected) as exc:
            if not self.is_current(operation_id):
                return ""
            record = self.read_operation(operation_id)
            record.update(status="not_sent", error=str(exc))
            data["stage"] = "confirm_hedge" if hedge else "confirm_fix"
            data["confirmation_id"] = uuid.uuid4().hex
            if not self.commit_operation(operation_id, data, record):
                return ""
            return f"{exc}\nConfirme novamente para realizar uma nova tentativa, ou informe os dados a corrigir."
        except (Exception, asyncio.CancelledError) as exc:
            if self.is_current(operation_id):
                data["stage"] = "uncertain"
                self.commit_operation(operation_id, data, self.read_operation(operation_id))
            logger.exception("Requisição de lote sem resultado conclusivo")
            if isinstance(exc, asyncio.CancelledError):
                raise
            if self.read_operation(operation_id).get("status") == "discarded":
                return ""
            return "Não foi possível obter um resultado conclusivo. Verifique no Protheus antes de qualquer nova tentativa."

    async def apply_result(self, data, result, hedge=False, persist=True):
        if not isinstance(result, dict):
            raise ValueError("Retorno do lote deve ser um objeto JSON.")
        success_key, failure_key = ("movimentosRegistrados", "movimentosNaoRegistrados") if hedge else ("contratosFixados", "contratosNaoFixados")
        successes, failures = result[success_key], result[failure_key]
        if not isinstance(successes, list) or not isinstance(failures, list):
            raise ValueError("Retorno do lote deve conter listas de sucessos e falhas.")
        returned = [identity(i) for i in successes + failures]
        sent = {identity(i) for i in data["movimentos" if hedge else "contratos"]}
        if len(returned) != len(set(returned)) or set(returned) != sent:
            raise ValueError("Retorno do lote contém contratos ausentes, duplicados ou não enviados.")
        if not hedge and any("nivel" not in item for item in successes):
            raise ValueError("Retorno de fixação sem o nível confirmado.")
        data[success_key], data[failure_key] = deepcopy(successes), deepcopy(failures)
        accumulated = "movimentosRegistradosAcumulado" if hedge else "contratosFixadosAcumulado"
        pending_key = "movimentosAindaNaoRegistrados" if hedge else "contratosAindaNaoFixados"
        ids = {identity(i) for i in data[accumulated]}
        data[accumulated].extend(deepcopy(i) for i in successes if identity(i) not in ids)
        succeeded = {identity(i) for i in data[accumulated]}
        errors = {identity(i): i for i in failures}
        if not hedge:
            # Retém metadados da fixação por contrato para a futura montagem do Hedge.
            data.setdefault("contratosDados", [])
            known = {identity(i): i for i in data["contratosDados"]}
            known.update({identity(i): deepcopy(i) for i in data["contratos"]})
            data["contratosDados"] = list(known.values())
        pending = []
        for item in data[pending_key]:
            key = identity(item)
            if key in succeeded:
                continue
            if key in errors:
                item["motivos"] = self.reasons(errors[key])
                item["ultimoRetorno"] = deepcopy(errors[key])
            pending.append(item)
        data[pending_key] = pending
        report = self.result_report(data, result, successes, failures, hedge)
        if pending:
            next_message = await self.ask_failure(data, hedge, persist=persist)
        else:
            next_message = self.finish_hedge(data, persist=persist) if hedge else self.finish_fixation(data, persist=persist)
        return report + "\n\n" + next_message

    async def handle(self, message):
        data = self.load()
        # Também permite recuperar/sair de uma trava cuja sessão já expirou.
        lock_owner = self._redis().get(self.key + ":envio")
        if not data and lock_owner:
            record = self.read_operation(lock_owner)
            data = deepcopy(record.get("snapshot") or {"stage": "uncertain"})
            if lock_owner != "1":
                data["operation_id"] = lock_owner
            if self.has_permission:
                self.save(data)
        stage = data.get("stage")
        new_request = self.is_request(message)
        if (not data or stage == "done") and not new_request:
            return None
        if not self.has_permission:
            return "Você não tem permissão para fixar contratos."
        value = normalized(message)
        try:
            if stage in self.BLOCKED:
                if value == "sair":
                    return self.abandon(data)
                related = self.is_pending_message(message)
                try:
                    recovered = await self.recover(data)
                except (ValueError, TypeError, KeyError):
                    logger.exception("Retorno persistido ainda não pôde ser interpretado")
                    recovered = self.RESULT_ERROR_MESSAGE
                if recovered is not None:
                    return recovered if related else None
                if not related:
                    return None
                return ("A operação enviada aguarda resultado conclusivo. Verifique no Protheus; "
                        "nenhum item será reenviado. Digite sair para encerrar a espera.")
            operation_id = data.get("operation_id")
            if operation_id and self.read_operation(operation_id).get("status") in {"received", "applied", "not_sent"}:
                # Reinício entre a gravação do estado final e a liberação da trava.
                self.release_lock(operation_id)
            if not data or stage == "done":
                updates, common = self.parse_updates(message)
                return self.prepare_fixation(updates, common)
            if stage == "offer":
                if value in self.NO or value == "sair":
                    data["stage"] = "done"
                    self.save(data)
                    return self.final_report(data)
                _, selected_refs = self.parse_contracts(message)
                if value == "parte":
                    return "Quais contratos deseja incluir no Hedge? Informe os números dos contratos fixados, ou digite sair."
                if value in self.YES or selected_refs or re.match(r"^(?:sim|hedge|todos|contratos)\b", value):
                    return await self.start_hedge(data, message)
                return "Deseja realizar o Hedge dos contratos fixados? Responda sim ou não, ou selecione os contratos."
            hedge = stage.endswith("hedge")
            if stage.startswith("list_"):
                if time.time() < data["list_deadline"] and value not in self.YES | self.NO:
                    return "Deseja a listagem detalhada? Responda sim ou não."
                report = self.failure_report(data, hedge) + "\n\n" if value in self.YES and time.time() < data["list_deadline"] else ""
                data["stage"] = "retry_hedge" if hedge else "retry_fix"
                self.save(data)
                return report + self.options(hedge)
            if stage.startswith("retry_"):
                option = re.fullmatch(r"(?:opcao\s*)?([123])", value)
                if not option:
                    return self.options(hedge)
                if option[1] == "1":
                    return self.finish_hedge(data) if hedge else self.finish_fixation(data)
                if option[1] == "2":
                    data["stage"] = "edit_hedge" if hedge else "edit_fix"
                    self.save(data)
                    return "Informe quais itens pendentes deseja tentar novamente e seus dados, ou digite sair."
                if hedge:
                    data["movimentos"] = deepcopy(data["movimentosAindaNaoRegistrados"])
                    return self.hedge_summary(data)
                data["contratos"] = deepcopy(data["contratosAindaNaoFixados"])
                data["stage"] = "confirm_fix"
                data["confirmation_id"] = uuid.uuid4().hex
                self.save(data)
                return self.fix_summary(data)
            if value == "sair":
                return self.finish_hedge(data) if hedge else self.finish_fixation(data)
            if stage == "collect_hedge" and data.get("missing"):
                return self.update_hedge(data, message)
            if stage in {"confirm_fix", "confirm_hedge"} and value in self.YES:
                return await self.send(data, hedge)
            if value in self.NO:
                return "Informe quais dados deseja corrigir, ou digite sair para descartar novas tentativas."
            if hedge:
                return self.update_hedge(data, message)
            updates, common = self.parse_updates(message)
            return self.prepare_fixation(updates, common)
        except (ValueError, TypeError, KeyError) as exc:
            return f"Verifique as informações: {exc}"
