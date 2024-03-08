import logging
import time

logger = logging.getLogger("pyatcmd.utils")


def wait_for(time_in_sec):
    time.sleep(time_in_sec)


def led(led, state):
    if led not in ["PWR", "ACT"]:
        raise f"Unknown led ({led})"
    with open(f"/sys/class/leds/{led}/brightness", "w") as fp:
        if state == "on":
            fp.write("255")
        else:
            fp.write("0")
