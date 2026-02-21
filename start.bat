@echo off
echo =======================================
echo    Iniciando o Projeto Mini-NET...
echo =======================================

:: 1. Inicia o Roteador em uma nova janela de terminal
start "Roteador" cmd /k "python router.py"

:: Aguarda 1 segundo para garantir que a porta do roteador abriu
timeout /t 1 /nobreak >nul

:: 2. Inicia o Servidor em uma nova janela de terminal
start "Servidor" cmd /k "python server.py"

:: Aguarda 1 segundo para garantir que o servidor subiu
timeout /t 1 /nobreak >nul

:: 3. Inicia o Cliente
start "Cliente_HOST_A" cmd /k "python client.py"

echo Todos os modulos foram iniciados em janelas separadas!
echo Para encerrar, basta fechar as janelas do terminal.
pause