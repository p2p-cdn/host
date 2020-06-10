#!/usr/bin/env python

from __future__ import print_function, division, unicode_literals

import argparse
import os
import sys
import signal
import subprocess
import platform
import tarfile
import shutil
import time
import json
from collections import defaultdict
from random import random

if sys.version_info.major == 3:
    from urllib.request import urlretrieve
else:
    from urllib import urlretrieve

class IPFSNode:
    def __init__(self, id, address):
        assert id in address
        self.id = id
        self.address = address


class IPFSFile:
    def __init__(self, url, hash):
        self.url = url
        self.hash = hash

FILES = {
    "ipad": IPFSFile(
        "https://www.apple.com/105/media/us/ipad-pro/2020/7be9ce7b-fa4e-4f54-968b-4a7687066ed8/films/feature/ipad-pro-feature-tpl-cc-us-2020_1280x720h.mp4",
        "QmfBsQa4iZRsKkELk7QGP4acN4sX6WfvBvVWT4Tz5yuE24"
    ),
    "iphone": IPFSFile(
        "https://www.apple.com/v/home/f/images/heroes/iphone-se/hero__dvsxv8smkkgi_large.jpg",
        "Qmay7eKcsxZ5UkraAucEGtTsv6LzA5hn3P8JnQQcWaVwcN"
    ),
    "apple1": IPFSFile(
        "https://www.apple.com/v/home/f/images/heroes/iphone-se/hero__dvsxv8smkkgi_large.jpg",
        "Qmay7eKcsxZ5UkraAucEGtTsv6LzA5hn3P8JnQQcWaVwcN"
    ),
    "apple2": IPFSFile(
        "https://www.apple.com/v/home/h/images/heroes/iphone-11-spring/hero__dvsxv8smkkgi_large.jpg",
        "QmZuH57WXytRdj9bqNYcJxCRmqhLHsoQapmtiiH8EzfRwm"
    ),
    "apple3": IPFSFile(
        "https://www.apple.com/v/home/h/images/promos/mothers-day/tile__cauwwcyyn9hy_large.jpg",
        "QmfChqUww9HhCt6SAapvFFrwacgjtCg27g8QiteUZxP9S3"
    ),
    "apple4": IPFSFile(
        "https://www.apple.com/v/home/h/images/heroes/iphone-11-pro-spring/hero__dvsxv8smkkgi_large.jpg",
        "QmQviWwJoq5Hq8nHkbhhUWKhXHTfG2Lj2457yGsYV2P52S"
    ),
    "apple5": IPFSFile(
        "https://www.apple.com/v/home/h/images/promos/wwdc-2020/tile__cauwwcyyn9hy_large.jpg",
        "QmRiMXxKPcVRV2Nzou3pGE1RFdMn6ANDeCr1i2QY9A9YAm"
    ),
    "apple6": IPFSFile(
        "https://www.apple.com/v/home/h/images/promos/taa-refresh/tile__cauwwcyyn9hy_large.jpg",
        "Qma3U4FPDV556WS8Uv1HMrru6f3sX9dBjjwFkRFf5Bmb3J"
    ),
    "apple7": IPFSFile(
        "https://www.apple.com/v/home/h/images/promos/watch-series-5/tile_aws5__fwphji1d8yeu_large.jpg",
        "QmQQ7sygVC6H1PHw2wDtj4VMyXUM2ezVjJGcAGuXwJo2LZ"
    ),
    "apple8": IPFSFile(
        "https://www.apple.com/v/home/h/images/logos/covid-19-app/logo__dcojfwkzna2q_large.png",
        "QmPXaxuwPRbX5XjuNdbAS2AMK1N5J2RxLmEmxDzzMNnr3U"
    ),
    "apple9": IPFSFile(
        "https://www.apple.com/v/home/h/images/promos/tv-plus-trying/tile__cauwwcyyn9hy_large.jpg",
        "QmXEhmHg6an55xH7nKnUYrTiotRMRMGMRCPHTjAJeNdEVt"
    ),
}

