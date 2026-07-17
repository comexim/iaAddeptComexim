"""Tool conversacional para cadastrar valor/fixacao em contrato existente."""
import asyncio
import json
import math
from typing import Any, Dict, Optional

import redis
from langchain_core.tools import StructuredTool

from app.core.config import settings
from app.core.fixacao_api_client import fixacao_api_client


class FixacaoTools:
    REQUIRED = ("contratodeVenda", "valorFixacao", "diferencial", "tipoValor", "fixadorPreco")
    LABELS = {"contratodeVenda": "contrato de venda", "valorFixacao": "valor da fixacao", "diferencial": "diferencial", "tipoValor": "tipo do valor", "fixadorPreco": "fixador do preco"}

    def __init__(self, session_id: str):
        self.key = f"fixacao_pendente:{session_id}"

    def _redis(self):
        return redis.from_url(settings.redis_url, decode_responses=True)

    def _load(self) -> Dict[str, Any]:
        raw = self._redis().get(self.key)
        return json.loads(raw) if raw else {}

    def _save(self, data: Dict[str, Any]):
        self._redis().setex(self.key, 3600, json.dumps(data, ensure_ascii=False))

    def _summary(self, data: Dict[str, Any]) -> str:
        return ("RESUMO PARA CONFIRMACAO:\n" f"Contrato de venda: {data['contratodeVenda']}\n" f"Valor da fixacao: {data['valorFixacao']}\n" f"Diferencial: {data['diferencial']}\n" f"Tipo do valor: {data['tipoValor']}\n" f"Fixador do preco: {data['fixadorPreco']}\n\n" "Pergunte se o usuario confirma explicitamente o envio destes dados para a API.")

    def cadastrar_valor_contrato(self, contratode_venda: Optional[str] = None, valor_fixacao: Optional[float] = None, diferencial: Optional[float] = None, tipo_valor: Optional[str] = None, fixador_preco: Optional[str] = None, confirmar_envio: bool = False) -> str:
        """Coleta, confirma e envia uma fixacao de contrato para a API CMX."""
        data = self._load()
        novos = {"contratodeVenda": contratode_venda, "valorFixacao": valor_fixacao, "diferencial": diferencial, "tipoValor": tipo_valor, "fixadorPreco": fixador_preco}
        changed = False
        for key, value in novos.items():
            if value is not None:
                if isinstance(value, str):
                    value = value.strip()
                    if not value:
                        return f"VALOR_INVALIDO: {self.LABELS[key]} nao pode ser vazio."
                if key in ("valorFixacao", "diferencial") and not math.isfinite(float(value)):
                    return f"VALOR_INVALIDO: {self.LABELS[key]} deve ser numerico e finito."
                data[key] = value
                changed = True
        if changed:
            data["aguardando_confirmacao"] = False
        missing = [self.LABELS[key] for key in self.REQUIRED if key not in data]
        if missing:
            self._save(data)
            return "PRECISA_PERGUNTAR: " + "; ".join(missing) + ". Pergunte um campo por vez e nao invente valores."
        if confirmar_envio:
            if changed or not data.get("aguardando_confirmacao"):
                self._save(data)
                return "CONFIRMACAO_INVALIDA: exiba os dados novamente antes de pedir nova confirmacao. " + self._summary(data)
            body = {"contratodeVenda": str(data["contratodeVenda"]), "fixacaoContrato": [{"valorFixacao": float(data["valorFixacao"]), "diferencial": float(data["diferencial"]), "tipoValor": str(data["tipoValor"]), "fixadorPreco": str(data["fixadorPreco"])}]}
            try:
                result = asyncio.run(fixacao_api_client.cadastrar_fixacao(body))
            except Exception as exc:
                return f"ERRO_API: o cadastro nao foi confirmado pela API CMX: {exc}"
            self._redis().delete(self.key)
            return "FIXACAO_CADASTRADA_SUCESSO: " + json.dumps(result, ensure_ascii=False)
        data["aguardando_confirmacao"] = True
        self._save(data)
        return "AGUARDANDO_CONFIRMACAO: " + self._summary(data)

    def get_tool(self) -> StructuredTool:
        return StructuredTool.from_function(func=self.cadastrar_valor_contrato, name="cadastrar_valor_contrato", description="Cadastra valor/fixacao em contrato existente. Colete contratode_venda, valor_fixacao, diferencial, tipo_valor e fixador_preco. Nunca invente dados. Mostre o resumo retornado e, somente depois de confirmacao explicita, chame novamente com confirmar_envio=True. Correcao de qualquer campo exige novo resumo e nova confirmacao.")


def create_fixacao_tool(session_id: str) -> StructuredTool:
    return FixacaoTools(session_id).get_tool()
