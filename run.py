import subprocess
import platform

python_command = 'python' if platform.system().lower() == 'windows' else 'python3'

subprocess.Popen(['cmd', '/c', 'start', python_command, 'app.py'])

subprocess.Popen(['cmd', '/c', 'start', python_command, 'data_transmitter.py'])