class IPFSClient:
    def __init__(self, ipfs_binary, ipfs_path):
        self.ipfs_binary = ipfs_binary
        self.ipfs_path = ipfs_path
        self.devnull = open(os.devnull, "w")
        self._ensure_path()

    def teardown(self):
        self.kill_daemon()
        self._unset_path()

    def launch_daemon(self):
        if self.daemon_available():
            return
        elif self.daemon_running():
            self.kill_daemon()
        print("Launching daemon...")
        while not self.daemon_running():
            try:
                subprocess.Popen(
                    self._get_command("daemon &"), shell=True, stdout=self.devnull)
            except:
                self.kill_daemon()
        while not self.daemon_available():
            print("Waiting for daemon... [may take a min, do not quit]")
            time.sleep(1)
        print("Success.")

    def daemon_available(self):
        try:
            subprocess.check_call(
                self._get_command("stats bitswap"),
                shell=True,
                stdout=self.devnull,
                stderr=self.devnull,
            )
            return True
        except:
            return False

    def daemon_running(self):
        try:
            return int(subprocess.check_output("pgrep ipfs", shell=True).strip())
        except:
            return False

    def kill_daemon(self):
        pid = self.daemon_running()
        while self.daemon_running():
            print("Killing daemon...")
            try:
                os.kill(pid, signal.SIGKILL)
            except:
                return

    def init(self):
        try:
            subprocess.check_call(
                self._get_command("init"),
                shell=True,
                stdout=self.devnull,
                stderr=self.devnull,
            )
        except:
            pass

    def is_connected(self, ipfs_node):
        addrs = self.check_output("swarm addrs").decode("utf8")
        return ipfs_node.id in addrs

    def ensure_connected(self, ipfs_node):
        if not self.is_connected(ipfs_node):
            self.check_output("swarm connect {}".format(ipfs_node.address))

    def ensure_disconnected(self, ipfs_node):
        if self.is_connected(ipfs_node):
            self.check_output("swarm disconnect {}".format(ipfs_node.address))

    def call(self, command):
        return subprocess.call(self._get_command(command), shell=True)

    def time_get(self, hash):
        return float(self.time("get {}".format(hash)).strip())

    def time(self, command):
        # TIMEFORMAT=%R
        if os.environ.get("TIMEFORMAT") != "%R":
            os.environ["TIMEFORMAT"] = "%R"
        try:
            return subprocess.check_output("(time " + self._get_command(command) + "&> /dev/null ) 2>&1", shell=True, executable='bash').decode("utf8")
        except:
            print("ERROR: Failed to run ipfs command: {}. Please report this error".format(command))
            exit()
        os.environ.pop("TIMEFORMAT", None)
        os.unsetenv("TIMEFORMAT")

    def check_output(self, command):
        try:
            return subprocess.check_output(self._get_command(command), shell=True)
        except:
            print("ERROR: Failed to run ipfs command: {}. Please report this error".format(command))
            exit()

    def _ensure_path(self):
        if os.environ.get("IPFS_PATH") != self.ipfs_path:
            os.environ["IPFS_PATH"] = self.ipfs_path

    def _unset_path(self):
        os.environ.pop("IPFS_PATH", None)
        os.unsetenv("IPFS_PATH")

    def _get_command(self, command):
        return "{} {}".format(self.ipfs_binary, command)

    def get_stats(self, file, hosts, samples=10):
        print("Collecting ipfs stats...")
        gets = []
        tries = 0
        while len(gets) < samples and tries < samples*2:
            tries += 1
            print("Attempt {} out of (min: {}, max: {})".format(tries, samples, samples*2))
            for h in hosts:
                self.ensure_connected(h)
            self.check_output("repo gc")
            if os.path.exists(file.hash):
                os.remove(file.hash)
            t = self.time_get(file.hash)
            if all(self.is_connected(h) for h in hosts):
                gets.append(t)
        if os.path.exists(file.hash):
            os.remove(file.hash)
        return {"tries": tries, "gets": gets, "average": sum(gets) / len(gets)}

    # all nodes in our CDN swarm repeatedly generate or request this ever-changing file,
    #   using the existing IPFS DHT to discover other peers who are doing the same
    # hosts generate the next two files in advance to be ready to be found
    def genHostSwarmFiles(self):
        # gen session id based on only known piece of shared* data: time
        #   *yes I know time is hard, but it's approximately shared
        sessionId = int(time.time() / 60) # new session every minute
        # generate the token for this session and the next two
        sharedTokens = ["Member of P2P CDN Session: {}".format(sessionId + i) for i in range(3)]
        # add and pin those tokens
        for t in sharedTokens:
            cmd = 'echo -n "{0}" | {1} add | awk  {2} | {1} pin add'.format(t, self.ipfs_binary, "'{print $2}'")
            try:
                subprocess.check_output(cmd, shell=True)
            except:
                print("ERROR: Failed to run command: {}. Please report this error".format(cmd))

