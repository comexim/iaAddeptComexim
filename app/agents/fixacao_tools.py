"""Tool conversacional para cadastrar valor/fixacao em contrato existente."""
import asyncio
import json
import re
import unicodedata
import logging
from typing import Any, Dict, Optional

import redis
from langchain_core.tools import StructuredTool

from app.core.config import settings
from app.core.fixacao_api_client import fixacao_api_client


logger = logging.getLogger(__name__)


class FixacaoTools:
    REQUIRED = ("numeroVenda", "valorFixacao")
    LABELS = {"numeroVenda": "número da venda", "valorFixacao": "valor da fixacao", "diferencial": "diferencial", "tipoValor": "tipo do valor", "fixadorPreco": "fixador do preco"}

    def __init__(self, session_id: str, has_permission: bool = False):
        self.key = f"fixacao_pendente:{session_id}"
        self.has_permission = has_permission

    def _redis(self):
        return redis.from_url(settings.redis_url, decode_responses=True)

    def _load(self) -> Dict[str, Any]:
        raw = self._redis().get(self.key)
        return json.loads(raw) if raw else {}

    def _save(self, data: Dict[str, Any]):
        self._redis().setex(self.key, 3600, json.dumps(data, ensure_ascii=False))

    def _batch_flow(self):
        from app.agents.contract_batch_flow import ContractBatchFlow
        return ContractBatchFlow(self.key.split(":", 1)[1], self.has_permission)

    def is_awaiting_confirmation(self) -> bool:
        return self.has_permission and self._batch_flow().load().get("stage") == "confirm_fix"

    def is_waiting_for_value(self) -> bool:
        return self.has_permission and self._batch_flow().load().get("stage") == "collect_fix"

    def clear_pending(self) -> None:
        flow = self._batch_flow()
        if flow.load().get("stage") in {"sending_fix", "sending_hedge", "uncertain"}:
            return
        flow._redis().delete(flow.key)

    def get_pending_contract(self) -> Optional[str]:
        from app.agents.contract_batch_flow import identity
        items = self._batch_flow().load().get("contratos", [])
        return identity(items[0]) if self.has_permission and len(items) == 1 else None

    @staticmethod
    def normalize_contract_reference(value: Any) -> str:
        """Normaliza espaços do número e cola a letra final ao contrato."""
        contract = str(value or "").strip().upper()
        match = re.fullmatch(r'(\d+)\s*/\s*(\d+)\s*([A-Z])?', contract)
        if not match:
            return contract
        return f"{match.group(1)}/{match.group(2)}{match.group(3) or ''}"

    @classmethod
    def extract_lettered_contract(
        cls, text: Any, current_contract: Optional[str] = None
    ) -> Optional[str]:
        """Extrai correções como 468/26A, 468/26 A ou 'a letra é A'."""
        normalized = unicodedata.normalize("NFKD", str(text or "").lower())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )

        glued = re.search(r'\b(\d{2,4})\s*/\s*(\d{2})([a-z])\b', normalized)
        if glued:
            return f"{glued.group(1)}/{glued.group(2)}{glued.group(3).upper()}"

        spaced = re.search(
            r'\b(\d{2,4})\s*/\s*(\d{2})\s+([a-z])(?=\s*(?:$|[,.;]))',
            normalized,
        )
        if spaced:
            return f"{spaced.group(1)}/{spaced.group(2)}{spaced.group(3).upper()}"

        letter = re.search(
            r'\bletra\s*(?:e|eh|esta|fica|:|=)?\s*([a-z])\b',
            normalized,
        )
        if not letter or not current_contract:
            return None
        base = re.fullmatch(
            r'(\d+)\s*/\s*(\d+)(?:\s*[a-z])?',
            str(current_contract).strip(),
            re.IGNORECASE,
        )
        if not base:
            return None
        return f"{base.group(1)}/{base.group(2)}{letter.group(1).upper()}"

    @staticmethod
    def extract_fixation_value(text: Any) -> Optional[float]:
        """Extrai valor explicitamente rotulado como valor, fixação ou nível."""
        normalized = unicodedata.normalize("NFKD", str(text or "").lower())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        normalized = re.sub(r'\s+', ' ', normalized)
        match = re.search(
            r'(?:valor(?:\s+(?:da|de)\s+fixacao)?|fixacao|nivel)\s*'
            r'(?:e|eh|de|como|:|=)*\s*'
            r'([+-]?\d+(?:[.,]\d+)?)',
            normalized,
        )
        if not match:
            match = re.search(
                r'([+-]?\d+(?:[.,]\d+)?)\s*(?:de\s+)?fixacao\b',
                normalized,
            )
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    @staticmethod
    def normalize_tipo_valor(value: Any) -> Optional[str]:
        """Converte descricoes do tipo de valor para o codigo interno CMX."""
        if value is None:
            return None
        text = unicodedata.normalize("NFKD", str(value).strip().lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r'\s+', ' ', text)

        if text.upper() in {"C", "K", "5", "6", "T"}:
            return text.upper()
        # Verifique pesos especificos antes do kg generico.
        if re.search(r'\b50\s*kg\b|\bus\$?\s*50\s*kg\b|\bsaca\s+de\s+50\s*kg\b', text):
            return "5"
        if re.search(r'\b59\s*kg\b|\bus\$?\s*59\s*kg\b|\bsaca\s+de\s+59\s*kg\b', text):
            return "6"
        if re.search(r'cts\s*/\s*lb|centavos?\s+(?:de\s+dolar\s+)?por\s+libra|cents?\s+per\s+pound', text):
            return "C"
        if re.search(r'\btoneladas?\b|\btons?\b|us\$?\s*ton\b|valor\s+por\s+tonelada', text):
            return "T"
        if re.search(r'\bquilos?\b|\bkg\b|\bquilogramas?\b|us\$?\s*kg\b', text):
            return "K"
        return None

    @staticmethod
    def build_contract_identifier(value: Any) -> Dict[str, str]:
        """Monta o identificador exigido pela API conforme o formato informado."""
        from app.agents.contract_batch_flow import identifier
        number, letter = identifier(value)
        return {"numeroVenda": number, "letraVenda": letter}

    def format_pending_summary(self) -> str:
        flow = self._batch_flow()
        return flow.fix_summary(flow.load())

    @staticmethod
    def _load_contract_value_type(contract: str) -> Optional[str]:
        """Lê o tipoValor oficial do contrato sem inferir unidade monetária."""
        try:
            from app.core.database import sql_client

            rows = sql_client.execute_procedure(
                "usp_IA_Vendas", {"Contrato": str(contract).strip()}
            )
            for row in rows or []:
                raw = None
                for key, value in row.items():
                    normalized_key = unicodedata.normalize("NFKD", str(key).lower())
                    normalized_key = "".join(
                        char for char in normalized_key
                        if not unicodedata.combining(char) and char.isalnum()
                    )
                    if normalized_key in {
                        "tipovalor", "tipodevalor", "unidadedovalor", "unidadevalor"
                    } and value not in (None, ""):
                        raw = value
                        break
                if raw is not None:
                    value_type = re.sub(r'\s+', ' ', str(raw)).strip().upper()
                    if value_type:
                        logger.info(
                            "[FIXACAO FLOW] tipoValor do contrato %s: %s",
                            contract, value_type,
                        )
                        return value_type
            if rows:
                logger.warning(
                    "[FIXACAO FLOW] tipoValor não encontrado no contrato %s; campos retornados=%s",
                    contract,
                    sorted(str(key).strip() for key in rows[0].keys()),
                )
        except Exception as exc:
            # A ausência dessa informação muda somente a apresentação; nunca
            # deve impedir a fixação do contrato.
            logger.warning(
                "[FIXACAO FLOW] Não foi possível consultar tipoValor de %s: %s",
                contract, exc,
            )
        return None

    def cadastrar_valor_contrato(self, numero_venda: Optional[str] = None, valor_fixacao: Optional[float] = None, diferencial: Optional[float] = None, tipo_valor: Optional[str] = None, fixador_preco: Optional[str] = None, confirmar_envio: bool = False, contratos_json: Optional[str] = None, letra_venda: Optional[str] = None) -> str:
        """Coleta um ou vários contratos; nunca aceita o código interno de venda."""
        from app.agents.contract_batch_flow import ContractBatchFlow, identifier
        flow = ContractBatchFlow(self.key.split(":", 1)[1], self.has_permission)
        if not self.has_permission:
            return "Você não tem permissão para fixar contratos."
        try:
            common = {key: value for key, value in {
                "valorFixacao": valor_fixacao, "diferencial": diferencial,
                "tipoValor": tipo_valor, "fixadorPreco": fixador_preco,
            }.items() if value is not None}
            updates = []
            if contratos_json is not None:
                contracts = json.loads(contratos_json)
                if not isinstance(contracts, list) or not contracts:
                    raise ValueError("contratos_json deve conter uma lista não vazia.")
                for item in contracts:
                    if "contratodeVenda" in item:
                        raise ValueError("Não informe contratodeVenda.")
                    number, letter = identifier(item["numeroVenda"], item.get("letraVenda"))
                    fixation = item.get("fixacaoContrato", [{}])
                    if not isinstance(fixation, list) or len(fixation) != 1:
                        raise ValueError("Cada contrato deve conter exatamente uma fixacaoContrato.")
                    fields = {**common, **fixation[0]}
                    fields.update({k: item[k] for k in ("corret", "mesfix", "anofix", "lotes", "lancaa") if k in item})
                    updates.append((number + letter, fields))
            elif numero_venda is not None:
                number, letter = identifier(numero_venda, letra_venda)
                updates = [(number + letter, common)]
            elif letra_venda is not None:
                raise ValueError("Informe numeroVenda junto da letra.")
            if updates or common:
                # Mesmo uma chamada com confirmar_envio junto de dados novos
                # somente apresenta o resumo e prepara confirmação posterior.
                return "AGUARDANDO_CONFIRMACAO: " + flow.prepare_fixation(updates, common)
            data = flow.load()
            if confirmar_envio and data.get("stage") == "confirm_fix":
                return "RESULTADO_LOTE: " + asyncio.run(flow.send(data))
            if data.get("contratos") and data.get("stage") in {"confirm_fix", "collect_fix"}:
                return "AGUARDANDO_CONFIRMACAO: " + flow.fix_summary(data)
            return "PRECISA_PERGUNTAR: informe numeroVenda no formato 999/99 e o valor da fixação."
        except (ValueError, TypeError, KeyError) as exc:
            return f"VALOR_INVALIDO: {exc}"

    def get_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            func=self.cadastrar_valor_contrato, name="cadastrar_valor_contrato",
            description=("Prepara fixação em lote. Informe numero_venda e letra_venda ou contratos_json "
                         "como lista de objetos numeroVenda, letraVenda e fixacaoContrato com exatamente um item. "
                         "Somente número da venda 999/99 e valorFixacao são obrigatórios; diferencial, tipoValor e fixadorPreco permanecem opcionais. "
                         "Nunca aceite código interno contratodeVenda. Complete zeros à esquerda e questione duplicidades. "
                         "Dados comuns devem ser reproduzidos por contrato. Mostre integralmente o resumo retornado. "
                         "Qualquer alteração exige nova confirmação posterior. Só use confirmar_envio=True após confirmação explícita sem novos dados. "
                         "O fluxo mantém sucessos acumulados e somente pendências podem ser reenviadas."))


def create_fixacao_tool(session_id: str, has_permission: bool = False) -> StructuredTool:
    return FixacaoTools(session_id, has_permission=has_permission).get_tool()
