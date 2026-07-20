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
    REQUIRED = ("contratodeVenda", "valorFixacao")
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

    def is_awaiting_confirmation(self) -> bool:
        """Indica se os dados ja foram exibidos e aguardam confirmacao."""
        data = self._load()
        return bool(data.get("aguardando_confirmacao")) and all(key in data for key in self.REQUIRED)

    def _summary(self, data: Dict[str, Any]) -> str:
        lines = [
            "RESUMO PARA CONFIRMACAO:",
            f"Contrato de venda: {data['contratodeVenda']}",
            f"Valor da fixacao: {data['valorFixacao']}",
        ]
        for key in ("diferencial", "tipoValor", "fixadorPreco"):
            if key in data:
                lines.append(f"{self.LABELS[key].capitalize()}: {data[key]}")
        lines.extend(["", "Pergunte se o usuario confirma explicitamente o envio destes dados para a API."])
        return "\n".join(lines)

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
                if key in ("valorFixacao", "diferencial"):
                    value = float(value)
                previous = data.get(key)
                data[key] = value
                # O LLM pode repetir contrato e valor junto com a confirmacao.
                # Repetir exatamente o mesmo dado nao e uma alteracao.
                if previous != value:
                    changed = True
        if changed:
            data["aguardando_confirmacao"] = False
        missing = [self.LABELS[key] for key in self.REQUIRED if key not in data]
        if missing:
            self._save(data)
            optional_hint = ""
            if "valor da fixacao" in missing and "contratodeVenda" in data:
                optional_hint = (
                    " Ao pedir o valor da fixacao, avise brevemente que, se quiser, o usuario pode informar "
                    "tambem diferencial, tipo do valor e fixador do preco na mesma resposta. "
                    "Deixe claro que sao opcionais e nao os apresente como pendencias."
                )
            return "PRECISA_PERGUNTAR: " + "; ".join(missing) + ". Pergunte um campo por vez e nao invente valores." + optional_hint
        # Fallback para modelos que, após o usuário confirmar, chamam a tool
        # sem preencher confirmar_envio=True. Uma chamada sem novos campos só
        # confirma quando o resumo já foi exibido e o estado está aguardando.
        confirmar_por_estado = bool(data.get("aguardando_confirmacao")) and not changed
        if confirmar_envio or confirmar_por_estado:
            if changed or not data.get("aguardando_confirmacao"):
                self._save(data)
                return "CONFIRMACAO_INVALIDA: exiba os dados novamente antes de pedir nova confirmacao. " + self._summary(data)
            fixacao = {"valorFixacao": float(data["valorFixacao"])}
            if "diferencial" in data:
                fixacao["diferencial"] = float(data["diferencial"])
            if "tipoValor" in data:
                fixacao["tipoValor"] = str(data["tipoValor"])
            if "fixadorPreco" in data:
                fixacao["fixadorPreco"] = str(data["fixadorPreco"])
            body = {"contratodeVenda": str(data["contratodeVenda"]), "fixacaoContrato": [fixacao]}
            try:
                result = asyncio.run(fixacao_api_client.cadastrar_fixacao(body))
            except Exception as exc:
                return f"ERRO_API: {exc}"
            self._redis().delete(self.key)
            return "FIXACAO_CADASTRADA_SUCESSO: " + json.dumps(result, ensure_ascii=False)
        data["aguardando_confirmacao"] = True
        self._save(data)
        return "AGUARDANDO_CONFIRMACAO: " + self._summary(data)

    def get_tool(self) -> StructuredTool:
        return StructuredTool.from_function(func=self.cadastrar_valor_contrato, name="cadastrar_valor_contrato", description="Cadastra valor/fixacao em contrato existente. Somente contratode_venda e valor_fixacao sao obrigatorios. diferencial, tipo_valor e fixador_preco sao opcionais: inclua-os apenas se o usuario informar e nao pergunte por eles automaticamente. Nunca invente dados. Mostre o resumo retornado. Depois de confirmacao explicita do usuario, chame com confirmar_envio=True; se o modelo omitir esse parametro, chame sem repetir os dados, pois a tool reconhece o estado aguardando confirmacao. Correcao de qualquer campo exige novo resumo e nova confirmacao.")


def create_fixacao_tool(session_id: str) -> StructuredTool:
    return FixacaoTools(session_id).get_tool()
