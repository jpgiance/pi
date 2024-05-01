# scp  /Users/lolo/Developer/Embedded/pi_scripts/android_accessory_v_1.py jorge@10.3.3.255:/home/jorge/usb_comms
# scp  /c/Users/Jorge/Developer/Code/Python/USB/usb_comms/android_accessory_v_1.py jorge@192.168.1.171:/home/jorge/usb_comms

import usb.core
import usb.util
import threading
import time
import queue
import traceback
import serial

# Configure these values based on your setup
arduino_port = '/dev/ttyS0'  # UART port for Raspberry Pi
baud_rate = 115200             # Match this with your Arduino's baud rate
last_uart_activity = time.time()
# Setup the serial connection
uart = serial.Serial(arduino_port, baudrate=baud_rate, timeout=1)

#  Product IDs / Vendor IDs 
AOA_ACCESSORY_VENDOR_ID		            =0x18D1	    # Google 

AOA_ACCESSORY_PRODUCT_ID		        =0x2D00	    # accessory 
AOA_ACCESSORY_ADB_PRODUCT_ID		    =0x2D01	    # accessory + adb 
AOA_AUDIO_PRODUCT_ID			        =0x2D02	    # audio 
AOA_AUDIO_ADB_PRODUCT_ID		        =0x2D03	    # audio + adb 
AOA_ACCESSORY_AUDIO_PRODUCT_ID	        =0x2D04	    # accessory + audio 
AOA_ACCESSORY_AUDIO_ADB_PRODUCT_ID      =0x2D05	    # accessory + audio + adb 

GOOGLE_VID = 0x18D1
ACCESSORY_PIDS = {0x2D00, 0x2D01}  # Accessory mode product IDs

# Flag to control the communication thread
running = True

# Create a thread-safe queue
MAX_QUEUE_SIZE = 100
message_queue_to_uart = queue.Queue()
message_queue_to_usb = queue.Queue()

def monitor_threads():
    global uart
    while True:
        now = time.time()
        print(f"Checking UART now: {now}  and last_uart_activity: {last_uart_activity} result: {now - last_uart_activity}")
        if now - last_uart_activity > 3:  # Threshold for inactivity
            print(f"UART appears to have stopped. Attempting to restart.")
            try:
                uart.close()
                uart = serial.Serial(arduino_port, baudrate=baud_rate, timeout=1)
                # Restart the thread
                read_uart_thread = threading.Thread(target=read_from_uart)
                send_uart_thread = threading.Thread(target=send_messages_from_queue)

                read_uart_thread.start()
                send_uart_thread.start()
                print(f"UART has been restarted.")
            except Exception as e:
                print(f"Exception occured while restarting UART threads: {e}")
        time.sleep(2)  # Check every 2 seconds

# Function to clear the queue
def clear_queue(q):
    with q.mutex:  # Acquire the queue's underlying lock to ensure thread-safe operations
        q.queue.clear()  # Directly clear the underlying deque
        
def read_from_uart():
    global uart, last_uart_activity
    while True:
        try:
            # print("trying to read from uart")
            bytes_to_read = uart.in_waiting
            if bytes_to_read:
                data = uart.read(bytes_to_read)
                if(message_queue_to_usb.qsize() > MAX_QUEUE_SIZE):
                    clear_queue(message_queue_to_usb)
                message_queue_to_usb.put(data)
                last_uart_activity = time.time()  # Update activity timestamp
                # print("Received data from UART:", data)
        except serial.SerialException as e:
            print(f"Serial exception: {e}")
        except Exception as e:
            print(f"Unexpected error during read from uart: {e}")
            
        
 
def send_messages_from_queue():
    global uart
    while True:
        try:
            # print("trying to send to uart")
            if not message_queue_to_uart.empty():
                message_to_send = message_queue_to_uart.get()
                print("Sending data to UART:", message_to_send)
                uart.write(message_to_send)
        except serial.SerialException as e:
            print(f"Serial exception during write: {e}. Waiting for reconnection...")
            # Wait a bit for the read thread to re-establish the connection
            time.sleep(2)
        except Exception as e:
            print(f"Unexpected error during write to uart: {e}")
        
            
