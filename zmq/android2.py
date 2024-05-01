import zmq
import time
import usb.core
import usb.util


#  Product IDs / Vendor IDs
AOA_ACCESSORY_VENDOR_ID             = 0x18D1  # Google
AOA_ACCESSORY_PRODUCT_ID            = 0x2D00  # accessory
AOA_ACCESSORY_ADB_PRODUCT_ID        = 0x2D01  # accessory + adb
AOA_AUDIO_PRODUCT_ID                = 0x2D02  # audio
AOA_AUDIO_ADB_PRODUCT_ID            = 0x2D03  # audio + adb
AOA_ACCESSORY_AUDIO_PRODUCT_ID      = 0x2D04  # accessory + audio
AOA_ACCESSORY_AUDIO_ADB_PRODUCT_ID  = 0x2D05  # accessory + audio + adb

GOOGLE_VID = 0x18D1
ACCESSORY_PIDS = {0x2D00, 0x2D01}  # Accessory mode product IDs

context = zmq.Context()

# Client code that connects to the UartServer publisher (receives from the uart)
in_sock = context.socket(zmq.SUB)
in_sock.connect("tcp://localhost:5556")
in_sock.setsockopt_string(zmq.SUBSCRIBE, "")

# Server Code that connects to the UartServers subscriber (sends to the uart)
out_sock = context.socket(zmq.PUB)
out_sock.bind("tcp://*:5555")


class Android:
    device = None

    def send_string(self, index, string):
        """
        :param index:
        :param string:
        :return:
        """
        sent = self.device.ctrl_transfer(
                                bmRequestType=usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR,
                                bRequest=52,
                                wValue=0,
                                wIndex=index,
                                data_or_wLength=string.encode('utf-8') + b'\x00')

        return True if sent == len(string) + 1 else False

    def send_accessory_mode_commands(self):
        """
        Assuming standard Android accessory mode protocol
        These strings should be replaced with your specific values
        :return:
        """
        manufacturer = 'Manufacturer'
        model = 'Model'
        description = 'Description'
        version = '1.0'
        uri = 'https://example.com'
        serial = 'serial'

        try:
            # Step 1: Get Protocol
            protocol = self.device.ctrl_transfer( bmRequestType=usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR,
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
            self.send_string(self.device, 0, manufacturer)
            self.send_string(self.device, 1, model)
            self.send_string(self.device, 2, description)
            self.send_string(self.device, 3, version)
            self.send_string(self.device, 4, uri)
            self.send_string(self.device, 5, serial)

            # Step 3: Start accessory mode
            self.device.ctrl_transfer(
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

    def attempt_accessory_mode_for_device(self):
        try:
            # Send accessory mode commands and check if successful
            if self.send_accessory_mode_commands(self.device):
                # Wait for the device to disconnect and reconnect
                print("Waiting for device to switch to accessory mode...")
                time.sleep(1)
                accessory = self.find_accessory_device()
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

    def identify_android_device_as_usb(self):
        try:
            already_in_OAM_device = self.find_accessory_device()
            if already_in_OAM_device is not None:
                return already_in_OAM_device
            devices = list(usb.core.find(find_all=True))

            # Iterate over all connected USB devices
            for dev in devices:
                description = usb.util.get_string(dev, dev.iProduct)
                print("checking device: ", description)
                accessory_dev = self.attempt_accessory_mode_for_device(dev)
                if accessory_dev is not None:
                    return accessory_dev  # Return the device already in accessory mode
            return None
        except usb.core.USBError as e:
            return None
        except Exception as e:
            print("Error attempting accessory mode:", e)
            return None

    @staticmethod
    def find_accessory_device():
        try:
            dev = usb.core.find(idVendor=GOOGLE_VID, find_all=True)
            for d in dev:
                if d.idProduct in ACCESSORY_PIDS:
                    return d
            return None
        except usb.core.USBError as e:
            return None

    @staticmethod
    def get_bulk_endpoints(accessory_device, interface_number):
        cfg = accessory_device.get_active_configuration()
        interface = usb.util.find_descriptor(cfg, bInterfaceNumber=interface_number)

        ep_in = usb.util.find_descriptor( interface,
                                          custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == \
                                                                 usb.util.ENDPOINT_IN
        )

        ep_out = usb.util.find_descriptor(interface,
                                          custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == \
                                                                 usb.util.ENDPOINT_OUT
        )

        return ep_in, ep_out

    @staticmethod
    def read_from_accessory(endpoint_in):
        """
        Get data from the Android
        :param endpoint_in:
        :return:
        """
        running = True
        while running:
            try:
                data = endpoint_in.read(1024, timeout=1000)  # Read up to 1024 bytes with a timeout
                out_sock.send(data)

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

    @staticmethod
    def write_to_accessory(endpoint_out, data):
        """
        Write data back
        :param endpoint_out:
        :param data:
        :return:
        """
        try:
            data = in_sock.recv()
            endpoint_out.write(data)
            print("Sending data to USB:", data)
        except usb.core.USBError as e:
            if e.errno == 110:  # errno 110 is a timeout error
                print("Read timeout occurred. Handling it.")
            else:
                print("Device disconnected or read error:", e)

        except Exception as e:
            print("Unexpected error:", e)


def main():
    android = Android()
    accessory = android.identify_android_device_as_usb()
    if accessory:
        print("Device found and switched to accessory mode.")
        try:

            print("Step 1 done")
            # Get endpoints based on product ID
            if accessory.idProduct == 0x2D00:
                endpoint_in, endpoint_out = android.get_bulk_endpoints(accessory, 0)
            elif accessory.idProduct == 0x2D01:
                # Standard communication endpoints
                endpoint_in, endpoint_out = android.get_bulk_endpoints(accessory, 0)
                # ADB communication endpoints (if needed)
                # adb_ep_in, adb_ep_out = get_bulk_endpoints(accessory, 1)
            print("Step 2 done")

        except usb.core.USBError as e:
            print("Error setting configuration:", e)
            usb.util.dispose_resources(accessory)
    else:
        print("No Android device found in accessory mode.")


if __name__ == "__main__":
    main()
