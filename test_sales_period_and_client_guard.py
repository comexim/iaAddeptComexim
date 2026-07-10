import sys
import types
from datetime import date


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

    class DummyDateParser:
        def get_current_date(self):
            return date(2026, 7, 10)

        def parse_natural_date(self, periodo):
            return None

    date_parser_mod.date_parser = DummyDateParser()
    sys.modules["app.utils.sql_validator"] = validator_mod
    sys.modules["app.utils.date_parser"] = date_parser_mod

    models_user_mod = types.ModuleType("app.models.user")

    class UserPermissions:
        pass

    models_user_mod.UserPermissions = UserPermissions
    sys.modules["app.models.user"] = models_user_mod

    from app.agents.sql_tools import SQLTools

    return SQLTools


def test_sales_month_range_is_not_reduced_to_first_month():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)

    assert sql_tools._parse_periodo_vendas("janeiro a junho de 2026") == {
        "mes_inicio": "2026/01",
        "mes_fim": "2026/06",
    }
    assert sql_tools._parse_periodo_vendas("janeiro a junho de 2025") == {
        "mes_inicio": "2025/01",
        "mes_fim": "2025/06",
    }
    assert sql_tools._parse_periodo_vendas("jan a jun 2025") == {
        "mes_inicio": "2025/01",
        "mes_fim": "2025/06",
    }


def test_sales_metric_request_is_not_detected_as_client():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    query = (
        "Mostre as vendas de janeiro a junho de 2026 com total de contratos, "
        "total de sacas, valor total, moeda e média por saca. "
        "A média deve ser valor total dividido por sacas."
    )

    assert sql_tools._extract_client_name(query) is None
