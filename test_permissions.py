from app.models.user import UserPermissions

def test_permissions():
    print("[INFO] Testando sistema de permissoes...\n")

    # Usuario com permissoes limitadas
    user = UserPermissions(
        telefone="5511972390860",
        nome="Pedro Silva",
        email="pedro.silva@comexim.com.br",
        direitos=["Financeiro", "Vendas"]
    )

    # Testes
    tests = [
        ("Financeiro", True),
        ("Vendas", True),
        ("Estoque", False),
        ("RH", False),
    ]

    for module, expected in tests:
        result = user.has_permission(module)
        status = "[OK]" if result == expected else "[ERRO]"
        print(f"{status} {user.nome} - {module}: {result} (esperado: {expected})")

    print("\n[OK] Teste de permissoes concluido!")

if __name__ == "__main__":
    test_permissions()
