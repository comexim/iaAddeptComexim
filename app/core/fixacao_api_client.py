"""Cliente da API CMX para cadastrar valor/fixacao em contrato existente."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


_SECRET_KEYS = {
    "access_token", "authorization", "client_secret", "password",
    "refresh_token", "senha", "token", "username", "usuario",
}


def _redact_secrets(value: Any) -> Any:
    """Mascara credenciais antes de registrar requests e responses da CMX."""
    if isinstance(value, dict):
        return {
            key: "***" if str(key).lower() in _SECRET_KEYS else _redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _json_for_log(value: Any) -> str:
    return json.dumps(_redact_secrets(value), ensure_ascii=False, default=str)


def _response_for_log(response: Any) -> str:
    """Retorna o corpo completo quando for JSON e texto limitado nos demais casos."""
    try:
        return _json_for_log(response.json())
    except ValueError:
        return str(response.text or "")[:10000]


class FixacaoApiClient:
    def __init__(self):
        self._token = None
        self._token_expiry = None

    async def get_token(self) -> str:
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token
        if not settings.cmx_username or not settings.cmx_password:
            raise RuntimeError("Credenciais da API CMX nao configuradas")
        url = f"{settings.cmx_api_url.rstrip('/')}{settings.cmx_token_path}"
        params = {"grant_type": "password", "username": settings.cmx_username, "password": settings.cmx_password}
        logger.info(
            "[CMX AUTH] REQUEST method=POST url=%s params=%s",
            url,
            _json_for_log(params),
        )
        try:
            async with httpx.AsyncClient(timeout=30, verify=settings.cmx_verify_ssl) as client:
                response = await client.post(url, params=params)
        except Exception as exc:
            logger.exception(
                "[CMX AUTH] SEM RESPOSTA tipo=%s detalhe=%r",
                type(exc).__name__,
                str(exc),
            )
            raise
        logger.info(
            "[CMX AUTH] RESPONSE status=%s body=%s",
            response.status_code,
            _response_for_log(response),
        )
        if not 200 <= response.status_code < 300:
            logger.error(
                "[CMX AUTH] POST do token recusado: HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )
            raise RuntimeError(f"Autenticacao CMX recusada (HTTP {response.status_code})")
        result = response.json()
        token = result.get("access_token")
        if not token:
            raise RuntimeError("A API CMX nao retornou access_token")
        expires_in = max(60, int(result.get("expires_in", 3600)) - 60)
        self._token = token
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
        return token

    async def cadastrar_fixacao(self, body: Dict[str, Any]) -> Dict[str, Any]:
        token = await self.get_token()
        url = f"{settings.cmx_api_url.rstrip('/')}{settings.cmx_fixacao_path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "tenantid": settings.cmx_tenant_id}
        contract_identifier = {
            key: body[key]
            for key in ("contratodeVenda", "numeroVenda", "letraVenda")
            if body.get(key) not in (None, "")
        }
        safe_headers = {
            "Authorization": "***",
            "Content-Type": headers["Content-Type"],
            "tenantid": headers["tenantid"],
        }
        logger.info(
            "[CMX Z24] REQUEST method=POST url=%s headers=%s body=%s",
            url,
            _json_for_log(safe_headers),
            _json_for_log(body),
        )
        try:
            async with httpx.AsyncClient(timeout=60, verify=settings.cmx_verify_ssl) as client:
                response = await client.post(url, json=body, headers=headers)
        except Exception as exc:
            logger.exception(
                "[CMX Z24] SEM RESPOSTA contrato=%s tipo=%s detalhe=%r",
                contract_identifier,
                type(exc).__name__,
                str(exc),
            )
            raise
        logger.info(
            "[CMX Z24] RESPONSE status=%s body=%s",
            response.status_code,
            _response_for_log(response),
        )
        if response.status_code == 401:
            # O token pode ser invalidado pela CMX antes do prazo informado.
            # Renova uma unica vez e repete exatamente a mesma operacao.
            logger.warning("[CMX Z24] Token recusado; renovando e tentando novamente")
            self._token = None
            self._token_expiry = None
            token = await self.get_token()
            headers["Authorization"] = f"Bearer {token}"
            logger.info(
                "[CMX Z24] RETRY REQUEST method=POST url=%s headers=%s body=%s",
                url,
                _json_for_log(safe_headers),
                _json_for_log(body),
            )
            try:
                async with httpx.AsyncClient(timeout=60, verify=settings.cmx_verify_ssl) as client:
                    response = await client.post(url, json=body, headers=headers)
            except Exception as exc:
                logger.exception(
                    "[CMX Z24] RETRY SEM RESPOSTA contrato=%s tipo=%s detalhe=%r",
                    contract_identifier,
                    type(exc).__name__,
                    str(exc),
                )
                raise
            logger.info(
                "[CMX Z24] RETRY RESPONSE status=%s body=%s",
                response.status_code,
                _response_for_log(response),
            )
        if not 200 <= response.status_code < 300:
            logger.error("[CMX Z24] Falha HTTP %s: %s", response.status_code, response.text[:500])
            raise RuntimeError(f"API CMX retornou HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError:
            return {"status_code": response.status_code, "message": response.text}

        # A CMX pode responder HTTP 200 e informar falha funcional no JSON.
        if isinstance(result, dict):
            error_code = result.get("errorCode", result.get("code"))
            try:
                has_error = error_code not in (None, "") and int(error_code) >= 400
            except (TypeError, ValueError):
                has_error = bool(error_code)

            if has_error:
                error_message = str(
                    result.get("errorMessage")
                    or result.get("message")
                    or "Operação recusada pela API CMX"
                ).strip()
                attention = str(result.get("atencao") or "").strip()
                errors = result.get("inconsistencias") or result.get("erros") or []
                if isinstance(errors, str):
                    errors = [errors]
                details = "; ".join(str(item).strip() for item in errors if str(item).strip())
                parts = [error_message]
                if details:
                    parts.append(f"Motivo: {details}")
                if attention:
                    parts.append(f"Atenção: {attention}")
                full_message = " ".join(parts).strip()
                logger.warning("[CMX Z24] Erro funcional %s: %s", error_code, full_message)
                raise RuntimeError(full_message)

        return result

    async def consultar_corretoras_bolsa(self) -> Dict[str, Any]:
        """Consulta códigos e descrições de corretoras disponíveis no F3."""
        token = await self.get_token()
        url = f"{settings.cmx_api_url.rstrip('/')}{settings.cmx_f3_path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "tenantid": settings.cmx_tenant_id,
        }
        body = {"consulta": "CORRETORABOLSA", "filtro": ""}
        logger.info("[CMX F3] REQUEST method=GET url=%s body=%s", url, _json_for_log(body))
        try:
            async with httpx.AsyncClient(timeout=30, verify=settings.cmx_verify_ssl) as client:
                response = await client.request("GET", url, json=body, headers=headers)
        except Exception as exc:
            logger.exception(
                "[CMX F3] SEM RESPOSTA tipo=%s detalhe=%r",
                type(exc).__name__,
                str(exc),
            )
            raise
        logger.info(
            "[CMX F3] RESPONSE status=%s body=%s",
            response.status_code,
            _response_for_log(response),
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Consulta de corretoras retornou HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError as exc:
            logger.warning("[CMX F3] Resposta não JSON: %s", response.text[:300])
            raise RuntimeError("Consulta de corretoras retornou resposta inválida") from exc

        def find_records(value: Any) -> list:
            """Aceita lista direta ou listas sob registros/data/items/resultado."""
            if isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    return value
                return []
            if not isinstance(value, dict):
                return []
            preferred = ("registros", "records", "data", "items", "resultado", "result")
            for key in preferred:
                records = find_records(value.get(key))
                if records:
                    return records
            for nested in value.values():
                records = find_records(nested)
                if records:
                    return records
            return []

        records = find_records(result)
        if not records:
            structure = sorted(result.keys()) if isinstance(result, dict) else type(result).__name__
            logger.warning("[CMX F3] Nenhuma lista de registros; estrutura=%s", structure)
            message = result.get("message") if isinstance(result, dict) else None
            raise RuntimeError(str(message or "Consulta de corretoras não retornou registros"))

        normalized_records = []
        for record in records:
            casefolded = {str(key).lower(): value for key, value in record.items()}
            code = (
                casefolded.get("codigo")
                or casefolded.get("code")
                or casefolded.get("cod")
            )
            description = (
                casefolded.get("descricao")
                or casefolded.get("description")
                or casefolded.get("nome")
            )
            if code not in (None, "") and description not in (None, ""):
                normalized_records.append({"codigo": str(code), "descricao": str(description)})

        if not normalized_records:
            logger.warning(
                "[CMX F3] %s registro(s) sem campos reconhecidos de código/descrição",
                len(records),
            )
            raise RuntimeError("Consulta de corretoras retornou campos não reconhecidos")

        logger.info("[CMX F3] %s corretora(s) carregada(s)", len(normalized_records))
        return {"registros": normalized_records}

    async def cadastrar_hedge(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Envia o Hedge confirmado ao endpoint Z03."""
        token = await self.get_token()
        url = f"{settings.cmx_api_url.rstrip('/')}{settings.cmx_hedge_path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "tenantid": settings.cmx_tenant_id,
        }
        logger.info(
            "[CMX Z03] REQUEST method=POST url=%s body=%s",
            url,
            _json_for_log(body),
        )
        try:
            async with httpx.AsyncClient(timeout=60, verify=settings.cmx_verify_ssl) as client:
                response = await client.post(url, json=body, headers=headers)
        except Exception as exc:
            logger.exception(
                "[CMX Z03] SEM RESPOSTA tipo=%s detalhe=%r",
                type(exc).__name__,
                str(exc),
            )
            raise
        logger.info(
            "[CMX Z03] RESPONSE status=%s body=%s",
            response.status_code,
            _response_for_log(response),
        )
        if not 200 <= response.status_code < 300:
            logger.error("[CMX Z03] Falha HTTP %s: %s", response.status_code, response.text[:500])
            raise RuntimeError(f"API CMX retornou HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError:
            return {"status_code": response.status_code, "message": response.text}
        if isinstance(result, dict):
            error_code = result.get("errorCode", result.get("code"))
            try:
                has_error = error_code not in (None, "") and int(error_code) >= 400
            except (TypeError, ValueError):
                has_error = bool(error_code)
            if has_error:
                message = str(
                    result.get("errorMessage")
                    or result.get("message")
                    or "Não foi possível cadastrar o Hedge"
                ).strip()
                errors = result.get("erros") or []
                if isinstance(errors, str):
                    errors = [errors]
                details = "; ".join(str(item).strip() for item in errors if str(item).strip())
                raise RuntimeError(f"{message} {details}".strip())
        return result


fixacao_api_client = FixacaoApiClient()
