import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if "redis" not in sys.modules:
    redis_stub = types.ModuleType("redis")
    redis_stub.from_url = lambda *_args, **_kwargs: None
    sys.modules["redis"] = redis_stub

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")
    httpx_stub.AsyncClient = MagicMock()
    sys.modules["httpx"] = httpx_stub

if "app.core.config" not in sys.modules:
    config_stub = types.ModuleType("app.core.config")
    config_stub.settings = types.SimpleNamespace(
        redis_url="redis://localhost",
        cmx_api_url="https://cmx.test",
        cmx_token_path="/token",
        cmx_fixacao_path="/z24",
        cmx_hedge_path="/z03",
        cmx_f3_path="/f3",
        cmx_tenant_id="01,05",
        cmx_verify_ssl=False,
        cmx_username="user",
        cmx_password="password",
    )
    sys.modules["app.core.config"] = config_stub

from app.agents.hedge_tools import HedgeTools
from app.core.fixacao_api_client import FixacaoApiClient


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, _ttl, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


class HedgeToolsTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeRedis()
        self.hedge = HedgeTools("teste")
        self.redis_patch = patch.object(self.hedge, "_redis", return_value=self.fake)
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()

    def test_offer_preserves_contract_and_fixation_value(self):
        self.hedge.prepare_offer("123/26A", 332)
        data = self.hedge.load()
        self.assertEqual(data["tipo"], "C")
        self.assertEqual(data["operac"], "FV")
        self.assertEqual(data["valor"], 332.0)
        self.assertEqual(data["ctrex"], "123/26A")
        self.assertEqual(data["stage"], "offered")

    def test_builds_exact_z03_body(self):
        data = {
            "tipo": "C", "mesfix": "SET", "anofix": "2026", "lotes": 1,
            "valor": 332.0, "corret": "SUCDEN", "operac": "FV",
            "account": "A13", "lancaa": "Sim", "ctrex": "123/26A",
            "corretDescricao": "SUCden Financial", "accountDescricao": "Adm13",
            "stage": "awaiting_confirmation",
        }
        self.assertEqual(self.hedge.build_body(data), {
            "tipo": "C", "mesfix": "SET", "anofix": "2026", "lotes": 1,
            "valor": 332.0, "corret": "SUCDEN", "operac": "FV",
            "account": "A13", "lancaa": "Sim", "ctrex": "123/26A",
        })

    def test_month_account_and_broker_are_not_confused(self):
        self.assertEqual(self.hedge.parse_month("março"), "MAR")
        self.assertIsNone(self.hedge.parse_account("março"))
        self.assertIsNone(self.hedge.parse_account("corretora Sucden"))
        self.assertEqual(self.hedge.parse_account("conta Sucden"), ("SCD", "Sucden"))
        self.assertEqual(self.hedge.parse_account("usar A13"), ("A13", "Adm13"))
        self.assertEqual(self.hedge.parse_account("usar Adm13"), ("A13", "Adm13"))

    def test_finds_broker_inside_full_message(self):
        records = [
            {"codigo": "ABCBNK", "descricao": "BANCO ABC"},
            {"codigo": "SUCDEN", "descricao": "SUCden Financial"},
        ]
        result = self.hedge.resolve_broker_from_message(
            "SET 2026, 1 lote, corretora Sucden Financial, A13 e AA sim", records
        )
        self.assertEqual(result, ("SUCDEN", "SUCden Financial"))


class HedgeApiResponseTest(unittest.IsolatedAsyncioTestCase):
    async def test_z03_business_error_is_not_reported_as_success(self):
        client = FixacaoApiClient()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "code": "400", "message": "Hedge recusado", "erros": ["Conta invalida"]
        }
        context = AsyncMock()
        context.__aenter__.return_value.post.return_value = response
        with patch.object(client, "get_token", AsyncMock(return_value="token")), patch(
            "app.core.fixacao_api_client.httpx.AsyncClient", return_value=context
        ):
            with self.assertRaisesRegex(RuntimeError, "Hedge recusado Conta invalida"):
                await client.cadastrar_hedge({"tipo": "C"})


if __name__ == "__main__":
    unittest.main()
