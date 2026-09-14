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

    dateutil_mod = types.ModuleType("dateutil")
    relativedelta_mod = types.ModuleType("dateutil.relativedelta")

    class DummyRelativeDelta:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    relativedelta_mod.relativedelta = DummyRelativeDelta
    sys.modules["dateutil"] = dateutil_mod
    sys.modules["dateutil.relativedelta"] = relativedelta_mod

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
            normalized = str(periodo).lower()
            if "novembro 26" in normalized or "novembro 2026" in normalized:
                return {"mes_embarque": "2026/11", "ano": "2026", "mes": "11"}
            if "dezembro 26" in normalized or "dezembro 2026" in normalized:
                return {"mes_embarque": "2026/12", "ano": "2026", "mes": "12"}
            if "09/2026" in normalized:
                return {"mes_embarque": "2026/09", "ano": "2026", "mes": "09"}
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


def test_unfixed_status_does_not_turn_shipment_month_into_fixing_month():
    SQLTools = _load_sql_tools_with_stubs()

    query = (
        "quantas sacas a fixar temos para os contratos de exportação "
        "com mês de embarque 09/2026?"
    )

    assert SQLTools._parse_mes_fixacao_vendas(query) is None
    assert SQLTools._parse_mes_fixacao_vendas("mês de fixação 09/2026") == {
        "mes_inicio": "2026/09",
        "mes_fim": "2026/09",
    }
    assert SQLTools._parse_mes_fixacao_vendas("09/2026", exigir_contexto=False) == {
        "mes_inicio": "2026/09",
        "mes_fim": "2026/09",
    }
    assert SQLTools._parse_mes_fixacao_vendas("mês de fixação janeiro 2026") == {
        "mes_inicio": "2026/01",
        "mes_fim": "2026/01",
    }


def test_fixing_procedure_specific_extractors():
    SQLTools = _load_sql_tools_with_stubs()

    assert SQLTools._extract_mercado_fixar("contratos a fixar contra N27") == "N27"
    assert SQLTools._extract_mercado_fixar("mês de fixação novembro 2026") is None
    assert SQLTools._fixing_company_params("sacas a fixar da COBRA e CUSA") == {
        "Cobra": "true",
        "Cusa": "true",
    }
    assert SQLTools._fixing_company_params(
        "Quantas sacas a fixar temos do cliente Nestle da cobra?"
    ) == {"Cobra": "true"}
    assert SQLTools._parse_emissao_vendas(
        SQLTools.__new__(SQLTools), "novembro 26"
    ) == {
        "data_inicio": "20261101",
        "data_fim": "20261130",
    }


def test_unfixed_query_calls_dedicated_procedure_with_compact_parameters():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools_module = sys.modules["app.agents.sql_tools"]

    class DummyValidator:
        @staticmethod
        def validate_permission(user, function_name):
            return True, None

    class DummySQLClient:
        def __init__(self):
            self.calls = []

        def execute_procedure(self, name, params):
            self.calls.append((name, params))
            return [{
                "contrato": "100/26A", "filial": "05", "cliente": "NESTLE",
                "mercadoFixar": "Z26", "peso": 6000, "sacas": 100,
            }]

    class DummyUser:
        telefone = "teste"
        nome = "Teste"

    fake_client = DummySQLClient()
    sql_tools_module.sql_validator = DummyValidator()
    sql_tools_module.sql_client = fake_client
    tool = SQLTools(DummyUser())
    tool.user_query_original = "Quantas sacas a fixar da Nestle da Cobra em dezembro 26?"
    tool.user_query = tool.user_query_original

    tool._pesquisa_vendas(periodo="dezembro 26", cliente="NESTLE")

    assert fake_client.calls == [(
        "usp_IA_Vendas_Fixar",
        {
            "MesIni": "202612", "MesFim": "202612",
            "Cliente": "NESTLE", "Cobra": "true",
        },
    )]

    fake_client.calls.clear()
    tool.user_query_original = (
        "Quantas sacas a fixar temos do cliente STRAUSS COMMODITIES da cobra?"
    )
    tool.user_query = tool.user_query_original

    tool._pesquisa_vendas(periodo="2026/12", cliente="STRAUSS COMMODITIES")

    assert fake_client.calls == [(
        "usp_IA_Vendas_Fixar",
        {"Cliente": "STRAUSS COMMODITIES", "Cobra": "true"},
    )]


