import sys
import types


def _load_sql_tools_with_stubs(rows):
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

    class SqlClient:
        def execute_function(self, *args, **kwargs):
            return rows

    database_mod.sql_client = SqlClient()
    redis_mod = types.ModuleType("app.core.redis_client")
    redis_mod.redis_client = object()
    sys.modules["app.core"] = core_pkg
    sys.modules["app.core.database"] = database_mod
    sys.modules["app.core.redis_client"] = redis_mod

    validator_mod = types.ModuleType("app.utils.sql_validator")

    class Validator:
        def validate_permission(self, *args, **kwargs):
            return True, ""

    validator_mod.sql_validator = Validator()
    date_parser_mod = types.ModuleType("app.utils.date_parser")

    class DateParser:
        def parse_natural_date(self, value):
            return {"data_inicio": "20260101", "data_fim": "20260713"}

    date_parser_mod.date_parser = DateParser()
    sys.modules["app.utils.sql_validator"] = validator_mod
    sys.modules["app.utils.date_parser"] = date_parser_mod

    models_user_mod = types.ModuleType("app.models.user")

    class UserPermissions:
        telefone = "teste"

    models_user_mod.UserPermissions = UserPermissions
    sys.modules["app.models.user"] = models_user_mod

    from app.agents.sql_tools import SQLTools

    return SQLTools, UserPermissions()


def test_overdue_receivables_total_and_clients_use_same_balance_field():
    rows = [
        {"cliente": "Cardiff Coffee", "valor": 169470.34, "saldo": 100000.00, "contrato": "1/26", "vencimentoReal": "20260101"},
        {"cliente": "Cafe Jandaia MG", "valor": 114359.46, "saldo": 80000.00, "contrato": "2/26", "vencimentoReal": "20260102"},
        {"cliente": "Kraft", "valor": 13493.90, "saldo": 20000.00, "contrato": "3/26", "vencimentoReal": "20260103"},
    ]
    SQLTools, user = _load_sql_tools_with_stubs(rows)
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user = user
    sql_tools.session_id = None
    sql_tools.user_query_original = "Qual o total de contas a receber vencidas?"
    sql_tools.user_query = sql_tools.user_query_original
    sql_tools._salvar_resultado_scheduler = lambda _results: None

    response = sql_tools._pesquisa_contas_a_receber(data_vencimento="vencidas")

    assert "R$ 200.000,00" in response
    assert "Cardiff Coffee: R$ 100.000,00" in response
    assert "Cafe Jandaia MG: R$ 80.000,00" in response
    assert "Kraft: R$ 20.000,00" in response
    assert "169.470,34" not in response
