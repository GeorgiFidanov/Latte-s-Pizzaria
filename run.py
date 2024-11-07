import subprocess
import platform
import os

# Determine the Python command based on the operating system
python_command = 'python' if platform.system().lower() == 'windows' else 'python3'

# Get the paths for both files
app_path = os.path.join(os.path.dirname(__file__), 'app', 'app.py')
data_transmitter_path = os.path.join(os.path.dirname(__file__), 'data_transmitter.py')

# Run app.py
subprocess.Popen(['cmd', '/c', 'start', python_command, app_path])

# Run data_transmitter.py
subprocess.Popen(['cmd', '/c', 'start', python_command, data_transmitter_path])
