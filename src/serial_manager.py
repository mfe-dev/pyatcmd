import sys
import serial
import serial.tools.list_ports
import re
import time
import traceback
import threading
import logging

logger = logging.getLogger("pyatcmd.serial_manager")


class SerialManager:

    def __init__(self):
        self.readError = 0
        self.rLock = threading.Lock()
        pass

    def open_serial_port(self, port, baudrate=115200, timeout=1, write_timeout=None):
        p = None
        self.rLock.acquire()
        try:
            p = serial.Serial(port, baudrate=baudrate, timeout=timeout,
                              write_timeout=write_timeout, exclusive=True)
            return p
        except Exception:
            raise
        finally:
            self.rLock.release()

    def close_serial_port(self, port):
        self.rLock.acquire()
        try:
            port.close()
        except Exception:
            raise
        finally:
            self.rLock.release()

    def read_serial_port(self, port=None, print_output=False):
        clean_response = []
        if port is not None:
            start = time.time()
            while (time.time() - start) < port.timeout:
                try:
                    response = port.readline().decode()
                    self.readError = 0
                except Exception:
                    response = None
                    self.readError += 1
                    logger.error(f"ERROR reading PORT{port.name}")
                    time.sleep(1)
                    if self.readError > 10:
                        logger.error(traceback.format_exc())
                        raise Exception(
                            f"{port.name} seems stuck - Please check manually and reboot if necessary")
                if isinstance(response, str):
                    clean_response.append(re.sub("\\r|\\n", "", response))
                    if print_output:
                        resp = str(re.sub("\\r|\\n", "", response))
                        if resp != "":
                            logger.info(f"{port.name} - {resp}")
        return clean_response

    def wait_for_response(self, port, response, timeout=180, silent=False):
        start_time = time.time()
        return_flag = False
        full_resp = []
        while not return_flag:
            resp = self.read_serial_port(port)
            full_resp += resp
            for line in resp:
                if line != "":
                    logger.info(f"{port.name} - {line}")
                    regex = ".*" + response + ".*"
                    if re.search(regex, line):
                        return_flag = True
                    elif re.search("ERROR", line):
                        return_flag = True
            if return_flag:
                return full_resp
            duration = time.time() - start_time
            if int(duration) >= timeout:
                if not silent:
                    logger.error(
                        f"{port.name} - TIMEOUT IN WAIT_FOR_RESPONSE - {response} not received in {timeout}s")
                return_flag = True
                return []

    def wait_reading_port(self, port, time_to_wait):
        start_time = time.time()
        duration = 0
        resp = []
        while duration < time_to_wait:
            resp += self.read_serial_port(port, True)
            duration = int(time.time() - start_time)
        return resp

    def write_serial_port(self, port, cmd, print_output=True, eol=True):
        if not port:
            raise Exception("COM Port is not available")
        if eol:
            cmd += "\r"

        self.rLock.acquire()
        try:
            port.write(cmd.encode())
            response = self.read_serial_port(port)
        except serial.SerialException:
            logger.error(
                "SerialException : Unable to read port - Device could be already disconnected")
            response = []
            raise
        finally:
            self.rLock.release()

        if print_output:
            for res in response:
                logger.info(f"{port.name} - {str(res)}")
        return response

    def write_serial_port_no_response(self, port, cmd, eol=True):
        if not port:
            raise Exception("COM Port is not available")
        if eol:
            cmd += "\r"

        self.rLock.acquire()
        try:
            port.write(cmd.encode())
        except serial.SerialException:
            logger.error(
                "SerialException : Unable to write on port - Device could be already disconnected")
            raise
        finally:
            self.rLock.release()

    def get_com_port_list(self):
        return list(serial.tools.list_ports.comports(True)) if re.search("linux", sys.platform) else list(serial.tools.list_ports.comports())

    def get_full_com_port_list(self):
        com_port_list = []
        for p in ["COM%s" % (i + 1) for i in range(256)]:
            try:
                s = serial.Serial(p)
                s.close()
                com_port_list.append(p)
            except (OSError, serial.SerialException):
                pass
        return com_port_list

    def get_at_port_name(self):
        for p in sorted(self.get_com_port_list()):
            if re.search(r"/dev/ttyUSB*", p.device):
                print(f"Trying {p.device}")
                try:
                    at_port = None
                    at_port = self.open_serial_port(p.device, write_timeout=1)
                    if "OK" in self.write_serial_port(at_port, "ATE1\r", print_output=True):
                        return p.device
                except Exception:
                    pass
                finally:
                    if at_port:
                        self.close_serial_port(at_port)

    def get_dm_port_name(self):
        for p in self.get_com_port_list():
            if re.search("DM Port", p.description):
                return p.name
        return ""


serial_manager = SerialManager()
