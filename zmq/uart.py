import zmq
import serial
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uart")


class UartServer:
    """
    Proxy server for the UART.
    """

    def __init__(self, port="/dev/ttyS0"):
        """
        Initialize the sockets to listen and publish
        :param port: serial port to open
        """
        ctx = zmq.Context()
        self.in_skt = ctx.socket(zmq.SUB)
        self.in_skt.bind("tcp://*:5555")
        self.in_skt.setsockopt_string(zmq.SUBSCRIBE, "")

        self.out_skt = ctx.socket(zmq.PUB)
        self.out_skt.bind("tcp://*:5556")

        self.uart = serial.Serial(port, 115200)

    def run(self):
        while True:
            try:
                data = self.in_skt.recv(flags=zmq.NOBLOCK)
                log.info("Got:{}".format(data))
            except zmq.ZMQError:
                pass
            else:
                self.uart.write(data)

            if self.uart.in_waiting:
                data = self.uart.read(self.uart.in_waiting)
                self.out_skt.send(data)
                log.info("Sent:{}".format(data))


if __name__ == "__main__":
    server = UartServer()
    server.run()
