#!/usr/bin/env python3
# Log data from serial port

# Author: Diego Herranz

import argparse
import serial
import datetime
import logging
import sys


log = logging.getLogger("gps")
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-d", "--device", help="device to read from", default="/dev/ttyS2")
parser.add_argument("-r", "--raw", help="enable m8n raw logs", default=True, type=bool)
parser.add_argument("-l", "--log-dir", help="directory for logs", type=str, required=True)
args = parser.parse_args()
logpath = args.log_dir + "/"
runid_path = logpath + ".runid"
file = None
tag = None


def get_run_id():
    try:
        with open(runid_path, 'r') as rf:
            return int(rf.readline().strip())
    except Exception as err:
        log.exception(err)
        return 0


def set_run_id(id):
    with open(runid_path, 'w') as rf:
        rf.write(str(id))


run_id = get_run_id()
run_id += 1
set_run_id(run_id)
file_id = 0

log.info("Running with id %i" % (run_id))


def switch_file(newtag):
    global tag
    global file
    global run_id
    global file_id

    if tag == newtag:
        return

    tag = None

    if file is not None:
        file.close()
        file = None

    path = logpath + "gps-log-%i-%i-%s.txt" % (run_id, file_id, newtag)
    file = open(path, mode='wb')
    tag = newtag
    file_id += 1
    log.info("Switched file to " + path)

def ubx_add_crc(data):
    CK_A = 0
    CK_B = 0
    for b in data[2:]:
        CK_A = (CK_A + b) % 256
        CK_B = (CK_B + CK_A) % 256

    return data+bytes([CK_A, CK_B])

def ubx_write(ser: serial.Serial, cmd):
    b = ubx_add_crc(bytes.fromhex(cmd))
    log.debug(">>> '%s'", b.hex())
    ser.write(b)

def initialize_port(ser: serial.Serial):
    # To enable UBX-protocol in and out and speed 115200 on UART1.
    ubx_write(ser, "B5620600140001000000D008000000C201000700030000000000")

def initialize_raw(ser: serial.Serial):
    # To enable TRK-SFRBX03x0F

    ubx_write(ser, "B56206010300030F01")

    # To enable TRK-MEAS 03x10

    ubx_write(ser, "B56206010300031001")

    # To enable NAV-CLOCK

    ubx_write(ser, "B56206010300012201")

    # To enable NAV-SVINFO

    ubx_write(ser, "B56206010300013001")

    # To change sample rate to 5Hz or 200ms

    ubx_write(ser, "B56206080600FA0001000100")


log.info("Logging started. Ctrl-C to stop.")
while True:
    ser = serial.Serial(args.device, 115200, timeout=1)
    initialize_raw(ser)
    try:
        while True:
            newtag = datetime.datetime.now().strftime("%Y-%m-%dT%H.%M")
            switch_file(newtag)
            data = ser.read(1)
            waiting = ser.inWaiting()
            if waiting > 0:
                data += ser.read(waiting)
            if len(data) == 0:
                log.error("No data received, reopening")
                break
            file.write(data)
            file.flush()
    except KeyboardInterrupt:
        break
    except Exception as err:
        log.exception("Something went wrong, trying again", err)
