import subprocess
import time

def start_uart_server():
    subprocess.Popen(["python", "uart.py"])

def start_usb_host_process():
    subprocess.Popen(["python", "android2.py"])

def start_bluetoothLE_process():
    subprocess.Popen(["python", "bluetooth2.py"])


# Start the components in the desired order
start_uart_server()
time.sleep(0.5)  # Wait for the server to start
start_usb_host_process()
start_bluetoothLE_process()

# Continue with any other necessary startup tasks