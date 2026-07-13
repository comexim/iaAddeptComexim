import sys
import types


def _load_sql_tools_with_stubs():
    langchain_core = types.ModuleType("langchain_core")
    tools_mod = types.ModuleType("langchain_core.tools")

    class DummyTool:
        @classmethod
        def from_function(cls, *args, **kwargs):
            return (args, kwargs)

    tools_mod.Tool = DummyTool
    tools_mod.StructuredTool = DummyTool
    sys.modules["langchain_core"] = langchain_core
    sys.modules["langchain_core.tools"] = tools_mod

    core_pkg = types.ModuleType("app.core")
    database_mod = types.ModuleType("app.core.database")
    database_mod.sql_client = object()
    redis_mod = types.ModuleType("app.core.redis_client")
    redis_mod.redis_client = object()
    sys.modules["app.core"] = core_pkg
    sys.modules["app.core.database"] = database_mod
    sys.modules["app.core.redis_client"] = redis_mod

    validator_mod = types.ModuleType("app.utils.sql_validator")
    validator_mod.sql_validator = object()
    date_parser_mod = types.ModuleType("app.utils.date_parser")
    date_parser_mod.date_parser = object()
    sys.modules["app.utils.sql_validator"] = validator_mod
    sys.modules["app.utils.date_parser"] = date_parser_mod

    models_user_mod = types.ModuleType("app.models.user")

    class UserPermissions:
        pass

    models_user_mod.UserPermissions = UserPermissions
    sys.modules["app.models.user"] = models_user_mod

    from app.agents.sql_tools import SQLTools

    return SQLTools


def test_safra_code_is_not_treated_as_contract_and_filters_purchases():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = "Qual o volume total da safra 25/26 até agora?"
    sql_tools.user_query = sql_tools.user_query_original

    rows = [
        {"numero": "1", "filial": "05", "SAFRA": "25/26", "quantidade": 100, "valor": 200, "moeda": "BRL"},
        {"numero": "2", "filial": "05", "SAFRA": "2025/2026", "quantidade": 50, "valor": 100, "moeda": "BRL"},
        {"numero": "3", "filial": "05", "SAFRA": "24/25", "quantidade": 999, "valor": 999, "moeda": "BRL"},
    ]

    assert sql_tools._extract_safra_code(sql_tools.user_query_original) == "25/26"

    response = sql_tools._format_results(rows, "IA_Compras")

    assert "Volume total da safra 25/26" in response
    assert "150,00 sacas" in response
    assert "999" not in response
