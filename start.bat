@echo off
echo =======================================
echo    Iniciando o Projeto Mini-NET...
echo =======================================

:: 1. Inicia o Roteador
start "Roteador (Fase 3)" cmd /k "python router.py"
timeout /t 1 /nobreak >nul

:: 2. Inicia o Servidor
start "Servidor" cmd /k "python server.py"
timeout /t 1 /nobreak >nul

:: 3. Inicia o Cliente 1
start "Cliente 1" cmd /k "python client.py"
timeout /t 1 /nobreak >nul

:: 4. Inicia o Cliente 2
start "Cliente 2" cmd /k "python client.py"

echo Todos os modulos foram iniciados!
echo Configure os VIPs nas janelas dos clientes para testar o chat.
pause