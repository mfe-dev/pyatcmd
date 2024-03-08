import logging

from src.at_manager import at
from src.logger_factory import pyatcmd_logger

logger = logging.getLogger("pyatcmd.examples.get_imsi")

pyatcmd_logger.create_logger()

with at:
    logger.info(f"Connected to {at.port_name}")
    logger.info("Getting SIM Card IMSI")
    imsi = at.get_imsi()
    logger.info(f"IMSI is {imsi}")
