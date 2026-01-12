"""
Script de teste da conexão Supabase
"""
import asyncio
import sys
import os

# Adiciona o diretorio raiz ao path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.supabase_client import supabase_client


async def test_connection():
    """Testa conexão com Supabase"""
    print("=" * 60)
    print("TESTE DE CONEXAO SUPABASE - SISTEMA DE PREFERENCIAS")
    print("=" * 60)
    print()

    # Teste 1: Buscar preferências de um usuário existente
    print("[TEST 1] Buscando preferências de Marco Aurelio...")
    try:
        prefs = await supabase_client.get_user_preferences("11915901500")
        if prefs:
            print("[OK] Preferências encontradas!")
            print()
            print(prefs.get_summary())
            print()
            print("[CUSTOM INSTRUCTIONS]")
            print(prefs.get_custom_instructions())
            print()
        else:
            print("[AVISO] Usuário não encontrado")
            print()
    except Exception as e:
        print(f"[ERRO] {e}")
        print()

    # Teste 2: Criar/buscar preferências com get_or_create
    print("=" * 60)
    print("[TEST 2] Testando get_or_create para novo usuário...")
    try:
        prefs = await supabase_client.get_or_create_user_preferences(
            telefone="5511999999999",
            nome="Usuário Teste",
            email="teste@teste.com"
        )
        print("[OK] Preferências criadas/recuperadas!")
        print()
        print(prefs.get_summary())
        print()
    except Exception as e:
        print(f"[ERRO] {e}")
        print()

    # Teste 3: Atualizar preferência
    print("=" * 60)
    print("[TEST 3] Atualizando preferência (nivel_detalhe = resumido)...")
    try:
        success = await supabase_client.update_user_preference(
            telefone="5511999999999",
            field="nivel_detalhe",
            value="resumido",
            learned_from="test_script",
            confidence=0.95
        )
        if success:
            print("[OK] Preferência atualizada com sucesso!")

            # Busca novamente para verificar
            prefs = await supabase_client.get_user_preferences("5511999999999")
            print()
            print("Preferências atualizadas:")
            print(prefs.get_summary())
            print()
        else:
            print("[ERRO] Falha ao atualizar preferência")
            print()
    except Exception as e:
        print(f"[ERRO] {e}")
        print()

    # Teste 4: Verificar learning history
    print("=" * 60)
    print("[TEST 4] Verificando learning_history...")
    try:
        prefs = await supabase_client.get_user_preferences("5511999999999")
        if prefs and prefs.learning_history:
            print("[OK] Learning history encontrado!")
            print()
            import json
            print(json.dumps(prefs.learning_history, indent=2, default=str))
            print()
        else:
            print("[INFO] Nenhum histórico de aprendizado ainda")
            print()
    except Exception as e:
        print(f"[ERRO] {e}")
        print()

    # Teste 5: Testar todos os 5 usuários pré-cadastrados
    print("=" * 60)
    print("[TEST 5] Verificando 5 usuários pré-cadastrados...")
    usuarios = [
        ("11915901500", "Marco Aurélio"),
        ("13991386001", "Renan Hazan"),
        ("35920000589", "Lucas Oliveira"),
        ("13991555279", "Rodrigo Perez"),
        ("13988188810", "Bruno Hazan"),
    ]

    for telefone, nome_esperado in usuarios:
        try:
            prefs = await supabase_client.get_user_preferences(telefone)
            if prefs:
                print(f"[OK] {nome_esperado}: {prefs.tom_de_voz}, {prefs.formato_resposta}")
            else:
                print(f"[AVISO] {nome_esperado} não encontrado")
        except Exception as e:
            print(f"[ERRO] {nome_esperado}: {e}")

    print()
    print("=" * 60)
    print("TESTES CONCLUIDOS!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_connection())
