import logging
import datetime
import time

from pathlib import Path

DEFAULT_LOG_PATH = "."


class LoggerFactory():

    def __init__(self, default_lvl=logging.DEBUG):
        self.default_lvl = default_lvl
        self.logger = logging.getLogger("pyatcmd")
        self.logger.setLevel(self.default_lvl)

    def create_logger(self, path=DEFAULT_LOG_PATH, fn=""):

        logging.Formatter.converter = time.gmtime
        filename = fn if fn else f"{datetime.datetime.utcnow().strftime(r'%Y%m%d_%H%M%S')}_default.log"

        # Configure default FileHandler
        try:
            self.f_handler = logging.FileHandler(Path(path, filename))
        except FileNotFoundError:
            path.mkdir(parents=True, exist_ok=True)
            self.f_handler = logging.FileHandler(Path(path, filename))
        self.f_handler.setLevel(logging.DEBUG)
        self.f_format = logging.Formatter(
            '{asctime} {levelname:.1}/ {name:>50} - {message}', style='{', datefmt='%Y-%m-%d %H:%M:%S')
        self.f_handler.setFormatter(self.f_format)

        # Handle default StreamHandler
        self.c_handler = logging.StreamHandler()
        self.c_handler.setLevel(self.default_lvl)
        self.c_format = logging.Formatter(
            '{asctime} {levelname:.1}/ {name:>50} - {message}', style='{', datefmt='%Y-%m-%d %H:%M:%S')
        self.c_handler.setFormatter(self.c_format)

        self.logger = logging.getLogger("pyatcmd")
        self.logger.setLevel(self.default_lvl)
        self.logger.addHandler(self.c_handler)
        self.logger.addHandler(self.f_handler)
        self.logger.info(
            f"LOGGER created with default level {self.default_lvl}")

    def set_fh_level(self, lvl):
        self.f_handler.setLevel(lvl)

    def set_ch_level(self, lvl):
        self.c_handler.setLevel(lvl)

    def set_default_level(self, lvl):
        self.logger.info(f"Setting default level to {lvl}")
        self.default_lvl = lvl

    def update_fh(self, log_path, filename):
        lvl = self.f_handler.level
        fmt = self.f_handler.formatter
        self.logger.removeHandler(self.f_handler)

        try:
            self.f_handler = logging.FileHandler(Path(log_path, filename))
        except FileNotFoundError:
            log_path.mkdir(parents=True, exist_ok=True)
            self.f_handler = logging.FileHandler(Path(log_path, filename))

        self.f_handler.setLevel(lvl)
        self.f_handler.setFormatter(fmt)
        self.logger.addHandler(self.f_handler)


pyatcmd_logger = LoggerFactory()
