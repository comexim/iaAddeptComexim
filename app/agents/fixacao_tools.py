"""Tool conversacional para cadastrar valor/fixacao em contrato existente."""
import asyncio
import json
import math
import re
import unicodedata
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

    def is_waiting_for_value(self) -> bool:
        """Indica contrato coletado que ainda aguarda o valor da fixacao."""
        data = self._load()
        return "contratodeVenda" in data and "valorFixacao" not in data

    def clear_pending(self) -> None:
        """Descarta os dados da operacao pendente desta conversa."""
        self._redis().delete(self.key)

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
        contract = str(value).strip()
        sale_match = re.fullmatch(r'(\d+\s*/\s*\d+)\s*([A-Za-z])?', contract)
        if not sale_match:
            return {"contratodeVenda": contract}

        sale_number = re.sub(r'\s+', '', sale_match.group(1))
        identifier = {"numeroVenda": sale_number}
        if sale_match.group(2):
            identifier["letraVenda"] = sale_match.group(2).upper()
        return identifier

    def format_pending_summary(self) -> str:
        """Formata o cadastro pendente para resposta direta ao usuario."""
        data = self._load()
        valor = f"{float(data['valorFixacao']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lines = [
            "Aqui está o resumo atualizado dos dados:",
            "",
            f"Contrato de venda: {data['contratodeVenda']}",
            f"Valor da fixação: R$ {valor}",
        ]
        if "diferencial" in data:
            lines.append(f"Diferencial: {data['diferencial']:g}")
        if "tipoValor" in data:
            lines.append(f"Tipo do valor: {data['tipoValor']}")
        if "fixadorPreco" in data:
            descriptions = {"F": "Fixador", "I": "Importador", "E": "Exportador"}
            code = data["fixadorPreco"]
            lines.append(f"Fixador do preço: {descriptions.get(code, code)} ({code})")
        lines.extend(["", "Você confirma o envio desses dados para registro?"])
        return "\n".join(lines)

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
                if key == "tipoValor":
                    normalized_tipo = self.normalize_tipo_valor(value)
                    if normalized_tipo is None:
                        if "tipoValor" in data:
                            data.pop("tipoValor")
                            changed = True
                        continue
                    value = normalized_tipo
                if key == "fixadorPreco":
                    fixador_normalizado = str(value).strip().lower()
                    fixadores = {
                        "f": "F", "fixador": "F",
                        "i": "I", "importador": "I",
                        "e": "E", "exportador": "E",
                    }
                    if fixador_normalizado not in fixadores:
                        return "VALOR_INVALIDO: fixador do preco deve ser F (Fixador), I (Importador) ou E (Exportador)."
                    value = fixadores[fixador_normalizado]
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
        if confirmar_envio:
            if changed or not data.get("aguardando_confirmacao"):
                # O modelo pode marcar confirmar_envio no mesmo turno em que
                # recebeu dados novos. Nunca envie nesse caso: exiba o resumo
                # e prepare o estado para uma confirmacao posterior do usuario.
                data["aguardando_confirmacao"] = True
                self._save(data)
                return "AGUARDANDO_CONFIRMACAO: " + self._summary(data)
            fixacao = {"valorFixacao": float(data["valorFixacao"])}
            if "diferencial" in data:
                fixacao["diferencial"] = float(data["diferencial"])
            if "tipoValor" in data:
                fixacao["tipoValor"] = str(data["tipoValor"])
            if "fixadorPreco" in data:
                fixacao["fixadorPreco"] = str(data["fixadorPreco"])
            body = {
                **self.build_contract_identifier(data["contratodeVenda"]),
                "fixacaoContrato": [fixacao],
            }
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
        return StructuredTool.from_function(func=self.cadastrar_valor_contrato, name="cadastrar_valor_contrato", description="Cadastra valor/fixacao em contrato existente. Somente contratode_venda e valor_fixacao sao obrigatorios. Preserve exatamente o identificador informado: formatos sem barra, como 012276, serao enviados como contratodeVenda; formatos com barra, como 352/26, serao enviados como numeroVenda; se houver letra final, como 352/26A, a tool separa numeroVenda=352/26 e letraVenda=A. diferencial, tipo_valor e fixador_preco sao opcionais. Se o usuario pedir para adicionar, alterar ou incluir um campo, passe obrigatoriamente esse campo na chamada; nunca chame sem parametros nesses casos. Fixador aceita F/Fixador, I/Importador e E/Exportador. Nunca invente dados. Mostre o resumo retornado. O envio so pode ocorrer com confirmar_envio=True, exclusivamente depois de uma mensagem de confirmacao pura do usuario. Correcao de qualquer campo exige novo resumo e nova confirmacao.")


def create_fixacao_tool(session_id: str) -> StructuredTool:
    return FixacaoTools(session_id).get_tool()