# Function to send a string to the USB device
def send_string(dev, index, string):
    assert dev.ctrl_transfer(
        bmRequestType=usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR,
        bRequest=52,
        wValue=0,
        wIndex=index,
        data_or_wLength=string.encode('utf-8') + b'\x00'
    ) == len(string) + 1

def send_accessory_mode_commands(dev):
    # Assuming standard Android accessory mode protocol
    # These strings should be replaced with your specific values
    manufacturer = 'Manufacturer'
    model = 'Model'
    description = 'Description'
    version = '1.0'
    uri = 'https://example.com'
    serial = 'serial'

    try:
        # Step 1: Get Protocol
        protocol = dev.ctrl_transfer(
            bmRequestType=usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR,
            bRequest=51,
            wValue=0,
            wIndex=0,
            data_or_wLength=2
        )

        # Check protocol support
        protocol_version = int.from_bytes(protocol, byteorder='little')
        if protocol_version == 0:
            print('Accessory mode not supported')
            return False

        # Step 2: Send identifying strings
        send_string(dev, 0, manufacturer)
        send_string(dev, 1, model)
        send_string(dev, 2, description)
        send_string(dev, 3, version)
        send_string(dev, 4, uri)
        send_string(dev, 5, serial)

        # Step 3: Start accessory mode
        dev.ctrl_transfer(
            bmRequestType=usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR,
            bRequest=53,
            wValue=0,
            wIndex=0,
            data_or_wLength=None
        )
        print("Switched to accessory mode")
        return True
    except Exception as e:
        print("Failed to send accessory mode commands:", e)
        return False

def attempt_accessory_mode_for_device(dev):
    try:
        # Send accessory mode commands and check if successful
        if send_accessory_mode_commands(dev):
            # Wait for the device to disconnect and reconnect
            print("Waiting for device to switch to accessory mode...")
            time.sleep(1) 
            accessory = find_accessory_device()
            if accessory is not None:
                print("Device found in accessory mode:", accessory)
                return accessory  # Return the device if accessory mode command was successful
            else:
                print("Device not found in accessory mode.")
                return None
            
        else:
            return None
    except Exception as e:
        print("Error attempting accessory mode:", e)
        return None
    
def identify_android_device_as_usb():
    try:
        already_in_OAM_device = find_accessory_device()
        if already_in_OAM_device is not None:
            return already_in_OAM_device
        devices = list(usb.core.find(find_all=True))
        # Iterate over all connected USB devices
        for dev in devices:
            description = usb.util.get_string(dev, dev.iProduct)
            print("checking device: ", description)
            accessory_dev = attempt_accessory_mode_for_device(dev)
            if accessory_dev is not None:
                return accessory_dev  # Return the device already in accessory mode
        return None
    except usb.core.USBError as e:
        return None
    except Exception as e:
        print("Error attempting accessory mode:", e)
        return None


def find_accessory_device():
    try:
        dev = usb.core.find(idVendor=GOOGLE_VID, find_all=True)
        for d in dev:
            if d.idProduct in ACCESSORY_PIDS:
                return d
        return None
    except usb.core.USBError as e:
        return None

