import re
import time
import logging

from .serial_manager import SerialManager
from .utils import wait_for
from .constants import TCPIP_ERROR_CODES

logger = logging.getLogger("pyatcmd.at_manager")


class AT(SerialManager):

    def __init__(self):
        SerialManager.__init__(self)
        self.port_name = None

    def __enter__(self):
        self.open_port()
        logger.debug("AT Port opened")

    def __exit__(self, *args):
        self.close_port()
        logger.debug("AT Port closed")

    def open_port(self):
        if self.port_name is None:
            self.port_name = self.get_at_port_name()
        self.port = self.open_serial_port(self.port_name, timeout=1)

    def close_port(self):
        self.close_serial_port(self.port)

    def is_available(self):
        if not self.port.isOpen():
            try:
                self.open_port()
            except Exception:
                return False
        try:
            resp = self.write_serial_port(self.port, "AT", print_output=False)
            for line in resp:
                if line != "" and not re.search("^AT|^OK", line):
                    logger.info(f"{self.port_name} - {resp}")

            if "OK" in resp:
                return True
            return False
        except Exception as e:
            try:
                logger.debug(
                    f"Unable to send 'AT' command. Failed to write on serial port: {e}-Type:{type(e)}.")
                self.close_port()
            except Exception:
                logger.debug(
                    f"is_available: Failure while trying to close port: {e}")
            finally:
                return False

    def wait_until_module_unavalaible(self, interval=0.5, timeout=30, check_communication=False):
        duration = 0
        is_disconnected = False
        start_time = time.time()
        while not is_disconnected and duration < timeout:
            wait_for(interval)
            if check_communication:
                is_disconnected = not self.is_available()
            else:
                try:
                    self.close_port()
                    self.open_port()
                except Exception as e:
                    logger.debug(
                        f"wait_until_module_unavalaible#DISCONNECTED:{e}")
                    is_disconnected = True
            duration = int(time.time() - start_time)

        if duration >= timeout and not is_disconnected:
            logger.error(f"AT port is still available after {timeout}s")
            has_been_rebooted = False
        else:
            logger.info("Module is now disconnected")
            has_been_rebooted = True
            wait_for(0.1)
            if not check_communication:
                if self.port.isOpen():
                    logger.info("AT PORT IS OPEN")
                    self.close_port()
                    logger.info("AT PORT CLOSED")
                else:
                    logger.info("AT PORT WAS NOT OPEN")
        return has_been_rebooted

    def wait_until_module_avalaible(self, interval=0.5, timeout=60, check_communication=False):
        logger.info(f"Wait until module is available (timeout:{timeout})")
        is_disconnected = True
        start_time = time.time()
        duration = 0

        while is_disconnected and duration <= timeout:
            wait_for(interval)
            if check_communication:
                is_disconnected = not self.is_available()
            else:
                try:
                    if not self.port.isOpen():
                        self.open_port()
                    is_disconnected = False
                except Exception:
                    pass
            duration = int(time.time() - start_time)

        if duration > timeout:
            raise Exception(
                "Device is not enumerated (COM port stuck?) after reboot")

        if is_disconnected:
            raise Exception(
                f"Timeout reached: the Device is still disconnected after {duration}s.")

        logger.info(f"Reboot time: {duration}s")
        logger.info("Module is now connected")
        logger.info("OPENING AT PORT")
        return duration

    def wait(self, time_to_wait):
        return self.wait_reading_port(self.port, time_to_wait)

    def send_cmd(self, cmd, timeout=60, wait_resp="(OK|ERROR)", eol=True):
        resp = self.write_serial_port(self.port, cmd, eol=eol)
        if not wait_resp:
            return resp

        for line in resp:
            if wait_resp:
                if re.search(wait_resp, line):
                    return resp
        return resp + self.wait_for_response(self.port, wait_resp, timeout=timeout)

    def get_imsi(self):
        resp = self.send_cmd("AT+CIMI")
        for line in resp:
            if re.search(r"\d{15}", line):
                return line
            elif re.search("ERROR", line):
                logger.error("Unable to get IMSI from module")
                return None

    def get_iccid(self):
        resp = self.send_cmd("AT+CCID")
        for line in resp:
            if re.search(r"(\d{20})(,\d+)?", line):
                return re.search(r"(\d{20})(,\d+)?", line).group(1)
            elif re.search("ERROR", line):
                logger.error("Unable to get ICCID from module")
                return None

    def soft_reset(self):
        self.send_cmd("AT+CFUN=1,1")
        self.wait_until_module_unavalaible()
        self.wait_until_module_avalaible()
        restart_time = time.time()
        # wait_for(5)
        # self.enable_unsollicited_nw_registration_cmd()
        return restart_time

    def enable_unsollicited_nw_registration_cmd(self):
        self.send_cmd("AT+COPS=3,2")
        self.send_cmd("AT+CREG=2", timeout=1)
        self.send_cmd("AT+CGREG=2", timeout=1)
        self.send_cmd("AT+CEREG=2", timeout=1)

    def set_automatic_nw_mode(self):
        self.send_cmd("AT+COPS=0")

    def check_attach_notifications(self, resp, data_required=True, data_only=False, details=False):
        is_attached_c = False
        is_attached_cg = False
        is_attached_ce = False
        for r in resp:
            if re.search(r"\+CREG: (2,)?5", r):
                is_attached_c = True
            elif re.search(r"\+CGREG: (2,)?5", r):
                is_attached_cg = True
            elif re.search(r"\+CEREG: ([24],)?5", r):
                is_attached_ce = True
            elif re.search(r"\+CREG: (0|2|3)", r):
                is_attached_c = False
            elif re.search(r"\+CGREG: (0|2|3)", r):
                is_attached_cg = False
            elif re.search(r"\+CEREG: (0|2|3)", r):
                is_attached_ce = False

        if details:
            return (is_attached_c, is_attached_cg, is_attached_ce)
        else:
            return self.attach_check(is_attached_c, is_attached_cg, is_attached_ce, data_required, data_only)

    def attach_check(self, c, cg, ce, data_req, data_only):
        if data_only:
            return cg or ce
        elif data_req:
            return c and (cg or ce)
        else:
            return c

    def is_attached(self, data_required=True, data_only=False, details=False, response=None):

        full_resp = self.send_cmd("AT+CREG?", timeout=1)
        full_resp += self.send_cmd("AT+CGREG?", timeout=1)
        full_resp += self.send_cmd("AT+CEREG?", timeout=1)

        if isinstance(response, list):
            response.extend(full_resp)

        return self.check_attach_notifications(full_resp, data_required, data_only, details)

    def is_lte_attached(self):
        resp = self.send_cmd("AT+COPS?")
        logger.debug("### AT+COPS? returned:")
        for r in resp:
            logger.debug(f"### {r}")
            if re.search(r"\+COPS:.*(\d+)", r):
                if re.search(r"\+COPS:.*(\d+)", r).group(1) == "7":
                    return True
        return False

    def get_current_nw_name(self):
        resp = self.send_cmd("AT+COPS?")
        for r in resp:
            if re.search(r"\+COPS: \d+,\d+,\"(.*)\",.*", r):
                return re.search(r"\+COPS: \d+,\d+,\"(.*)\",.*", r).group(1)
        return ""

    def wait_for_attachment(self, data_required=True, data_only=False, timeout=180):
        start_time = time.time()
        resp = at.register()
        attach_c, attach_cg, attach_ce = self.check_attach_notifications(
            resp, data_required=data_required, data_only=data_only, details=True)
        attached = self.attach_check(
            attach_c, attach_cg, attach_ce, data_required, data_only)
        while not attached:
            resp += self.wait(1)
            attach_c, attach_cg, attach_ce = self.check_attach_notifications(
                resp, data_required=data_required, data_only=data_only, details=True)
            attached = self.attach_check(
                attach_c, attach_cg, attach_ce, data_required, data_only)
            if int(time.time() - start_time) > timeout:
                raise Exception(
                    f"Device not attached to the network after {timeout}s")
        return attach_c, attach_cg, attach_ce

    def configure_sms(self):
        self.send_cmd("AT+CNMI=1,2,2,0,0")
        self.send_cmd("AT+CMGF=1")

    def send_sms(self, msisdn, msg):
        resp = self.send_cmd(f"AT+CMGS=\"{msisdn}\"", wait_resp="")
        resp += self.send_cmd(msg, wait_resp="", eol=False)
        resp += self.send_cmd(chr(26), timeout=300, eol=False)
        return resp

    def check_resp(self, resp):
        for line in resp:
            if re.search("ERROR", line):
                return False
            elif re.search("OK", line):
                return True
        return True

    def get_ip_address(self):
        self.send_cmd("AT+CGACT=1,1")
        resp = self.send_cmd("AT+CGCONTRDP")
        for line in resp:
            regex = r"\+CGCONTRDP: \d,\d,[\w\.]*,(\d+\.\d+\.\d+\.\d+),.*"
            if re.search(regex, line):
                return re.search(regex, line).group(1)
        return ""

    def deregister(self):
        return self.send_cmd("AT+CFUN=4")

    def register(self):
        return self.send_cmd("AT+CFUN=1")

    def check_ping_support(self):
        logger.debug("Testing Quectel command (AT+QPING)")
        resp = self.send_cmd("AT+QPING=?")
        for line in resp:
            if re.search("OK", line):
                return "QPING"
        logger.debug("Quectel command (AT+QPING) not supported")
        return None

    def force_roaming_nw(self, nw_name):
        if re.search(r"\d{5,6}", nw_name):
            mode = "2"  # numeric value
        else:
            mode = "0"  # Long format alphanumeric
        resp = self.send_cmd(f"AT+COPS=1,{mode},\"{nw_name}\"")
        for line in resp:
            if re.search("ERROR", line):
                return self.send_cmd(f"AT+COPS=1,{mode},\"{nw_name}\"")
        return resp

    def check_ping_command(self):
        resp = self.send_cmd("AT+QPING=?")  # Quectel Modem
        for line in resp:
            if re.search("OK", line):
                return "QPING"
        resp = self.send_cmd("AT+CPING=?")  # SIMCOM Modem
        for line in resp:
            if re.search("OK", line):
                return "CPING"
        return ""

    def send_ping_request(self, ping_cmd, host, cid="1"):
        if ping_cmd == "QPING":
            qping_result_regex = r"\+QPING: (\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)"
            qping_error_regex = r"\+QPING: (\d+)$"
            resp_to_wait = r"\+QPING\: (?:(?:(\d+),10,.*)|(?:(\d+)$))"
            resp = self.send_cmd(
                f"AT+QPING={cid},\"{host}\",4,10", timeout=60, wait_resp=resp_to_wait)
            for line in resp:
                if re.search(qping_result_regex, line):
                    results = re.search(qping_result_regex, line).groups()
                    logger.info("QPING request stats")
                    logger.info(f"   - Final Result : {results[0]}")
                    logger.info(f"   -         Sent : {results[1]}")
                    logger.info(f"   -     Received : {results[2]}")
                    logger.info(f"   -         Lost : {results[3]}")
                    logger.info(f"   -  Min Latency : {results[4]} ms")
                    logger.info(f"   -  Max Latency : {results[5]} ms")
                    logger.info(f"   -  Avg Latency : {results[6]} ms")
                    return results
                elif re.search(qping_error_regex, line):
                    error = re.search(qping_error_regex, line).group(1)
                    if error in TCPIP_ERROR_CODES:
                        logger.error(
                            f"PING ERROR: {TCPIP_ERROR_CODES[error]} ({error})")
                    else:
                        logger.error(f"PING ERROR: Unknown({error})")
                    return [error, "10", "0", "10", "", "", ""]
            logger.error("PING ERROR - PING request should have timed out")
            return ["Unknown error", "10", "0", "10", "", "", ""]
        elif ping_cmd == "CPING":
            cping_result_regex = r"\+CPING: (\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)"
            cping_error_regex = r"\+CPING: 2"
            resp_to_wait = r"\+CPING\: 3,.*"
            resp = self.send_cmd(
                f"AT+CPING=\"{host}\",1,10", timeout=180, wait_resp=resp_to_wait)
            for line in resp:
                if re.search(cping_result_regex, line):
                    results = re.search(cping_result_regex, line).groups()
                    if results[1] == "0":
                        logger.error("PING ERROR (unknown)")
                        return ["3", "10", "0", "10", "", "", ""]
                    logger.info("CPING request stats")
                    logger.info(f"   - Final Result : {results[0]}")
                    logger.info(f"   -         Sent : {results[1]}")
                    logger.info(f"   -     Received : {results[2]}")
                    logger.info(f"   -         Lost : {results[3]}")
                    logger.info(f"   -  Min Latency : {results[4]} ms")
                    logger.info(f"   -  Max Latency : {results[5]} ms")
                    logger.info(f"   -  Avg Latency : {results[6]} ms")
                    return results
                elif re.search(cping_error_regex, line):
                    logger.error("PING TIMEOUT")
        return ['-1']

    def read_fplmn(self):
        resp = self.send_cmd('AT+CRSM=176,28539,0,0,24')
        for line in resp:
            if re.search(r'\+CRSM: .*\"([0-9A-F]{48})\".*', line):
                return re.search(r'\+CRSM: .*\"([0-9A-F]{48})\".*', line).group(1)
        resp = self.send_cmd('AT+CRSM=176,28539,0,0,12')
        for line in resp:
            if re.search(r'\+CRSM: .*\"([0-9A-F]{24})\".*', line):
                return re.search(r'\+CRSM: .*\"([0-9A-F]{24})\".*', line).group(1)
        return ""

    def enable_timezone_update(self):
        self.send_cmd('AT+CTZU=1')

    def get_time_and_date(self):
        return self.send_cmd("AT+CCLK?")

    def configure_ntp(self):
        return self.send_cmd('AT+QNTP=1,"time.google.com", 123')

    def enable_modem_logging(self):
        return self.send_cmd('AT+QCFG="dbgctl",0')

    def get_signal_strengh(self):
        self.send_cmd('AT+CSQ')
        self.send_cmd('AT+QENG="servingcell"')


at = AT()
