import subprocess
import time

def start_process(command, name):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        print(f"{name} started successfully.")
    else:
        print(f"Failed to start {name}.")
        print(f"stdout: {stdout.decode('utf-8')}")
        print(f"stderr: {stderr.decode('utf-8')}")

def start_uart_server():
    start_process(["python", "uart.py"], "uart")

def start_usb_host_process():
    start_process(["sudo", "python", "android2.py"], "usb_host")

def start_bluetoothLE_process():
    start_process(["python", "bluetooth2.py"], "bluetoothLE")


# Start the components in the desired order
start_uart_server()
time.sleep(0.5)  # Wait for the server to start
start_usb_host_process()
start_bluetoothLE_process()

# Continue with any other necessary startup tasks