"""
Teste da funcionalidade de resolução de campos (descrição → código)
"""

import asyncio
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.field_resolver import field_resolver
from app.core.ada_api_client import ada_api_client


async def test_connection():
    """Testa conexão com a API"""
    print("\n" + "="*80)
    print("🔌 TESTE 1: Conexão com API ADA")
    print("="*80)
    
    try:
        connected = await ada_api_client.test_connection()
        if connected:
            print("✅ Conexão estabelecida com sucesso!")
            return True
        else:
            print("❌ Falha ao conectar")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def test_consulta_embalagem():
    """Testa consulta de embalagens"""
    print("\n" + "="*80)
    print("📦 TESTE 2: Consulta de Embalagens")
    print("="*80)
    
    try:
        result = await ada_api_client.consultar_campo("codigoEmbalagem", filtro="")
        
        print(f"✅ Consulta realizada com sucesso!")
        print(f"📊 Total de registros: {len(result.get('registros', []))}")
        
        # Mostra primeiros 5 registros
        registros = result.get('registros', [])[:5]
        print("\n📋 Primeiros 5 registros:")
        for i, reg in enumerate(registros, 1):
            codigo = reg.get('codigo', 'N/A')
            descricao = reg.get('descricao', 'N/A')
            print(f"   {i}. [{codigo}] {descricao}")
        
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def test_resolve_campo():
    """Testa resolução de campo (matching)"""
    print("\n" + "="*80)
    print("🔍 TESTE 3: Resolução de Campo (Matching)")
    print("="*80)
    
    # Casos de teste
    test_cases = [
        ("codigo_embalagem", "pallet com alpha bag 190gr", 70),
        ("codigo_embalagem", "pallet alpha bag gramatura 190", 70),
        ("codigo_embalagem", "00304", 70),  # Código direto
        ("codigo_embalagem", "alpha bag 59 kg", 70),
    ]
    
    for campo, descricao, threshold in test_cases:
        print(f"\n🔎 Testando: '{descricao}'")
        try:
            codigo = await field_resolver.resolve_field(campo, descricao, threshold)
            if codigo != descricao:
                print(f"   ✅ Resolvido: '{descricao}' → '{codigo}'")
            else:
                print(f"   ℹ️ Mantido original: '{descricao}'")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    return True


async def test_fluxo_completo():
    """Testa fluxo completo como seria usado no agente"""
    print("\n" + "="*80)
    print("🎯 TESTE 4: Fluxo Completo (Simulação Real)")
    print("="*80)
    
    print("\n📝 Simulação: Usuário diz 'embalagem de pallet com 2 alpha bag'")
    
    try:
        # Simula o que aconteceria quando usuário informa a embalagem
        campo = "codigo_embalagem"
        entrada_usuario = "pallet com 2 alpha bag gramatura 190gr"
        
        print(f"\n1️⃣ Entrada do usuário: '{entrada_usuario}'")
        
        # Resolve o campo
        codigo_resolvido = await field_resolver.resolve_field(campo, entrada_usuario, threshold=70)
        
        print(f"2️⃣ Código resolvido: '{codigo_resolvido}'")
        
        # Mostra o que seria enviado para a API
        if codigo_resolvido != entrada_usuario:
            print(f"\n✅ SUCESSO! Sistema converteu automaticamente:")
            print(f"   • Usuário disse: '{entrada_usuario}'")
            print(f"   • Sistema enviará: '{codigo_resolvido}'")
            print(f"\n💡 O usuário NÃO precisa saber o código!")
        else:
            print(f"\n⚠️ Nenhuma conversão aplicada (pode ser código direto ou sem match)")
        
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def main():
    """Executa todos os testes"""
    print("\n" + "="*80)
    print("🧪 TESTE DE RESOLUÇÃO DE CAMPOS (Descrição → Código)")
    print("="*80)
    
    # Executa testes em sequência
    tests = [
        test_connection,
        test_consulta_embalagem,
        test_resolve_campo,
        test_fluxo_completo
    ]
    
    results = []
    for test_func in tests:
        try:
            result = await test_func()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Erro no teste {test_func.__name__}: {e}")
            results.append(False)
    
    # Resumo final
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passou: {passed}/{total}")
    print(f"❌ Falhou: {total - passed}/{total}")
    
    if all(results):
        print("\n🎉 TODOS OS TESTES PASSARAM!")
    else:
        print("\n⚠️ Alguns testes falharam")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
