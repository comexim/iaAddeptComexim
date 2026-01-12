"""
Script para iniciar ngrok e obter a URL publica
"""
import subprocess
import time
import requests
import json

def get_ngrok_url():
    """Obtem URL do ngrok"""
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                if data.get("tunnels"):
                    for tunnel in data["tunnels"]:
                        if tunnel.get("proto") == "https":
                            url = tunnel.get("public_url")
                            print(f"\n[OK] Ngrok tunnel ativo!")
                            print(f"[INFO] URL Publica: {url}")
                            print(f"[INFO] URL Webhook: {url}/webhook\n")
                            return url
        except requests.exceptions.ConnectionError:
            pass

        print(f"[INFO] Aguardando ngrok inicializar... ({i+1}/{max_retries})")
        time.sleep(2)

    print("[ERRO] Nao foi possivel conectar ao ngrok")
    return None

def start_ngrok():
    """Inicia ngrok se nao estiver rodando"""
    try:
        # Tentar obter URL primeiro (pode ja estar rodando)
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=1)
        if response.status_code == 200:
            print("[INFO] Ngrok ja esta rodando!")
            return get_ngrok_url()
    except:
        pass

    print("[INFO] Iniciando ngrok...")

    # Iniciar ngrok em background
    subprocess.Popen(
        ["ngrok", "http", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
    )

    time.sleep(3)
    return get_ngrok_url()

if __name__ == "__main__":
    print("="*60)
    print(" NGROK - Tunnel HTTP")
    print("="*60)
    print()

    url = start_ngrok()

    if url:
        print("[PROXIMO PASSO]")
        print("1. Configure o webhook na Evolution API:")
        print(f"   URL: {url}/webhook")
        print("   Events: messages.upsert")
        print()
        print("2. Inicie o FastAPI:")
        print("   python -m uvicorn app.main:app --reload")
        print()
    else:
        print("[ERRO] Falha ao iniciar ngrok")
        print("[ACAO] Tente manualmente: ngrok http 8000")