class IPFSDownloader:
    BASE_URL = "https://dist.ipfs.io/go-ipfs/v0.5.0/go-ipfs_v0.5.0_"
    FOLDER_NAME = "go-ipfs"
    PATH_TO_FOLDER = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), FOLDER_NAME)

    @classmethod
    def run(cls):
        if os.path.exists(cls.PATH_TO_FOLDER):
            return cls.PATH_TO_FOLDER
        cls.download_and_extract(cls.get_ipfs_download_link())
        return cls.PATH_TO_FOLDER

    @classmethod
    def delete(cls):
        print("Deleting folder...")
        if os.path.exists(cls.PATH_TO_FOLDER):
            shutil.rmtree(cls.PATH_TO_FOLDER)

    @classmethod
    def get_ipfs_download_link(cls):
        return cls.BASE_URL + cls.get_ipfs_download_postfix()

    @staticmethod
    def get_ipfs_download_postfix():
        is_64bits = sys.maxsize > 2 ** 32
        is_arm = "arm" in platform.machine()
        platform_name = sys.platform

        if platform_name == "linux" or platform_name == "linux2":
            # linux
            if is_arm:
                if is_64bits:
                    return "linux-arm64.tar.gz"
                return "linux-arm.tar.gz"

            if is_64bits:
                return "linux-amd64.tar.gz"
            return "linux-386.tar.gz"

        elif platform_name == "darwin":
            # OS X
            if is_64bits:
                return "darwin-amd64.tar.gz"
            return "darwin-386.tar.gz"
        elif platform_name == "win32":
            # Windows...
            sys.exit("Windows is not supported")

    @staticmethod
    def download_and_extract(url):
        print("Downloading...")
        file_tmp = urlretrieve(url, filename=None)[0]
        tar = tarfile.open(file_tmp)
        print("Extracting...")
        tar.extractall()


def main():
    parser = argparse.ArgumentParser(
        description="Experiments. Please contact the sender for questions.")
    parser.add_argument("--kill",
                        help="Kill the background node",
                        action="store_true")
    parser.add_argument("-d", "--dotipfs",
                        help="/path/to/.ipfs/ (default: .ipfs)")
    args = parser.parse_args()

    if sys.platform == "win32":
        sys.exit("Windows is not supported")

    ipfs_folder = IPFSDownloader.run()
    if args.dotipfs:
        dotipfs = args.dotipfs
    else:
        dotipfs = os.path.join(ipfs_folder, ".ipfs/")
    ipfs = IPFSClient(os.path.join(ipfs_folder, "ipfs"), dotipfs)
    ipfs.init()

    if args.kill:
        ipfs.kill_daemon()
    else:
        print(
"""
Thank you for volunteering! You've helping us beat commercial CDNs
with P2P technology!

Please keep your computer powered on and connected to the internet. Do
not tamper with the ./go-ipfs directory or the running ipfs daemon
process.

If you wish to turn off the host (we hope you'll stay!) you may run:
./host.py --kill
 """)

        ipfs.launch_daemon()

        # pin the files
        for f in FILES.values():
            print("pinning {}...".format(f.hash))
            ipfs.check_output("pin add {}".format(f.hash))

        print("\nIPFS client info (using {}):".format(dotipfs))
        ipfs.call("id")

        print(
"""
Host is running! Pleae do not close this shell.

To keep running long term, we recommend using tmux
(https://github.com/tmux/tmux/wiki) or screen
(https://www.gnu.org/software/screen/). Feel free to close and rerun
this script as needed.
 """)
        while True:
            ipfs.launch_daemon()
            ipfs.genHostSwarmFiles()
            time.sleep(60)

    ipfs.kill_daemon()
    ipfs.teardown()
    IPFSDownloader.delete()

if __name__ == "__main__":
    main()
