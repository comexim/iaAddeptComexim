"""
Validador de queries SQL e permissões
"""
import logging
from typing import Dict, Optional, List
from app.models.user import UserPermissions, PermissionType

logger = logging.getLogger(__name__)


# Mapeamento: Função SQL → Permissão necessária
FUNCTION_PERMISSIONS: Dict[str, PermissionType] = {
    "IA_Vendas": "Vendas",
    "IA_Compras": "Compras",
    "IA_ContasPagas": "Financeiro",
    "IA_ContasAPagar": "Financeiro",
    "IA_ContasAReceber": "Financeiro",
    "IA_SaldoBancario": "Financeiro",
    "IA_Estoque": "Estoque",
    "IA_Orcamento": "Orçamento",
    "IA_Cotacao": "Vendas",
    "IA_DespesaVenda": "Vendas"
}


# Funções que EXIGEM filtros WHERE
FUNCTIONS_REQUIRING_WHERE = {
    "IA_Vendas": {
        "required_field": "mesEmbarque",
        "alternative_field": "emissao",  # Aceita também data de emissão
        "format": "YYYY/MM ou YYYYMMDD",
        "prompt": "De qual período você gostaria de consultar? (Ex: dezembro de 2025, hoje, sexta-feira passada)"
    },
    "IA_Compras": {
        "required_field": "emissao",
        "format": "YYYYMMDD",
        "prompt": "A partir de qual data? (Ex: últimos 7 dias, 05/12/2025)"
    },
    "IA_ContasPagas": {
        "required_field": "emissao",
        "format": "YYYYMMDD",
        "prompt": "Qual período de pagamento? (Ex: este mês, últimos 30 dias)"
    },
    "IA_ContasAPagar": {
        "required_field": "vencimento",
        "format": "YYYYMMDD",
        "prompt": "Para qual data de vencimento? (Ex: hoje, próximos 7 dias)"
    },
    "IA_Orcamento": {
        "required_fields": ["ano", "mes"],
        "format": "ano=YYYY, mes=MM",
        "prompt": "De qual mês e ano? (Ex: dezembro de 2025)"
    }
}


# Funções que NÃO precisam de WHERE (snapshot/poucos dados)
FUNCTIONS_WITHOUT_WHERE = ["IA_SaldoBancario", "IA_Estoque", "IA_Cotacao"]


class SQLValidator:
    """Validador de queries SQL e permissões"""

    @staticmethod
    def validate_permission(
        user: UserPermissions,
        function_name: str
    ) -> tuple[bool, Optional[str]]:
        """
        Valida se usuário tem permissão para executar função

        Args:
            user: Usuário autenticado
            function_name: Nome da função SQL

        Returns:
            (is_valid, error_message)
        """
        required_permission = FUNCTION_PERMISSIONS.get(function_name)

        if not required_permission:
            logger.warning(f"Função SQL desconhecida: {function_name}")
            return False, f"Função {function_name} não está configurada no sistema."

        if not user.has_permission(required_permission):
            logger.warning(
                f"Usuário {user.nome} não tem permissão {required_permission} "
                f"para executar {function_name}"
            )
            return False, f"Você não tem permissão para acessar informações de {required_permission}."

        return True, None

    @staticmethod
    def validate_filters(
        function_name: str,
        filters: Optional[Dict[str, any]] = None
    ) -> tuple[bool, Optional[str], bool]:
        """
        Valida se query possui filtros obrigatórios

        Args:
            function_name: Nome da função SQL
            filters: Filtros fornecidos

        Returns:
            (is_valid, error_message, needs_clarification)
        """
        # Funções sem WHERE podem executar direto
        if function_name in FUNCTIONS_WITHOUT_WHERE:
            return True, None, False

        # Funções com WHERE obrigatório
        if function_name in FUNCTIONS_REQUIRING_WHERE:
            config = FUNCTIONS_REQUIRING_WHERE[function_name]

            # Verifica se filtros foram fornecidos
            if not filters:
                return False, config["prompt"], True

            # Valida campos obrigatórios
            if "required_fields" in config:
                missing = [f for f in config["required_fields"] if f not in filters or not filters[f]]
                if missing:
                    return False, config["prompt"], True
            else:
                # Verifica se tem o campo principal OU os campos alternativos
                has_required = config["required_field"] in filters and filters[config["required_field"]]
                has_alternatives = False

                # Suporta alternative_field (singular) para campo alternativo único
                if "alternative_field" in config:
                    alt_field = config["alternative_field"]
                    has_alternatives = alt_field in filters and filters[alt_field]

                # Suporta alternative_fields (plural) para múltiplos campos alternativos
                elif "alternative_fields" in config:
                    # Verifica se TODOS os campos alternativos estão presentes
                    alt_fields = config["alternative_fields"]
                    has_alternatives = all(f in filters and filters[f] for f in alt_fields)

                if not has_required and not has_alternatives:
                    return False, config["prompt"], True

            return True, None, False

        # Função desconhecida
        logger.warning(f"Função {function_name} não configurada para validação de filtros")
        return True, None, False  # Permite executar por padrão

    @staticmethod
    def get_required_permission(function_name: str) -> Optional[PermissionType]:
        """Retorna permissão necessária para função"""
        return FUNCTION_PERMISSIONS.get(function_name)

    @staticmethod
    def requires_filters(function_name: str) -> bool:
        """Verifica se função requer filtros WHERE"""
        return function_name in FUNCTIONS_REQUIRING_WHERE

    @staticmethod
    def get_filter_prompt(function_name: str) -> Optional[str]:
        """Retorna prompt para solicitar filtros"""
        config = FUNCTIONS_REQUIRING_WHERE.get(function_name)
        return config["prompt"] if config else None


# Instância global
sql_validator = SQLValidator()
