"""
Resolvedor de campos - converte descrições em códigos via API F3
"""
import logging
import asyncio
import unicodedata
from typing import Optional, Dict, List, Tuple
from rapidfuzz import fuzz, process

from app.core.ada_api_client import ada_api_client

logger = logging.getLogger(__name__)


class FieldResolver:
    """Resolve descrições de campos para códigos via consulta à API F3"""
    
    # Mapeamento de campos Python → campos da API de consulta
    FIELD_MAPPING = {
        "codigo_embalagem": "codigoEmbalagem",
        "codigo_cliente": "codigoCliente",
        "padrao_qualidade": "padraoQualidade",
        "modalidade_pagamento": "modalidadePagamento",
        "condicao_entrega": "condicaoEntrega",
        "moeda_fixacao": "moedaFixacao",
        "tipo_contrato": "tipoContrato",
        "condicao_peso": "condicaoPeso",
        "condicao_pagamento": "condicaoPagamento",
        # Campos opcionais adicionais
        "armazem_preparo": "armazemPreparo",
        "produto_exportacao": "produtoExportacao",
        "responsavel_documento": "responsavelDocumento",
        "embarcador": "embarcador",
        "incoterm": "incoterm",
        "armazem_destino": "armazemDestino",
        "vendedor": "vendedor",
        "spot": "spot",
        "bolsa_fixacao": "bolsaFixacao",
        # Campos de fixação e comissão
        "tipo_preco_fixacao": "tipoPrecoFixacao",
        "tipo_valor": "tipoValor",
        "fixador_preco": "fixadorPreco",
        "codigo_agente_exportacao": "codigoAgenteExportacao",
        "tipo_comissao": "tipoComissao",
    }
    
    # Cache para evitar consultas repetidas na mesma sessão
    _cache: Dict[str, List[Dict]] = {}
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normaliza texto removendo acentos, caracteres especiais e convertendo para lowercase
        
        Exemplos:
            "DÓLAR" → "dolar"
            "Café" → "cafe"
            "US$ KG" → "us kg"
            "CTS/LB" → "cts lb"
        """
        # Remove acentos usando normalização NFD e filtrando marcas diacríticas
        nfd = unicodedata.normalize('NFD', text)
        without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
        
        # Normaliza caracteres especiais comuns
        normalized = without_accents.replace('$', ' ').replace('/', ' ').replace('-', ' ')
        
        # Remove espaços duplicados e converte para lowercase
        normalized = ' '.join(normalized.split()).lower().strip()
        
        return normalized
    
    @classmethod
    async def resolve_field(
        cls, 
        field_name: str, 
        user_input: str, 
        threshold: int = 70
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Resolve um campo convertendo descrição do usuário em código
        
        Args:
            field_name: Nome do campo Python (ex: 'codigo_embalagem')
            user_input: Entrada do usuário (descrição ou código)
            threshold: Score mínimo de similaridade (0-100) para aceitar match
        
        Returns:
            Tupla (codigo, descricao, loja) onde:
            - codigo: código resolvido
            - descricao: descrição do item (ou None)
            - loja: loja do cliente (apenas para codigo_cliente, ou None)
        """
        # Verifica se campo é resolvível
        api_field = cls.FIELD_MAPPING.get(field_name)
        if not api_field:
            logger.info(f"[RESOLVER] Campo '{field_name}' não é resolvível, usando valor direto")
            return (user_input, None, None)
        
        logger.info(f"[RESOLVER] Resolvendo '{field_name}': '{user_input}'")
        logger.info(f"[RESOLVER] Input normalizado: '{cls._normalize_text(user_input)}'")
        
        # Busca registros (usa cache se disponível)
        registros = await cls._get_registros(api_field)
        
        if not registros:
            logger.warning(f"[RESOLVER] Nenhum registro encontrado para '{api_field}'")
            return (user_input, None, None)
        
        logger.info(f"[RESOLVER] {len(registros)} registros disponíveis para matching")
        # Log primeiros registros para debug
        for i, reg in enumerate(registros[:3]):
            logger.info(f"[RESOLVER] Registro #{i+1}: codigo='{reg.get('codigo')}', descricao='{reg.get('descricao')}'")
        
        # Faz matching por similaridade
        best_match = cls._find_best_match(user_input, registros, threshold)
        
        if best_match:
            codigo, descricao, score = best_match
            logger.info(f"[RESOLVER] ✅ Match encontrado: '{descricao}' (score: {score:.1f}%) → código: {codigo}")
            
            # Se for cliente, faz split de código e loja (formato: "00000329 0001")
            if field_name == "codigo_cliente" and " " in codigo:
                partes = codigo.split()
                if len(partes) == 2:
                    codigo_cliente = partes[0]
                    loja_cliente = partes[1]
                    logger.info(f"[RESOLVER] ✅ Cliente split: código='{codigo_cliente}', loja='{loja_cliente}'")
                    return (codigo_cliente, descricao, loja_cliente)
            
            return (codigo, descricao, None)
        else:
            logger.warning(f"[RESOLVER] ⚠️ Nenhum match encontrado (threshold: {threshold}%)")
            logger.warning(f"[RESOLVER] 💡 Tente buscar com threshold mais baixo ou verifique se o nome está correto")
            return (user_input, None, None)
    
    @classmethod
    async def _get_registros(cls, api_field: str) -> List[Dict]:
        """Busca registros da API (com cache)"""
        # Verifica cache
        if api_field in cls._cache:
            logger.info(f"[RESOLVER] Usando cache para '{api_field}' ({len(cls._cache[api_field])} registros)")
            return cls._cache[api_field]
        
        # Consulta API
        logger.info(f"[RESOLVER] Consultando API para '{api_field}'...")
        try:
            result = await ada_api_client.consultar_campo(api_field, filtro="")
            registros = result.get("registros", [])
            
            logger.info(f"[RESOLVER] API retornou {len(registros)} registros para '{api_field}'")
            
            # Log primeiras amostras
            if registros:
                logger.info(f"[RESOLVER] Amostra dos primeiros 5 registros:")
                for i, reg in enumerate(registros[:5]):
                    logger.info(f"[RESOLVER]   [{i+1}] codigo='{reg.get('codigo')}', descricao='{reg.get('descricao')}'")
            else:
                logger.warning(f"[RESOLVER] ⚠️ Nenhum registro retornado pela API!")
            
            # Salva em cache
            cls._cache[api_field] = registros
            
            return registros
        except Exception as e:
            logger.error(f"[RESOLVER] Erro ao consultar API: {e}")
            import traceback
            logger.error(f"[RESOLVER] Traceback: {traceback.format_exc()}")
            return []
    
    @classmethod
    def _find_best_match(
        cls, 
        user_input: str, 
        registros: List[Dict], 
        threshold: int
    ) -> Optional[Tuple[str, str, float]]:
        """
        Encontra melhor match usando fuzzy matching
        
        Args:
            user_input: Texto do usuário
            registros: Lista de {codigo, descricao}
            threshold: Score mínimo para aceitar
        
        Returns:
            Tupla (codigo, descricao, score) ou None
        """
        if not registros:
            return None
        
        # Normaliza input do usuário (remove acentos e converte para lowercase)
        user_input_normalized = cls._normalize_text(user_input)
        
        logger.info(f"[RESOLVER] Buscando match para: '{user_input_normalized}'")
        
        # ETAPA 0: Verifica se o input é exatamente um código válido
        for reg in registros:
            codigo = reg.get("codigo", "")
            if cls._normalize_text(codigo) == user_input_normalized:
                descricao = reg.get("descricao", "")
                logger.info(f"[RESOLVER] ✅ Input é um CÓDIGO válido: '{codigo}' → '{descricao}' (100%)")
                return (codigo, descricao, 100.0)
        
        # Prepara lista de descrições (normaliza removendo acentos e convertendo para minúsculas)
        descricoes = [cls._normalize_text(r.get("descricao", "")) for r in registros]
        
        logger.info(f"[RESOLVER] Comparando com {len(descricoes)} descrições (amostra das 10 primeiras):")
        for i, desc in enumerate(descricoes[:10]):
            logger.info(f"[RESOLVER]   [{i+1}] '{desc}'")
        
        # ETAPA 1: Verifica match exato primeiro (com descrição)
        for idx, desc in enumerate(descricoes):
            if desc == user_input_normalized:
                logger.info(f"[RESOLVER] ✅ Match EXATO encontrado: '{desc}' (100%)")
                best_registro = registros[idx]
                best_descricao_original = best_registro.get("descricao", desc)
                return (best_registro.get("codigo"), best_descricao_original, 100.0)
        
        # ETAPA 2: Usa fuzzy matching com fuzz.ratio (considera comprimento e ordem)
        # ratio é melhor que token_set_ratio para evitar "CD" dar match com "TOP CD"
        result = process.extractOne(
            user_input_normalized,
            descricoes,
            scorer=fuzz.ratio,
            score_cutoff=threshold
        )
        
        logger.info(f"[RESOLVER] Resultado do matching (ratio): {result}")
        
        # ETAPA 3: Se não encontrou com ratio, tenta token_set_ratio mas com threshold mais alto
        if not result:
            logger.info(f"[RESOLVER] Tentando com token_set_ratio (threshold mais alto)...")
            result = process.extractOne(
                user_input_normalized,
                descricoes,
                scorer=fuzz.token_set_ratio,
                score_cutoff=max(threshold + 10, 80)  # Requer score mais alto
            )
            logger.info(f"[RESOLVER] Resultado do matching (token_set_ratio): {result}")
        
        if not result:
            # Mostra os top 3 matches mais próximos para debug
            top_matches = process.extract(
                user_input_normalized,
                descricoes,
                scorer=fuzz.ratio,
                limit=3
            )
            if top_matches:
                logger.warning(f"[RESOLVER] Top 3 matches mais próximos (ratio):")
                for desc, score, idx in top_matches:
                    codigo = registros[idx].get("codigo", "?")
                    desc_original = registros[idx].get("descricao", "?")
                    logger.warning(f"[RESOLVER]   - '{desc_original}' (codigo: {codigo}, score: {score:.1f}%)")
            return None
        
        best_descricao_lower, score, idx = result
        best_registro = registros[idx]
        # Pega a descrição original (com capitalização correta) do registro
        best_descricao_original = best_registro.get("descricao", best_descricao_lower)
        
        return (best_registro.get("codigo"), best_descricao_original, score)
    
    @classmethod
    def _is_likely_code(cls, value: str) -> bool:
        """
        Verifica se valor parece ser um código ao invés de descrição
        
        Heurísticas:
        - Só dígitos
        - Formato curto (< 20 caracteres)
        - Formato específico (ex: 00316, ABC123)
        """
        value_clean = str(value).strip()
        
        # Só dígitos (ex: 00316, 123)
        if value_clean.isdigit():
            return True
        
        # Formato curto e alfanumérico sem espaços (ex: ABC123, XYZ01)
        if len(value_clean) <= 10 and not " " in value_clean:
            return True
        
        return False
    
    @classmethod
    def clear_cache(cls):
        """Limpa cache de consultas"""
        cls._cache.clear()
        logger.info("[RESOLVER] Cache limpo")


# Instância global (stateless, usa cache de classe)
field_resolver = FieldResolver()
