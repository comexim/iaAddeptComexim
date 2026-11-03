"""Fluxo persistente de fixação e Hedge em lote, sem decisões financeiras do LLM."""
import asyncio
from copy import deepcopy
import json
import logging
import math
import re
import time
import unicodedata
import uuid

import redis

from app.core.config import settings
from app.core.fixacao_api_client import fixacao_api_client

logger = logging.getLogger(__name__)
_timers = set()


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text).lower())
                   if not unicodedata.combining(c)).strip().rstrip(".! ")


def identifier(value, letter=None):
    """Não aceita código interno nem anos incompletos; conserva zeros e letra."""
    match = re.fullmatch(r"\s*([0-9]{1,3})\s*/\s*([0-9]{2})\s*([A-Z]?)\s*", str(value))
    if not match:
        raise ValueError("Informe numeroVenda no formato 999/99 e, se existir, uma letra maiúscula. Não informe contratodeVenda.")
    suffix = match[3]
    if letter is not None:
        if not re.fullmatch(r"[A-Z]?", str(letter)) or (suffix and suffix != letter):
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
            if re.search(r"\b(?:mes|ano|nivel|valor|tipo|operac|account|conta|ctrex|lancaa)\b", plain):
                raise ValueError("Após a montagem do Hedge, somente corretora e lotes podem ser alterados.")
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
        if hedge and set(result) - {"corret", "lotes"}:
            raise ValueError("Somente corretora e lotes podem ser alterados no Hedge.")
        if "corret" in result:
            result["corret"] = str(result["corret"]).strip()
            if not result["corret"]:
                raise ValueError("Informe a corretora.")
        return result

    def prepare_fixation(self, updates, common=None):
        """Prepara apenas; qualquer alteração sempre exige confirmação posterior."""
        data = self.load()
        if data.get("stage") in {"sending_fix", "sending_hedge", "uncertain"}:
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
    def fix_summary(data):
        missing = [identity(i) for i in data["contratos"] if "valorFixacao" not in i]
        if missing:
            return ("Informe o valor da fixação para: " + ", ".join(missing)
                    + ". Se quiser, informe também diferencial, tipo do valor e fixador do preço; são opcionais.")
        lines = ["Resumo para confirmação da fixação:"]
        for item in data["contratos"]:
            details = "; ".join(f"{key}: {item[key]}" for key in ContractBatchFlow.FIX_FIELDS if key in item)
            lines.append(f"- {identity(item)} — {details}")
        return "\n".join(lines + ["Confirma o envio destes contratos?"])

    @staticmethod
    def options(hedge=False):
        return ("Escolha uma opção:\n1 — Descartar novas tentativas" + (" de Hedge" if hedge else " de fixação")
                + "\n2 — Corrigir informações e realizar nova tentativa\n3 — Realizar nova tentativa sem alterar informações")

    def final_report(self, data, hedge=False):
        lines = ["Relatório sintético final de fixação e Hedge:" if hedge else "Relatório sintético da fixação:", "Contratos Fixados:"]
        registered = {identity(i) for i in data.get("movimentosRegistradosAcumulado", [])}
        pending = {identity(i) for i in data.get("movimentosAindaNaoRegistrados", [])}
        selected = {identity(i) for i in data.get("movimentosIniciais", [])}
        for item in data["contratosFixadosAcumulado"]:
            key = identity(item)
            suffix = ""
            if hedge:
                status = "SIM" if key in registered and key not in pending else "NAO" if key in pending or key not in selected else "VERIFICAR"
                suffix = f" — Hedge = {status}"
            lines.append(f"- {key} = Nível: {item['nivel']}{suffix}")
        if not data["contratosFixadosAcumulado"]:
            lines.append("- Nenhum")
        lines.append("Contratos não Fixados:")
        for item in data["contratosAindaNaoFixados"]:
            lines.append(f"- {identity(item)} = Motivos: " + "; ".join(item.get("motivos", [])))
        if not data["contratosAindaNaoFixados"]:
            lines.append("- Nenhum")
        return "\n".join(lines)

    def finish_fixation(self, data):
        if data["contratosFixadosAcumulado"]:
            data["stage"] = "offer"
            self.save(data)
            return "Gostaria que eu fizesse o Hedge da bolsa para os contratos fixados? Você pode selecionar todos ou parte deles."
        data["stage"] = "done"
        self.save(data)
        return "Nenhum contrato elegível para o Hedge\n\n" + self.final_report(data)

    def finish_hedge(self, data):
        data["stage"] = "done"
        self.save(data)
        return self.final_report(data, hedge=True)

    async def ask_failure(self, data, hedge=False):
        data["stage"] = "list_hedge" if hedge else "list_fix"
        data["list_deadline"] = time.time() + 300
        data["list_token"] = uuid.uuid4().hex
        self.save(data)
        if self.notify:
            task = asyncio.create_task(self._list_timeout(data["list_token"], hedge))
            _timers.add(task)
            task.add_done_callback(_timers.discard)
        return "Deseja uma listagem detalhada apenas dos " + ("movimentos não registrados?" if hedge else "contratos não fixados?")

    async def _list_timeout(self, token, hedge):
        await asyncio.sleep(300)
        data = self.load()
        if data.get("list_token") == token and data.get("stage") == ("list_hedge" if hedge else "list_fix"):
            data["stage"] = "retry_hedge" if hedge else "retry_fix"
            self.save(data)
            await self.notify(self.options(hedge))

    @staticmethod
    def failure_report(data, hedge=False):
        items = data["movimentosAindaNaoRegistrados" if hedge else "contratosAindaNaoFixados"]
        lines = ["Movimentos não registrados:" if hedge else "Contratos não fixados:"]
        for item in items:
            lines.append(f"- {identity(item)}: " + "; ".join(item.get("motivos", [])))
            lines.append("  Dados: " + json.dumps({k: v for k, v in item.items() if k != "motivos"}, ensure_ascii=False))
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
            movement = {"ctrex": key, "valor": eligible[key]["nivel"], "tipo": "C", "operac": "FV"}
            recommendation = await asyncio.to_thread(HedgeTools.recommend_lots, key) or {}
            for field, recommended in (("mesfix", "mesfixRecomendado"), ("anofix", "anofixRecomendado"), ("lotes", "lotesRecomendados")):
                value = source.get(field, recommendation.get(recommended))
                if value is not None:
                    movement[field] = value
            for field in ("corret", "lancaa"):
                if field in source:
                    movement[field] = source[field]
            movement.update(per_contract.get(key, common))
            if "corret" in movement:
                movement["account"] = movement["corret"]
            movements.append(movement)
        data.update({"movimentosIniciais": deepcopy(movements), "movimentosAindaNaoRegistrados": movements,
                     "movimentosRegistradosAcumulado": [], "movimentos": deepcopy(movements), "stage": "collect_hedge"})
        self.save(data)
        return self.hedge_summary(data)

    def hedge_summary(self, data):
        from app.agents.hedge_tools import HedgeTools
        for item in data["movimentos"]:
            # Conserva inclusive lancaa, obrigatório no fluxo anterior.
            for field in HedgeTools.REQUIRED:
                if field not in item or (field == "lotes" and item[field] <= 0):
                    data["stage"] = "collect_hedge"
                    data["missing"] = [identity(item), field]
                    self.save(data)
                    return f"Contrato {identity(item)}: " + HedgeTools.question_for(field)
        data.pop("missing", None)
        data["stage"] = "confirm_hedge"
        data["confirmation_id"] = uuid.uuid4().hex
        self.save(data)
        return "Resumo do Hedge:\n" + "\n".join(
            "- " + json.dumps({k: item[k] for k in self.MOV_FIELDS if k in item}, ensure_ascii=False)
            for item in data["movimentos"]) + "\nConfirma o envio destes movimentos?"

    def update_hedge(self, data, message):
        from app.agents.hedge_tools import HedgeTools
        selecting_retry = data.get("stage") == "edit_hedge"
        current_selection = {identity(i) for i in data["movimentos"]}
        updates, common = [], {}
        if data.get("stage") == "collect_hedge" and data.get("missing"):
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
        if not updates and not common:
            raise ValueError("Informe a corretora ou a quantidade de lotes, por contrato ou para o grupo.")
        targets = {ref for ref, _ in updates} or {identity(i) for i in data["movimentos"]}
        for item in data["movimentosAindaNaoRegistrados"]:
            ref = identity(item)
            if ref in targets:
                values = next((fields for key, fields in updates if key == ref), common)
                item.update(values)
                if "corret" in item:
                    item["account"] = item["corret"]
        selection = targets if selecting_retry else current_selection
        data["movimentos"] = [deepcopy(i) for i in data["movimentosAindaNaoRegistrados"] if identity(i) in selection]
        return self.hedge_summary(data)

    async def send(self, data, hedge=False):
        items = data["movimentos" if hedge else "contratos"]
        if not items:
            raise ValueError("Selecione ao menos um item antes do envio.")
        registered = {identity(i) for i in data["movimentosRegistradosAcumulado" if hedge else "contratosFixadosAcumulado"]}
        if any(identity(i) in registered for i in items):
            raise ValueError("Itens já concluídos não podem ser reenviados.")
        lock_key = self.key + ":envio"
        # Não expira durante uma chamada tardia: evita repetir transações de resultado incerto.
        if not self._redis().set(lock_key, "1", nx=True):
            return "A requisição já está em processamento. Aguarde o resultado."
        current = self.load()
        if current.get("stage") != ("confirm_hedge" if hedge else "confirm_fix") or current.get("confirmation_id") != data.get("confirmation_id"):
            self._redis().delete(lock_key)
            return "O resumo foi alterado ou já foi processado. Confira a confirmação atual antes de enviar."
        data["stage"] = "sending_hedge" if hedge else "sending_fix"
        self.save(data)
        body = {"movimentos": [{k: item[k] for k in self.MOV_FIELDS if k in item} for item in items]} if hedge else {
            "contratos": [{"numeroVenda": i["numeroVenda"], "letraVenda": i.get("letraVenda", ""),
                           "fixacaoContrato": [{k: i[k] for k in self.FIX_FIELDS if k in i}]} for i in items]}
        operation = fixacao_api_client.cadastrar_hedge if hedge else fixacao_api_client.cadastrar_fixacao
        request = asyncio.create_task(operation(body))
        try:
            done, _ = await asyncio.wait({request}, timeout=len(items) * 30)
            if not done:
                warning = "ATENÇÃO - Não obtivemos resposta do processo de " + ("Hedge" if hedge else "fixação de contratos") + ". Verifique no Protheus!"
                if self.notify:
                    try:
                        await self.notify(warning)
                    except Exception:
                        logger.exception("Não foi possível entregar o aviso de prazo; aguardando o mesmo resultado")
                else:
                    logger.warning(warning)
            result = await asyncio.shield(request)
            output = await self.apply_result(data, result, hedge)
        except (Exception, asyncio.CancelledError) as exc:
            data["stage"] = "uncertain"
            self.save(data)
            logger.exception("Requisição de lote sem resultado conclusivo")
            if isinstance(exc, asyncio.CancelledError):
                raise
            return "Não foi possível obter um resultado conclusivo. Verifique no Protheus antes de qualquer nova tentativa."
        self._redis().delete(lock_key)
        return output

    async def apply_result(self, data, result, hedge=False):
        success_key, failure_key = ("movimentosRegistrados", "movimentosNaoRegistrados") if hedge else ("contratosFixados", "contratosNaoFixados")
        successes, failures = result[success_key], result[failure_key]
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
                item["motivos"] = errors[key].get("motivos", [])
                item["ultimoRetorno"] = deepcopy(errors[key])
            pending.append(item)
        data[pending_key] = pending
        lines = [str(result.get("message", "")),
                 f"Quantidade de {'movimentos registrados' if hedge else 'contratos fixados'}: {result['registrados' if hedge else 'fixados']}",
                 f"Quantidade de {'movimentos não registrados' if hedge else 'contratos não fixados'}: {result['naoRegistrados' if hedge else 'naoFixados']}"]
        for label, records in (("Movimentos registrados" if hedge else "Contratos fixados", successes),
                               ("Movimentos não registrados" if hedge else "Contratos não fixados", failures)):
            lines.append(label + ":")
            lines.extend("- " + json.dumps(i, ensure_ascii=False) for i in records)
        self.save(data)
        if pending:
            next_message = await self.ask_failure(data, hedge)
        else:
            next_message = self.finish_hedge(data) if hedge else self.finish_fixation(data)
        return "\n".join(lines) + "\n\n" + next_message

    async def handle(self, message):
        data = self.load()
        stage = data.get("stage")
        new_request = self.is_request(message)
        if (not data or stage == "done") and not new_request:
            return None
        if not self.has_permission:
            return "Você não tem permissão para fixar contratos."
        value = normalized(message)
        try:
            if not data or stage == "done":
                updates, common = self.parse_updates(message)
                return self.prepare_fixation(updates, common)
            if stage in {"sending_fix", "sending_hedge", "uncertain"}:
                return "A operação enviada aguarda resultado conclusivo. Verifique no Protheus; nenhum item será reenviado."
            if stage == "offer":
                if value in self.NO:
                    data["stage"] = "done"
                    self.save(data)
                    return self.final_report(data)
                if value in self.YES or re.match(r"^(?:sim|hedge|todos|contratos|[0-9]+\s*/)", value):
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
