# pi

The directory Pi contains the code to run on the raspberry pi zero, to create the UART
service. uart-server.py sends what text string it gets to the minor port ( the UART port using
GPIO 14(tx) and GPIO15(rx))

Install instructions for the Raspberry Pi using Raspbian(Bullseye)

1. sudo apt install git
2. git clone https://github.com/jpgiance/pi.git
3. cd bluetooth_uart/pi
4. sudo apt install python3-pip
5. sudo apt install python3-dbus
6. sudo apt install python3-serial
7. sudo raspi-config
   1. select interface options
   2. select Serial Port
   3. Would you like a login shell to be accessible over serial? No
   4. Would you like the serial port hardware to be enabled? Yes
   5. You should see.
        The serial login shell is disabled                       
        The serial interface is enabled
   6. When you exit it will ask to reboot. Yes
1. After the Pi reboots login again and return to the pi directory
1. python3 uart-server.py