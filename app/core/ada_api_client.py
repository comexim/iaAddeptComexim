"""
Cliente para API ADA (Autenticação e criação de contratos)
"""
import json
import logging
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)


class ADAApiClient:
    """Cliente para comunicação com API ADA"""

    def __init__(self):
        self.base_url = settings.ada_api_url
        self.username = settings.ada_username
        self.password = settings.ada_password
        self.token = None
        self.token_expiry = None

    def _fix_malformed_json(self, text: str) -> str:
        """
        Corrige JSON malformado retornado pela API F3
        
        A API retorna JSON com erros de sintaxe:
        - {"code:" "201" → {"code": "201"
        - "registros: [" → "registros": ["
        - Barras invertidas sem escape: "C\LOGO" → "C\\LOGO"
        
        Args:
            text: Texto JSON malformado
        
        Returns:
            Texto JSON corrigido
        """
        import re
        
        # Corrige chaves sem fechamento de aspas antes dos dois pontos
        # "code:" → "code":
        # "message:" → "message":
        # "registros: → "registros":
        text = re.sub(r'"(\w+):\s*"', r'"\1": "', text)
        
        # Corrige "registros: [" → "registros": [
        text = re.sub(r'"registros:\s*\[', r'"registros": [', text)
        
        # Corrige array de objetos que está como string escapada
        # Remove aspas extras ao redor dos objetos dentro do array
        # "registros": ["{"codigo": → "registros": [{"codigo":
        text = re.sub(r'\["(\{)', r'[\1', text)
        text = re.sub(r'(\})"]\}', r'\1]}', text)
        
        # Corrige barras invertidas sem escape correto
        # "C\LOGO" → "C\\LOGO" (escapa a barra invertida)
        # Mas preserva escapes válidos: \", \\, \/, \b, \f, \n, \r, \t, \u
        text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
        
        return text

    async def get_token(self) -> str:
        """
        Obtém token de autenticação OAuth2
        
        Returns:
            Token de acesso
        
        Raises:
            Exception: Se falhar na autenticação
        """
        # Verifica se já tem token válido
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            logger.info("[ADA API] Token ainda válido, reutilizando")
            return self.token

        logger.info("[ADA API] Obtendo novo token de autenticação...")
        
        url = f"{self.base_url}/rest/ia/api/oauth2/v1/token"
        
        # OAuth2 geralmente usa POST com form data
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Tenta primeiro com POST form data (padrão OAuth2)
                response = await client.post(url, data=data)
                response.raise_for_status()
                
                result = response.json()
                self.token = result.get("access_token")
                
                # Define expiração para 1 hora (padrão OAuth2)
                self.token_expiry = datetime.now() + timedelta(hours=1)
                
                logger.info("[ADA API] ✅ Token obtido com sucesso")
                return self.token

        except httpx.HTTPStatusError as e:
            logger.error(f"[ADA API] ❌ Erro HTTP ao obter token: {e.response.status_code}")
            logger.error(f"[ADA API] Response: {e.response.text}")
            raise Exception(f"Falha na autenticação ADA API: {e.response.status_code}")
        except Exception as e:
            logger.error(f"[ADA API] ❌ Erro ao obter token: {e}")
            raise Exception(f"Erro ao conectar com ADA API: {str(e)}")

    async def criar_contrato_venda(self, dados_contrato: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria um contrato de venda/exportação via API
        
        Args:
            dados_contrato: Dados do contrato (dict/JSON)
        
        Returns:
            Resposta da API
        
        Raises:
            Exception: Se falhar na criação
        """
        logger.info("[ADA API] Criando contrato de venda...")
        logger.info(f"[ADA API] Dados: {dados_contrato}")

        # Obtém token
        token = await self.get_token()

        url = f"{self.base_url}/rest/ia/api/v1/postADA/vendaExp"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=dados_contrato, headers=headers)
                
                # Log detalhado da resposta
                logger.info(f"[ADA API] Status Code: {response.status_code}")
                logger.info(f"[ADA API] Headers: {dict(response.headers)}")
                logger.info(f"[ADA API] Texto bruto: {response.text[:500]}")
                
                # Verificar status HTTP
                if not (200 <= response.status_code < 300):
                    logger.error(f"[ADA API] ❌ Erro HTTP {response.status_code}: {response.text}")
                    raise Exception(f"Erro HTTP {response.status_code}: {response.text}")
                
                # Parsear resposta (JSON pode estar malformado)
                texto = response.text
                result = None
                try:
                    result = response.json()
                except Exception:
                    logger.warning("[ADA API] ⚠️ JSON malformado, extraindo dados manualmente...")
                
                # Detectar erro no BODY mesmo com HTTP 200
                # A API retorna HTTP 200 mas com errorCode/errorMessage no body
                import re
                has_error = False
                error_msg = ""
                
                if result and isinstance(result, dict):
                    error_code = result.get("errorCode")
                    if error_code and int(error_code) >= 400:
                        has_error = True
                        error_msg = result.get("errorMessage", "")
                        erros = result.get("erros", [])
                        if erros:
                            error_msg += " Erros: " + ", ".join(str(e) for e in erros)
                else:
                    # JSON malformado — tenta regex no texto bruto
                    match_error_code = re.search(r'"errorCode"\s*:\s*(\d+)', texto)
                    if match_error_code and int(match_error_code.group(1)) >= 400:
                        has_error = True
                        match_error_msg = re.search(r'"errorMessage"\s*:\s*([^,}]+)', texto)
                        error_msg = match_error_msg.group(1).strip('" ') if match_error_msg else ""
                        match_erros = re.search(r'"erros"\s*:\s*\[([^\]]+)\]', texto)
                        if match_erros:
                            error_msg += " Erros: " + match_erros.group(1).strip()
                
                if has_error:
                    logger.error(f"[ADA API] ❌ Erro retornado pela API: {error_msg}")
                    raise Exception(f"API retornou erro: {error_msg}")
                
                # Sucesso — extrair dados da resposta
                if result and isinstance(result, dict):
                    logger.info("[ADA API] ✅ Contrato criado com sucesso!")
                    logger.info(f"[ADA API] Resposta: {result}")
                    return result
                
                # Fallback para JSON malformado mas sem erro
                match_contrato = re.search(r'Contrato (\d+)', texto)
                numero_contrato = match_contrato.group(1) if match_contrato else None
                
                match_message = re.search(r'"message"\s*:\s*"([^"]+)"', texto)
                mensagem = match_message.group(1) if match_message else "Contrato criado"
                
                match_alertas = re.search(r'Alertas:\s*\[([^\]]*)', texto)
                alertas = match_alertas.group(1).strip('" ') if match_alertas else None
                
                resultado = {
                    "code": "201",
                    "message": mensagem,
                    "numeroContrato": numero_contrato,
                    "alertas": [alertas] if alertas else []
                }
                
                logger.info("[ADA API] ✅ Contrato criado com sucesso!")
                logger.info(f"[ADA API] Número: {numero_contrato}")
                return resultado

        except httpx.HTTPStatusError as e:
            logger.error(f"[ADA API] ❌ Erro HTTP ao criar contrato: {e.response.status_code}")
            logger.error(f"[ADA API] Response: {e.response.text}")
            
            # Tenta extrair mensagem de erro
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", error_data.get("error", str(e)))
            except:
                error_msg = e.response.text
            
            raise Exception(f"Erro ao criar contrato: {error_msg}")
        
        except Exception as e:
            logger.error(f"[ADA API] ❌ Erro ao criar contrato: {e}")
            raise Exception(f"Erro ao criar contrato: {str(e)}")

    async def consultar_campo(self, nome_campo: str, filtro: str = "") -> Dict[str, Any]:
        """
        Consulta valores possíveis para um campo via API F3
        
        Args:
            nome_campo: Nome do campo a consultar (ex: 'codigoEmbalagem', 'codigoCliente', etc)
            filtro: Filtro opcional para a consulta
        
        Returns:
            Dict com registros encontrados: {"code": "201", "registros": [{"codigo": "X", "descricao": "Y"}]}
        
        Raises:
            Exception: Se falhar na consulta
        """
        logger.info(f"[ADA API] Consultando campo '{nome_campo}' com filtro '{filtro}'...")
        
        # Obtém token
        token = await self.get_token()
        
        url = f"{self.base_url}/rest/ia/api/wsgetF3/v1/consulta"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        body = {
            "consulta": nome_campo,
            "filtro": filtro
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # GET com JSON body - usa request() genérico
                response = await client.request(
                    method="GET",
                    url=url,
                    json=body,
                    headers=headers
                )
                
                logger.info(f"[ADA API] Status Code: {response.status_code}")
                logger.info(f"[ADA API] Headers: {dict(response.headers)}")
                logger.info(f"[ADA API] Texto completo da resposta: {response.text[:500]}...")
                
                if not (200 <= response.status_code < 300):
                    logger.error(f"[ADA API] ❌ Erro HTTP {response.status_code}: {response.text}")
                    raise Exception(f"Erro HTTP {response.status_code}: {response.text}")
                
                # Corrige JSON malformado da API
                texto_corrigido = self._fix_malformed_json(response.text)
                
                # Tenta parsear JSON
                try:
                    result = json.loads(texto_corrigido)
                except Exception as json_error:
                    logger.error(f"[ADA API] ❌ Erro ao parsear JSON: {json_error}")
                    logger.error(f"[ADA API] Resposta original: {response.text[:200]}")
                    logger.error(f"[ADA API] Resposta corrigida: {texto_corrigido[:200]}")
                    raise Exception(f"Resposta não é JSON válido: {json_error}")
                
                # Verifica se há erro no body
                if result.get("code") and int(result.get("code")) >= 400:
                    error_msg = result.get("message", "Erro desconhecido")
                    logger.error(f"[ADA API] ❌ Erro na consulta: {error_msg}")
                    raise Exception(f"Erro na consulta: {error_msg}")
                
                registros = result.get("registros", [])
                logger.info(f"[ADA API] ✅ Consulta realizada: {len(registros)} registro(s) encontrado(s)")
                
                return result
        
        except httpx.HTTPStatusError as e:
            logger.error(f"[ADA API] ❌ Erro HTTP ao consultar campo: {e.response.status_code}")
            logger.error(f"[ADA API] Response: {e.response.text}")
            raise Exception(f"Erro ao consultar campo: {e.response.status_code}")
        
        except Exception as e:
            logger.error(f"[ADA API] ❌ Erro ao consultar campo: {e}")
            raise Exception(f"Erro ao consultar campo: {str(e)}")

    async def test_connection(self) -> bool:
        """
        Testa conexão com a API
        
        Returns:
            True se conectou com sucesso
        """
        try:
            token = await self.get_token()
            return bool(token)
        except:
            return False


# Instância global
ada_api_client = ADAApiClient()
