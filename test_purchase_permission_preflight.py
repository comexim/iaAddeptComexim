from unittest.mock import patch

from app.agents.sql_tools import SQLTools


class UserWithoutPurchasePermission:
    nome = "Usuário sem Compras"
    telefone = "5511999999999"

    @staticmethod
    def has_permission(permission):
        return permission != "Compras"


def test_purchase_permission_is_checked_before_date_parsing_or_database_access():
    tools = SQLTools.__new__(SQLTools)
    tools.user = UserWithoutPurchasePermission()

    with patch.object(tools, "_parse_periodo_compras") as parse_period, patch(
        "app.agents.sql_tools.sql_client.execute_procedure"
    ) as execute_procedure:
        result = tools._pesquisa_compras(data_inicio="hoje")

    assert result == "Você não tem permissão para acessar informações de Compras."
    parse_period.assert_not_called()
    execute_procedure.assert_not_called()
