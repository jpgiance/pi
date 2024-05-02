import zmq
import dbus
import select
import logging
import dbus.mainloop.glib

from gi.repository import GLib

from advertisement  import Advertisement
from advertisement  import register_ad_cb, register_ad_error_cb
from gatt_server    import Service, Characteristic
from gatt_server    import register_app_cb, register_app_error_cb

BLUEZ_SERVICE_NAME              = 'org.bluez'
DBUS_OM_IFACE                   = 'org.freedesktop.DBus.ObjectManager'
LE_ADVERTISING_MANAGER_IFACE    = 'org.bluez.LEAdvertisingManager1'
GATT_MANAGER_IFACE              = 'org.bluez.GattManager1'
GATT_CHRC_IFACE                 = 'org.bluez.GattCharacteristic1'
UART_SERVICE_UUID               = '6e400001-b5a3-f393-e0a9-e50e24dcca9e'
UART_RX_CHARACTERISTIC_UUID     = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
UART_TX_CHARACTERISTIC_UUID     = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'
LOCAL_NAME                      = 'rpi-gatt-server'


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("bluetooth")

mainloop = None

context = zmq.Context()

# Client code that connects to the UartServer publisher (receives from the uart)
in_sock = context.socket(zmq.SUB)
in_sock.connect("tcp://localhost:5556")
in_sock.setsockopt_string(zmq.SUBSCRIBE, "")


# Server Code that connects to the UartServers subscriber (sends to the uart)
out_sock = context.socket(zmq.PUB)
out_sock.connect("tcp://localhost:5555")


class TxCharacteristic(Characteristic):
    def __init__(self, bus, index, service):

        Characteristic.__init__(self, bus, index, UART_TX_CHARACTERISTIC_UUID,
                                ['notify'], service)
        self.notifying = False

        GLib.io_add_watch(in_sock, GLib.IO_IN, self.read_from_uart_helper)

    def send_tx(self, chars):
        if not self.notifying:
            return

        value = []
        for ch in chars:
            value.append(dbus.Byte(ch))

        self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': value}, [])

    def read_from_uart_helper(self, fd, condition):
        while in_sock.getsockopt(zmq.EVENTS):
            try:
                data = in_sock.recv(flags=zmq.NOBLOCK)      # Don't block or it can hold up all the code
            except Exception as e:
                log.error("Error receiving data".format(e))
            else:
                log.info("Data:{}".format(data))
                if data:
                    self.send_tx(data)

        return True

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False


class RxCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, UART_RX_CHARACTERISTIC_UUID, ['write','notify'], service)

    def WriteValue(self, value, options):
        print('Remote: {}'.format(bytearray(value)))
        try:
            out_sock.send(bytearray(value))
        except Exception as e:
            log.error("{} trying to send {}".format(e,value))


class UartService(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, UART_SERVICE_UUID, True)
        self.add_characteristic(TxCharacteristic(bus, 0, self))
        self.add_characteristic(RxCharacteristic(bus, 1, self))


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
        return response


class UartApplication(Application):
    def __init__(self, bus):
        Application.__init__(self, bus)
        self.add_service(UartService(bus, 0))


class UartAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, 'peripheral')
        self.add_service_uuid(UART_SERVICE_UUID)
        self.add_local_name(LOCAL_NAME)
        self.include_tx_power = True


def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'), DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for o, props in objects.items():
        if LE_ADVERTISING_MANAGER_IFACE in props and GATT_MANAGER_IFACE in props:
            return o
        print('Skip adapter:', o)
    return None


def main():
    global mainloop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = find_adapter(bus)
    if not adapter:
        print('BLE adapter not found')
        return

    service_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter), GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                LE_ADVERTISING_MANAGER_IFACE)

    app = UartApplication(bus)
    adv = UartAdvertisement(bus, 0)

    mainloop = GLib.MainLoop()

    service_manager.RegisterApplication(app.get_path(), {},
                                        reply_handler=register_app_cb,
                                        error_handler=register_app_error_cb)

    ad_manager.RegisterAdvertisement(adv.get_path(), {},
                                     reply_handler=register_ad_cb,
                                     error_handler=register_ad_error_cb)
    try:
        mainloop.run()

    except KeyboardInterrupt:
        adv.Release()


if __name__ == '__main__':
    main()

