import time


def log(msg):
    ts = time.strftime("%Y/%m/%d %H:%M:%S")
    print("[+] {} - {}".format(ts, msg))