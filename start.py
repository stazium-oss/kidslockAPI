"""
KidLock — запуск агента и сервера одновременно.
Используй этот скрипт вместо запуска agent.py и uvicorn по отдельности.

Запуск: python start.py
"""

import subprocess
import sys
import signal
import time
from pathlib import Path

BASE = Path(__file__).parent

def main():
    print("=" * 50)
    print("  KidLock — запуск системы")
    print("=" * 50)

    procs = []

    # Запуск агента
    agent_cmd = [sys.executable, str(BASE / "agent" / "agent.py")]
    print(f"\n[1/2] Запуск агента...")
    agent = subprocess.Popen(agent_cmd)
    procs.append(("Агент", agent))
    time.sleep(1)

    # Запуск FastAPI сервера
    server_cmd = [
        sys.executable, "-m", "uvicorn",
        "server.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ]
    print(f"[2/2] Запуск веб-сервера на http://0.0.0.0:8000 ...")
    server = subprocess.Popen(server_cmd, cwd=BASE)
    procs.append(("Сервер", server))

    print("\n✓ Всё запущено!")
    print("  Веб-панель: http://localhost:8000")
    print("  API docs:   http://localhost:8000/api/docs")
    print("\n  Ctrl+C для остановки\n")

    def shutdown(sig, frame):
        print("\nОстановка...")
        for name, p in procs:
            print(f"  Останавливаю {name}...")
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Ждём пока процессы живы
    while True:
        for name, p in procs:
            if p.poll() is not None:
                print(f"\n[!] {name} завершился (код {p.returncode})")
                shutdown(None, None)
        time.sleep(2)

if __name__ == "__main__":
    main()
