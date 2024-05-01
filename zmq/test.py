import zmq


def main():
    """Test the UART server on the raspberry pi
        Change line 13 from raspberry to the network name of the raspberry pi, or local
        host if run on the same raspberry pi
    """
    import time
    context = zmq.Context()

    # Client code that connects to the UartServer publisher
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://raspberry:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE,"")

    # Sever Code that connects to the UartServers subscriber
    out_sock = context.socket(zmq.PUB)
    out_sock.bind("tcp://*:5555")

    while True:
        try:
            message = socket.recv(zmq.NOBLOCK)
        except zmq.ZMQError as e:
            pass
        else:
            print("Received reply:{}".format(message))
            out_sock.send(message)


if __name__ == "__main__":
    main()