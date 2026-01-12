"""
Script para verificar se todas as dependencias estao instaladas corretamente
"""
import sys

def check_dependencies():
    print("[INFO] Verificando dependencias do projeto...\n")

    dependencies = [
        ("fastapi", "FastAPI framework"),
        ("uvicorn", "ASGI server"),
        ("pydantic", "Data validation"),
        ("pydantic_settings", "Settings management"),
        ("dotenv", "Environment variables"),
        ("pyodbc", "SQL Server driver"),
        ("redis", "Redis client"),
        ("supabase", "Supabase client"),
        ("langchain", "LangChain framework"),
        ("langchain_openai", "OpenAI integration"),
        ("openai", "OpenAI SDK"),
        ("httpx", "HTTP client"),
        ("dateutil", "Date utilities"),
        ("pytz", "Timezone support"),
        ("email_validator", "Email validation"),
    ]

    missing = []
    installed = []

    for module_name, description in dependencies:
        try:
            __import__(module_name)
            installed.append((module_name, description))
            print(f"[OK] {module_name:25} - {description}")
        except ImportError:
            missing.append((module_name, description))
            print(f"[ERRO] {module_name:25} - {description} (NAO INSTALADO)")

    print(f"\n{'='*60}")
    print(f"Resumo:")
    print(f"  Instaladas: {len(installed)}/{len(dependencies)}")
    print(f"  Faltando:   {len(missing)}/{len(dependencies)}")
    print(f"{'='*60}\n")

    if missing:
        print("[ACAO NECESSARIA] Instale as dependencias faltantes:\n")
        print("python -m pip install", end="")
        for module_name, _ in missing:
            print(f" {module_name}", end="")
        print("\n")
        return False
    else:
        print("[OK] Todas as dependencias estao instaladas!\n")
        return True

def check_env_file():
    import os
    from pathlib import Path

    print("[INFO] Verificando arquivo .env...\n")

    env_path = Path(".env")

    if not env_path.exists():
        print("[ERRO] Arquivo .env nao encontrado!")
        print("[ACAO] Crie o arquivo .env baseado no .env.example\n")
        return False

    required_vars = [
        "SQL_SERVER_HOST",
        "SQL_SERVER_DATABASE",
        "SQL_SERVER_USERNAME",
        "SQL_SERVER_PASSWORD",
        "REDIS_HOST",
        "REDIS_PASSWORD",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "OPENAI_API_KEY",
        "EVOLUTION_API_URL",
        "EVOLUTION_API_KEY",
        "EVOLUTION_INSTANCE_NAME",
    ]

    # Load .env
    from dotenv import load_dotenv
    load_dotenv()

    missing_vars = []
    found_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if value and value.strip() and value != "your_xxx_here":
            found_vars.append(var)
            # Ocultar valores sensiveis
            if "KEY" in var or "PASSWORD" in var:
                display_value = f"{value[:8]}..."
            else:
                display_value = value[:40] + "..." if len(value) > 40 else value
            print(f"[OK] {var:30} = {display_value}")
        else:
            missing_vars.append(var)
            print(f"[ERRO] {var:30} (NAO CONFIGURADO)")

    print(f"\n{'='*60}")
    print(f"Resumo:")
    print(f"  Configuradas: {len(found_vars)}/{len(required_vars)}")
    print(f"  Faltando:     {len(missing_vars)}/{len(required_vars)}")
    print(f"{'='*60}\n")

    if missing_vars:
        print("[ACAO NECESSARIA] Configure as variaveis faltantes no .env:\n")
        for var in missing_vars:
            print(f"  {var}=")
        print("\n")
        return False
    else:
        print("[OK] Todas as variaveis de ambiente estao configuradas!\n")
        return True

def check_python_version():
    print("[INFO] Verificando versao do Python...\n")

    version = sys.version_info
    print(f"Versao instalada: Python {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor >= 10:
        print("[OK] Versao do Python compativel (>= 3.10)\n")
        return True
    else:
        print("[ERRO] Versao do Python incompativel!")
        print("[ACAO] Instale Python 3.10 ou superior\n")
        return False

def main():
    print("="*60)
    print(" VERIFICACAO DE DEPENDENCIAS - AGENTE COMEXIM")
    print("="*60)
    print()

    results = []

    # Check 1: Python version
    results.append(("Versao Python", check_python_version()))

    # Check 2: Dependencies
    results.append(("Dependencias", check_dependencies()))

    # Check 3: Environment variables
    results.append(("Variaveis .env", check_env_file()))

    # Summary
    print("="*60)
    print(" RESUMO FINAL")
    print("="*60)
    print()

    all_ok = True
    for check_name, check_result in results:
        status = "[OK]" if check_result else "[ERRO]"
        print(f"{status} {check_name}")
        if not check_result:
            all_ok = False

    print()

    if all_ok:
        print("[OK] Sistema pronto para uso!")
        print("\nProximos passos:")
        print("  1. python test_connection.py")
        print("  2. python test_supabase.py")
        print("  3. python test_redis.py (apos configurar Upstash)")
        print("  4. python test_agent.py")
        print()
    else:
        print("[ERRO] Algumas verificacoes falharam.")
        print("       Corrija os problemas acima antes de continuar.\n")

    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
