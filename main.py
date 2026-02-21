import subprocess
import platform
import os
import time

def abrir_terminais(comandos):
    sistema = platform.system()
    # Pega o caminho absoluto da pasta onde este main.py está
    diretorio_projeto = os.path.dirname(os.path.abspath(__file__))

    env_limpo = os.environ.copy()
    if "LD_LIBRARY_PATH" in env_limpo:
        del env_limpo["LD_LIBRARY_PATH"]

    for cmd in comandos:
        print(f"Lançando: {cmd} em {diretorio_projeto}")
        
        if sistema == "Windows":
            # Usamos o argumento 'cwd' para que o processo já comece na pasta certa
            subprocess.Popen(f'start cmd /k "{cmd}"', shell=True, cwd=diretorio_projeto)

        elif sistema == "Linux":
            # No Linux (como no seu print), usamos o gnome-terminal ou x-terminal-emulator
            # A flag --working-directory é a forma mais segura de definir a pasta inicial
            try:
                # Tentativa com gnome-terminal (comum no Ubuntu/Debian)
                subprocess.Popen([
                    "gnome-terminal", 
                    f"--working-directory={diretorio_projeto}", 
                    "--", "bash", "-c", f"{cmd}; exec bash"
                ], env=env_limpo)
            except Exception:
                # Fallback para x-terminal-emulator se o gnome-terminal não existir
                comando_linux = f'x-terminal-emulator -e bash -c "cd \'{diretorio_projeto}\' && {cmd}; exec bash"'
                subprocess.Popen(comando_linux, shell=True, env=env_limpo)

        elif sistema == "Darwin": # macOS
            script = f'tell application "Terminal" to do script "cd {diretorio_projeto} && {cmd}"'
            subprocess.Popen(['osascript', '-e', script])
        
        time.sleep(1.5)

if __name__ == "__main__":
    # Certifique-se de usar 'python3' no Linux e apenas 'python' se estiver no Windows
    # Se estiver no Linux, mantenha python3
    meus_scripts = [
        "python3 router.py",
        "python3 server.py",
        "python3 client.py"
    ]
    
    abrir_terminais(meus_scripts)