def test_market_index_is_filtered_after_unparameterized_fixing_query():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools_module = sys.modules["app.agents.sql_tools"]

    class DummyValidator:
        @staticmethod
        def validate_permission(user, function_name):
            return True, None

    class DummySQLClient:
        def __init__(self):
            self.calls = []

        def execute_procedure(self, name, params):
            self.calls.append((name, params))
            return [
                {"contrato": "100/26A", "mercadoFixar": "N27", "peso": 6000},
                {"contrato": "101/26A", "mercadoFixar": "Z26", "peso": 12000},
            ]

    class DummyUser:
        telefone = "teste"
        nome = "Teste"

    fake_client = DummySQLClient()
    sql_tools_module.sql_validator = DummyValidator()
    sql_tools_module.sql_client = fake_client
    tool = SQLTools(DummyUser())
    tool.user_query_original = "Quais contratos a fixar contra N27?"
    tool.user_query = tool.user_query_original

    output = tool._pesquisa_vendas(mes_fixacao="N27")

    assert fake_client.calls == [("usp_IA_Vendas_Fixar", None)]
    assert "Volume total: 100,00 sacas de 60 kg" in output
    assert "Contratos: 1" in output
    assert "Critério:" not in output
    assert "usp_IA_Vendas_Fixar" not in output
    assert "sem peso positivo" not in output
    assert "Parcelas com volume replicado desconsideradas" not in output
    assert "Contratos-pai consolidados" not in output


def test_fixing_procedure_accepts_all_supported_filters_together():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools_module = sys.modules["app.agents.sql_tools"]

    class DummyValidator:
        @staticmethod
        def validate_permission(user, function_name):
            return True, None

    class DummySQLClient:
        def __init__(self):
            self.calls = []

        def execute_procedure(self, name, params):
            self.calls.append((name, params))
            return [{"contrato": "123/26", "peso": 6000, "mercadoFixar": "H27"}]

    class DummyUser:
        telefone = "teste"
        nome = "Teste"

    fake_client = DummySQLClient()
    sql_tools_module.sql_validator = DummyValidator()
    sql_tools_module.sql_client = fake_client
    tool = SQLTools(DummyUser())
    tool.user_query_original = (
        "Contratos a fixar do cliente ACME, contrato 123/26, da CUSA, "
        "emitidos em novembro 26, com embarque em dezembro 26 e mês de fixação janeiro 2027"
    )
    tool.user_query = tool.user_query_original

    tool._pesquisa_vendas(
        periodo="dezembro 26",
        data_emissao="novembro 26",
        cliente="ACME",
        contrato="123/26",
        mes_fixacao="janeiro 2027",
    )

    assert fake_client.calls == [(
        "usp_IA_Vendas_Fixar",
        {
            "EmisIni": "20261101", "EmisFim": "20261130",
            "MesFixIni": "202701", "MesFixFim": "202701",
            "MesIni": "202612", "MesFim": "202612",
            "Cliente": "ACME", "Contrato": "123/26", "Cusa": "true",
        },
    )]


def test_export_unfixed_query_uses_market_and_complete_fixing_status():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = (
        "quantas sacas a fixar temos para os contratos de exportação "
        "com mês de embarque 09/2026?"
    )
    sql_tools.user_query = sql_tools.user_query_original
    sql_tools._series_expected_months = []
    sql_tools._series_date_fields = ("mesEmbarque", "mesembarque")
    sql_tools._series_query_context = {}
    sql_tools.session_id = None
    rows = [
        {
            "contrato": "100/26A", "filial": "05", "cliente": "EXTERNO",
            "MERCADO": "EXTERNO", "precoFix": "A fixar", "valorFixado": 0,
            "peso": 6000, "sacas": 101.69, "mesEmbarque": "2026/09",
        },
        {
            "contrato": "101/26A", "filial": "05", "cliente": "INTERNO",
            "MERCADO": "INTERNO", "precoFix": "A fixar", "valorFixado": 0,
            "peso": 12000, "sacas": 203.39, "mesEmbarque": "2026/09",
        },
        {
            "contrato": "102/26A", "filial": "05", "cliente": "FIXO",
            "MERCADO": "EXTERNO", "precoFix": "Fixo", "valorFixado": 0,
            "peso": 18000, "sacas": 305.08, "mesEmbarque": "2026/09",
        },
    ]

    output = sql_tools._format_results(rows, "IA_Vendas")

    assert "Volume total: 100,00 sacas de 60 kg" in output
    assert "Contratos: 1" in output
    assert "Critério:" not in output
    assert "precoFix = A fixar e valorFixado nulo ou zero" not in output


def test_unfixed_output_hides_internal_consolidation_metadata():
    SQLTools = _load_sql_tools_with_stubs()
    sql_tools = SQLTools.__new__(SQLTools)
    sql_tools.user_query_original = "Quantas sacas a fixar temos?"
    sql_tools.user_query = sql_tools.user_query_original
    sql_tools._series_expected_months = []
    sql_tools._series_date_fields = ("mesEmbarque", "mesembarque")
    sql_tools._series_query_context = {}
    sql_tools.session_id = None
    rows = [
        {
            "contrato": "200/26A", "filial": "05", "cliente": "CLIENTE",
            "peso": 6000, "sacas": 101.69,
        },
        {
            "contrato": "200/26B", "filial": "05", "cliente": "CLIENTE",
            "peso": 6000, "sacas": 101.69,
        },
    ]

    output = sql_tools._format_results(
        rows,
        "IA_Vendas",
        unfixed_source_pre_filtered=True,
    )

    assert "Contratos: 1" in output
    assert "Parcelas com volume replicado desconsideradas" not in output
    assert "Contratos-pai consolidados" not in output
    assert "Contratos-pai com parcelas" not in output


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
