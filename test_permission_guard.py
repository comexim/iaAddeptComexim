import unittest

from app.utils.permission_guard import get_early_permission_denial


class FakeUser:
    def __init__(self, permissions):
        self.permissions = set(permissions)

    def has_permission(self, module):
        return module in self.permissions


class EarlyPermissionGuardTest(unittest.TestCase):
    def test_blocks_explicit_purchase_query_without_permission(self):
        result = get_early_permission_denial(
            FakeUser([]),
            "Qual o total de compras hoje por qualidade em diferencial?",
        )

        self.assertEqual(
            result,
            "Você não tem permissão para acessar informações de Compras.",
        )

    def test_accepts_accented_purchase_synonym(self):
        result = get_early_permission_denial(
            FakeUser([]),
            "Mostre as aquisições realizadas hoje",
        )

        self.assertIsNotNone(result)

    def test_allows_purchase_query_with_permission(self):
        result = get_early_permission_denial(
            FakeUser(["Compras"]),
            "Mostre as compras de hoje",
        )

        self.assertIsNone(result)

    def test_does_not_block_unrelated_message(self):
        result = get_early_permission_denial(FakeUser([]), "Bom dia")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
