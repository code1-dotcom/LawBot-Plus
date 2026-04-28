import psutil
import time

print("Checking port 8000...")
for conn in psutil.net_connections():
    if conn.laddr.port == 8000 and conn.status == 'LISTEN':
        pid = conn.pid
        print(f"Found: PID={pid}")
        try:
            p = psutil.Process(pid)
            print(f"Process: {p.name()} | {p.exe()}")
            p.kill()
            print("Killed")
        except Exception as e:
            print(f"Error: {e}")

time.sleep(2)
print("Done")
