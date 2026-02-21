import subprocess
import platform
import os
import time

def abrir_terminais(scripts):
    sistema = platform.system()
    diretorio_projeto = os.path.dirname(os.path.abspath(__file__))
    
    # Limpa variáveis de ambiente que podem bugar terminais no Linux
    env_limpo = os.environ.copy()
    if "LD_LIBRARY_PATH" in env_limpo:
        del env_limpo["LD_LIBRARY_PATH"]

    for titulo, cmd in scripts:
        print(f"Lançando: {titulo}")
        
        # Adapta o comando 'python' para 'python3' em sistemas Unix
        if sistema in ["Linux", "Darwin"] and cmd.startswith("python "):
            cmd = cmd.replace("python ", "python3 ")
        
        if sistema == "Windows":
            # Abre o CMD com o título especificado e mantém aberto (/k)
            comando_win = f'start "{titulo}" cmd /k "{cmd}"'
            subprocess.Popen(comando_win, shell=True, cwd=diretorio_projeto)

        elif sistema == "Linux":
            try:
                subprocess.Popen([
                    "gnome-terminal", 
                    f"--title={titulo}",
                    f"--working-directory={diretorio_projeto}", 
                    "--", "bash", "-c", f"{cmd}; exec bash"
                ], env=env_limpo)
            except Exception:
                comando_linux = f'x-terminal-emulator -T "{titulo}" -e bash -c "cd \'{diretorio_projeto}\' && {cmd}; exec bash"'
                subprocess.Popen(comando_linux, shell=True, env=env_limpo)

        elif sistema == "Darwin": # macOS
            script = f'tell application "Terminal" to do script "cd {diretorio_projeto} && {cmd}"'
            subprocess.Popen(['osascript', '-e', script])
        
        # Delay de 1 segundo para garantir que portas abram na ordem certa
        time.sleep(1)

if __name__ == "__main__":
    print("=======================================")
    print("   Iniciando o Projeto Mini-NET...")
    print("=======================================")
    
    # Lista contendo (Título da Janela, Comando)
    meus_scripts = [
        ("Roteador (Fase 3)", "python router.py"),
        ("Servidor", "python server.py"),
        ("Cliente 1", "python client.py"),
        ("Cliente 2", "python client.py")
    ]
    
    abrir_terminais(meus_scripts)
    
    print("Todos os modulos foram iniciados!")
    print("Configure os VIPs nas janelas dos clientes para testar o chat.")