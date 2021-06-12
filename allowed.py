import asyncio
import os
import time
from asyncio import sleep

import yaml
from yaml import SafeLoader

from logger import log


class Allowed(object):
    def __init__(self, ymldatafile, ymlipfile):
        self.ymldatafile = ymldatafile
        self.ymlipfile = ymlipfile
        self.allowed_dict = None
        self.load_yml()
        self.waiting_co = None

    def load_yml(self):
        if not os.path.isfile(self.ymldatafile):
            self.allowed_dict = {}
            self.push_data()
        else:
            self.load_data()

    def load_data(self):
        with open(self.ymldatafile, "r") as f:
            self.allowed_dict = yaml.load(f, Loader=SafeLoader)
        self.push_data()

    def push_data(self):
        if self.allowed_dict is None:
            return
        with open(self.ymlipfile, "w") as f:
            yaml.dump(
                {
                    "http": {
                        "middlewares": {
                            "ipwhitelist": {
                                "ipWhiteList": {
                                    "sourceRange": list(self.allowed_dict.keys())
                                }
                            }
                        }
                    }
                },
                f,
            )
        with open(self.ymldatafile, "w") as f:
            yaml.dump(self.allowed_dict, f)

    def get_allowed(self):
        now = int(time.time())
        refreshed_allowed = {
            ip: data
            for ip, data in self.allowed_dict.items()
            if data["expiration"] == 0 or data["expiration"] > now
        }
        if len(refreshed_allowed) != len(self.allowed_dict):
            self.allowed_dict = refreshed_allowed
            self.push_data()
        return self.allowed_dict

    def add_allowed(self, ip, desc, expiration):
        log(f"Adding {ip}")
        now = int(time.time())
        if (
            expiration > 0
            and expiration - now < self.recommended_waiting_time()
            and self.waiting_co
        ):
            self.waiting_co.cancel()
        self.allowed_dict[ip] = {
            "desc": desc,
            "expiration": expiration,
        }
        self.push_data()

    def del_allowed(self, ip):
        log(f"Deleting ip {ip}")
        if ip in self.allowed_dict:
            del self.allowed_dict[ip]
            self.push_data()

    def recommended_waiting_time(self):
        self.get_allowed()
        now = int(time.time())
        try:
            next_expire = min(
                [
                    a["expiration"]
                    for ip, a in self.allowed_dict.items()
                    if a["expiration"] > 0
                ]
            )
            recommended_waiting_time = next_expire - now
        except ValueError:
            recommended_waiting_time = 3600
        return min(recommended_waiting_time, 3600)

    async def wait_for_expiration(self):
        if self.waiting_co:
            raise Exception("Should not happen")
        recommended_waiting_time = self.recommended_waiting_time()
        log(f"Waiting for {recommended_waiting_time}")
        self.waiting_co = asyncio.create_task(sleep(recommended_waiting_time))
        try:
            await self.waiting_co
            self.waiting_co = None
            return False
        except asyncio.CancelledError:
            log(f"Allowed has been updated, refreshing waiting time")
            self.waiting_co = None
            return True
