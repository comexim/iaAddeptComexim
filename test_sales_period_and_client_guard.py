import sys
import types
from datetime import date


def _load_sql_tools_with_stubs():
    sys.modules.pop("app.agents.sql_tools", None)

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


def test_sales_purchase_volume_comparison_is_not_detected_as_client():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    query = "Compare o volume comprado com o volume vendido em junho de 2026."

    assert sql_tools._extract_client_name(query) is None


def test_second_semester_is_never_detected_as_client():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    query = (
        "Aron, mostre as vendas mês a mês do segundo semestre de 2026, "
        "com contratos, sacas e valor total."
    )

    assert sql_tools._extract_client_name(query) is None


def test_partial_monthly_sales_output_names_missing_months():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = "Mostre as vendas por mês de julho a outubro de 2026"
    sql_tools.user_query = sql_tools.user_query_original
    sql_tools._series_expected_months = ["2026/07", "2026/08", "2026/09", "2026/10"]
    sql_tools._series_date_fields = ("mesEmbarque",)
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/07", "sacas": 10, "valorTotal": 1000},
        {"contrato": "2", "filial": "05", "cliente": "B", "mesEmbarque": "2026/09", "sacas": 20, "valorTotal": 3000},
    ]

    output = sql_tools._format_results(rows, "IA_Vendas")

    assert "2026/07" in output
    assert "2026/09" in output
    assert "Meses sem registros: 2026/08, 2026/10." in output
    assert "2026/08:" not in output
    assert "2026/10:" not in output


def test_empty_period_uses_required_message():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = "Vendas por mês em 2099"
    sql_tools.user_query = sql_tools.user_query_original

    assert sql_tools._format_results([], "IA_Vendas") == (
        "Não foram encontrados registros para esse período."
    )


def test_unmapped_monthly_series_fails_closed_instead_of_estimating():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = "Mostre a evolução mensal do saldo"
    sql_tools.user_query = sql_tools.user_query_original
    sql_tools._series_expected_months = []
    sql_tools._series_date_fields = None

    output = sql_tools._format_results([{"saldo": 100}], "IA_SaldoBancario")

    assert "Não foi possível montar esta série mensal de forma determinística" in output
    assert "nenhum mês ou valor foi completado" in output


def test_monthly_sales_divergence_is_blocked_before_answer():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = "Vendas mês a mês do segundo semestre"
    sql_tools.user_query = sql_tools.user_query_original
    sql_tools._series_expected_months = ["2026/07", "2026/08"]
    sql_tools._series_date_fields = ("mesEmbarque",)
    sql_tools._series_query_context = {
        "procedure": "usp_IA_Vendas",
        "params": {"MesIni": "2026/07", "MesFim": "2026/08"},
    }
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/07", "sacas": 10, "valorTotal": 1000},
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/08", "sacas": 10, "valorTotal": 1000},
    ]

    output = sql_tools._format_results(rows, "IA_Vendas")

    assert "Foi encontrada uma inconsistência na reconciliação mensal" in output
    assert "Total agregado: 1 contrato(s)" in output
    assert "Soma dos meses: 2 contrato(s)" in output
    assert "Vendas por mês:" not in output