# Function to get bulk endpoints
def get_bulk_endpoints(accessory_device, interface_number):
    cfg = accessory_device.get_active_configuration()
    interface = usb.util.find_descriptor(cfg, bInterfaceNumber=interface_number)

    ep_in = usb.util.find_descriptor(
        interface, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    ep_out = usb.util.find_descriptor(
        interface, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )

    return ep_in, ep_out

def read_from_accessory(device, endpoint_in):
    global running
    while running:
        try:
            data = endpoint_in.read(1024, timeout=1000)  # Read up to 1024 bytes with a timeout
            data_string = data.tobytes().decode('utf-8', errors='replace')
            # print("Received data from USB:", data_string)
            if(message_queue_to_uart.qsize() > MAX_QUEUE_SIZE):
                    clear_queue(message_queue_to_uart)
            message_queue_to_uart.put(data.tobytes())  # Enqueue the received data
        except usb.core.USBError as e:
            if e.errno == 110:
                print("Read timeout. Continuing...")
                continue
            else:
                print("Read thread USB error:", e)
                running = False  # Stop the threads
                break
        except Exception as e:
            print("Read thread unexpected error:", e)
            running = False  # Stop the threads
            break

def write_to_accessory(device, endpoint_out):
    global running, message_queue_to_usb
    while running:
        if not message_queue_to_usb.empty():
            data = message_queue_to_usb.get()  # Dequeue the data
            try:
                # endpoint_out.write(data_string.encode('utf-8')) # for string data encode first
                endpoint_out.write(data)
                print("Sending data to USB:", data)
            except usb.core.USBError as e:
                if e.errno == 110:  # errno 110 is a timeout error
                    print("Read timeout occurred. Handling it.")
                    continue
                else:
                    print("Device disconnected or read error:", e)
                    running = False  # Stop the threads
                    break
            except Exception as e:
                print("Unexpected error:", e)
                running = False  # Stop the threads
                break  # Exit the loop for non-USB errors

def write_to_uart():
    global running, message_queue_to_uart
    while running:
        with serial.Serial(arduino_port, baud_rate, timeout=1) as ser:
            while True:
                if not message_queue_to_uart.empty():
                    data = message_queue_to_uart.get()
                    ser.write(data)

                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    from_arduino.put(data)
        
def main():
    global running
    
    # Create and start threads
    read_uart_thread = threading.Thread(target=read_from_uart)
    send_uart_thread = threading.Thread(target=send_messages_from_queue)
    monitor_thread = threading.Thread(target=monitor_threads)

    read_uart_thread.start()
    send_uart_thread.start()
    monitor_thread.start()

    while True:
        running = True
        print("\n--------------------\nSoftware Version: 3.7 ........ Searching for device as USB...")
        accessory = identify_android_device_as_usb()
        if accessory:
            print("Device found and switched to accessory mode.")
            try:
                
                print("Step 1 done")
                # Get endpoints based on product ID
                if accessory.idProduct == 0x2D00:
                    endpoint_in, endpoint_out = get_bulk_endpoints(accessory, 0)
                elif accessory.idProduct == 0x2D01:
                    # Standard communication endpoints
                    endpoint_in, endpoint_out = get_bulk_endpoints(accessory, 0)
                    # ADB communication endpoints (if needed)
                    # adb_ep_in, adb_ep_out = get_bulk_endpoints(accessory, 1)

                print("Step 2 done")

                if endpoint_in is not None and endpoint_out is not None:
                    read_thread = threading.Thread(target=read_from_accessory, args=(accessory, endpoint_in))
                    write_thread = threading.Thread(target=write_to_accessory, args=(accessory, endpoint_out))

                    read_thread.start()
                    write_thread.start()
                    print("Threads started")

                    read_thread.join()
                    write_thread.join()

                    print("Continue Main loop after finish")
                else:
                    print("Endpoints not found.")
            except usb.core.USBError as e:
                print("Error setting configuration:", e)
                traceback_str = ''.join(traceback.format_tb(e.__traceback__))
                print("Traceback:", traceback_str)
                usb.util.dispose_resources(accessory)
            except KeyboardInterrupt:
                print("Keyboard interrupt received. Stopping threads...")
                running = False
                print("Threads stopped. Exiting.")
                break
        else:
            print("No Android device found in accessory mode.")
            
        time.sleep(3)  # Wait for 3 seconds before searching again
    

if __name__ == "__main__":
    main()
