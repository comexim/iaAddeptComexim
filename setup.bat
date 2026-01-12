@echo off
echo ==========================================
echo    AGENTE COMEXIM IA - SETUP
echo ==========================================
echo.

echo [1/4] Criando ambiente virtual...
python -m venv venv
if errorlevel 1 (
    echo ERRO: Falha ao criar ambiente virtual
    pause
    exit /b 1
)

echo [2/4] Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo [3/4] Instalando dependencias...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias
    pause
    exit /b 1
)

echo [4/4] Configurando ambiente...
if not exist .env (
    copy .env.example .env
    echo Arquivo .env criado! Por favor, configure as variaveis.
) else (
    echo Arquivo .env ja existe.
)

echo.
echo ==========================================
echo    SETUP CONCLUIDO COM SUCESSO!
echo ==========================================
echo.
echo Proximos passos:
echo 1. Configure o arquivo .env
echo 2. Execute: python main.py
echo.
pause
