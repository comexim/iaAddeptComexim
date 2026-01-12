"""
Cliente Redis para cache, memória de conversação e anti-flood
"""
import redis.asyncio as redis
import json
import logging
from typing import Optional, List, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Cliente Redis para operações assíncronas"""

    def __init__(self):
        self.redis_url = settings.redis_url
        self._client: Optional[redis.Redis] = None
        logger.info(f"[DEBUG] RedisClient.__init__: redis_url = {self.redis_url}")

    async def get_client(self) -> redis.Redis:
        """Obtém cliente Redis (singleton) com reconexão automática"""
        if self._client is None:
            logger.info(f"[DEBUG] Conectando ao Redis: {self.redis_url}")
            self._client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            logger.info("Cliente Redis inicializado")
        else:
            # Testa se a conexão ainda está ativa
            try:
                await self._client.ping()
            except Exception as e:
                logger.warning(f"Conexão Redis perdida: {e}. Reconectando...")
                try:
                    await self._client.close()
                except:
                    pass
                self._client = await redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )
                logger.info("Reconexão Redis bem-sucedida")
        return self._client

    async def close(self):
        """Fecha conexão com Redis"""
        if self._client:
            await self._client.close()
            logger.info("Conexão com Redis fechada")

    # ====================
    # Anti-Flood Buffer
    # ====================

    async def push_message(self, session_id: str, message: str) -> int:
        """
        Adiciona mensagem ao buffer anti-flood

        Args:
            session_id: ID da sessão (telefone ou conversation_id)
            message: Mensagem a ser adicionada

        Returns:
            Tamanho da lista após inserção
        """
        client = await self.get_client()
        key = f"chat-buffer:{session_id}"
        length = await client.rpush(key, message)
        await client.expire(key, 300)  # Expira em 5 minutos
        logger.debug(f"Mensagem adicionada ao buffer {session_id}. Total: {length}")
        return length

    async def get_buffered_messages(self, session_id: str) -> List[str]:
        """
        Obtém todas as mensagens do buffer

        Args:
            session_id: ID da sessão

        Returns:
            Lista de mensagens
        """
        client = await self.get_client()
        key = f"chat-buffer:{session_id}"
        messages = await client.lrange(key, 0, -1)
        logger.debug(f"Recuperadas {len(messages)} mensagens do buffer {session_id}")
        return messages

    async def clear_buffer(self, session_id: str):
        """Remove buffer de mensagens"""
        client = await self.get_client()
        key = f"chat-buffer:{session_id}"
        await client.delete(key)
        logger.debug(f"Buffer {session_id} deletado")

    # ====================
    # User Cache
    # ====================

    async def cache_user(self, phone: str, user_data: dict, ttl: int = 3600):
        """
        Cacheia dados do usuário

        Args:
            phone: Telefone do usuário
            user_data: Dados do usuário
            ttl: Tempo de vida em segundos (default: 1h)
        """
        client = await self.get_client()
        key = f"user:{phone}"
        await client.setex(key, ttl, json.dumps(user_data, ensure_ascii=False))
        logger.debug(f"Usuário {phone} cacheado por {ttl}s")

    async def get_cached_user(self, phone: str) -> Optional[dict]:
        """Recupera usuário do cache"""
        client = await self.get_client()
        key = f"user:{phone}"
        data = await client.get(key)
        if data:
            logger.debug(f"Usuário {phone} encontrado no cache")
            return json.loads(data)
        logger.debug(f"Usuário {phone} não encontrado no cache")
        return None

    # ====================
    # Generic Operations
    # ====================

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Define valor no Redis"""
        client = await self.get_client()
        serialized = json.dumps(value) if not isinstance(value, str) else value

        if ttl:
            await client.setex(key, ttl, serialized)
        else:
            await client.set(key, serialized)

    async def get(self, key: str) -> Optional[Any]:
        """Obtém valor do Redis"""
        client = await self.get_client()
        value = await client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def delete(self, key: str):
        """Deleta chave do Redis"""
        client = await self.get_client()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        """Verifica se chave existe"""
        client = await self.get_client()
        return await client.exists(key) > 0


# Instância global do cliente
redis_client = RedisClient()
