import sys
from types import ModuleType, SimpleNamespace


# O teste valida somente a montagem da SQL e não abre uma conexão real. Esses
# módulos opcionais não existem no ambiente mínimo usado pelos testes locais.
config_stub = ModuleType("app.core.config")
config_stub.settings = SimpleNamespace(sql_server_connection_string="")
sys.modules.setdefault("app.core.config", config_stub)

pyodbc_stub = ModuleType("pyodbc")
pyodbc_stub.Error = Exception
pyodbc_stub.Connection = object
pyodbc_stub.connect = lambda *args, **kwargs: None
sys.modules.setdefault("pyodbc", pyodbc_stub)

from app.core.database import SQLServerClient


class FakeCursor:
    def __init__(self):
        self.query = None
        self.description = []

    def execute(self, query):
        self.query = query

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self):
        return self.fake_cursor

    def close(self):
        pass


def test_receivables_query_has_expected_parameters_and_type_filter():
    client = SQLServerClient.__new__(SQLServerClient)
    connection = FakeConnection()
    client._get_connection = lambda: connection

    result = client.execute_function(
        "dbo.IA_ContasAReceberPar",
        {
            "data_inicio": "19990101",
            "data_fim": "20260817",
            "tipo": "Receber",
        },
    )

    assert result == []
    assert connection.fake_cursor.query == (
        "SELECT * FROM dbo.IA_ContasAReceberPar('19990101', '20260817') "
        "WHERE tipo = 'Receber'"
    )


if __name__ == "__main__":
    test_receivables_query_has_expected_parameters_and_type_filter()
    print("receivables_sql_query: 1 test OK")
