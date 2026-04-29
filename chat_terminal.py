"""
Chat interativo com a IA via terminal
Permite conversação dinâmica sem precisar usar WhatsApp
"""
import asyncio
import sys
import uuid
from datetime import datetime

# Ajusta path para imports
sys.path.insert(0, '.')

from app.agents.orchestrator import AgentOrchestrator
from app.core.redis_client import RedisClient
from app.models.user import UserPermissions


def print_separator(char="=", length=80):
    """Imprime linha separadora"""
    print(char * length)


def print_header():
    """Imprime cabeçalho do chat"""
    print_separator()
    print("🤖 CHAT INTERATIVO - IA COMEXIM")
    print_separator()
    print("Digite suas mensagens normalmente.")
    print("Comandos especiais:")
    print("  /sair ou /quit - Encerra o chat")
    print("  /limpar ou /clear - Limpa histórico da conversa")
    print("  /info - Mostra informações da sessão")
    print_separator()
    print()


def print_user_message(msg: str):
    """Formata mensagem do usuário"""
    print(f"\n👤 VOCÊ:")
    print(f"{msg}")
    print()


def print_ia_message(msg: str):
    """Formata mensagem da IA"""
    print(f"🤖 IA:")
    print(f"{msg}")
    print()


def print_info(session_id: str, user_name: str, messages_count: int):
    """Mostra informações da sessão"""
    print_separator("-")
    print(f"📊 INFORMAÇÕES DA SESSÃO")
    print(f"   Usuário: {user_name}")
    print(f"   Session ID: {session_id}")
    print(f"   Mensagens trocadas: {messages_count}")
    print(f"   Horário: {datetime.now().strftime('%H:%M:%S')}")
    print_separator("-")
    print()


async def main():
    """Loop principal do chat interativo"""
    
    # Configuração inicial
    user_name = input("Digite seu nome (ou pressione Enter para 'Lucas'): ").strip()
    if not user_name:
        user_name = "Lucas"
    
    session_id = f"term_{uuid.uuid4().hex[:12]}"  # Max 17 chars (cabe em varchar(20))
    
    print(f"\n✅ Inicializando chat para {user_name}...\n")
    
    # Cria objeto de permissões
    user = UserPermissions(
        telefone=session_id,  # Usa session_id como telefone para chat terminal
        nome=user_name,
        email=f"{user_name.lower()}@comexim.com.br",
        direitos=["Vendas", "Financeiro"]
    )
    
    # Inicializa orquestrador
    orchestrator = AgentOrchestrator(user=user, session_id=session_id)
    
    print_header()
    
    message_count = 0
    
    while True:
        try:
            # Lê input do usuário
            user_input = input("👤 VOCÊ: ").strip()
            
            if not user_input:
                continue
            
            # Comandos especiais
            if user_input.lower() in ["/sair", "/quit", "/exit"]:
                print("\n👋 Encerrando chat. Até logo!\n")
                break
            
            elif user_input.lower() in ["/limpar", "/clear", "/reset"]:
                # Limpa histórico
                redis_client = RedisClient()
                if hasattr(redis_client, 'r') and redis_client.r:
                    history_key = f"chat_history:{session_id}"
                    redis_client.r.delete(history_key)
                    # Também limpa dados de contrato pendente
                    contrato_key = f"contrato_pendente:{session_id}"
                    redis_client.r.delete(contrato_key)
                print("\n✅ Histórico e dados pendentes limpos!\n")
                message_count = 0
                continue
            
            elif user_input.lower() in ["/info", "/status"]:
                print_info(session_id, user_name, message_count)
                continue
            
            # Processa mensagem normal
            print(f"\n⏳ Processando...\n")
            
            response = await orchestrator.process_message(user_input)
            
            print_ia_message(response)
            print_separator("-", 80)
            
            message_count += 1
            
        except KeyboardInterrupt:
            print("\n\n👋 Chat interrompido. Até logo!\n")
            break
        except Exception as e:
            print(f"\n❌ ERRO: {e}\n")
            import traceback
            traceback.print_exc()
            print()


if __name__ == "__main__":
    print("\n🚀 Iniciando chat interativo...\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Até logo!\n")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}\n")
        import traceback
        traceback.print_exc()
