"""Cliente da API CMX para cadastrar valor/fixacao em contrato existente."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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
        async with httpx.AsyncClient(timeout=30, verify=settings.cmx_verify_ssl) as client:
            response = await client.post(url, params=params)
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
        async with httpx.AsyncClient(timeout=60, verify=settings.cmx_verify_ssl) as client:
            response = await client.post(url, json=body, headers=headers)
        if not 200 <= response.status_code < 300:
            logger.error("[CMX Z24] Falha HTTP %s: %s", response.status_code, response.text[:500])
            raise RuntimeError(f"API CMX retornou HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError:
            return {"status_code": response.status_code, "message": response.text}

        # A CMX pode responder HTTP 200 e informar falha funcional no JSON.
        if isinstance(result, dict):
            error_code = result.get("errorCode")
            try:
                has_error = error_code not in (None, "") and int(error_code) >= 400
            except (TypeError, ValueError):
                has_error = bool(error_code)

            if has_error:
                error_message = str(result.get("errorMessage") or "Operacao recusada pela API CMX").strip()
                errors = result.get("erros") or []
                if isinstance(errors, str):
                    errors = [errors]
                details = "; ".join(str(item).strip() for item in errors if str(item).strip())
                full_message = f"{error_message} {details}".strip()
                logger.warning("[CMX Z24] Erro funcional %s: %s", error_code, full_message)
                raise RuntimeError(full_message)

        return result


fixacao_api_client = FixacaoApiClient()
