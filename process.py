#!/usr/bin/env python3

import yaml
import re
import sys
from os import walk
import matplotlib.path as mpltPath
import numpy as np

path = "../"

with open('sectors', 'r') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    sectors = yaml.load(file, Loader=yaml.FullLoader)

print(sectors)
#sys.exit(1)
pre_finish_sector = mpltPath.Path(sectors['pre_finish'])

def files(path):
    _, _, filenames = next(walk(path))

    order = {}

    r = re.compile("gps-log-([\d]*)-([\d]*)-.*")
    for f in filenames:
        m = r.match(f)
        run = int(m.group(1))
        minute = int(m.group(2))
        if run not in order:
            order[run] = {}
        order[run][minute] = f

    for run in sorted(order):
        for minute in sorted(order[run]):
            yield order[run][minute]

rmc = re.compile("\$..RMC.([\d]{2})([\d]{2})([\d]{2})\.([\d]{2})\,A,([0-9]*)([0-9]{2}\.[0-9]*),(.),([0-9]*)([0-9]{2}\.[0-9]*),(.),([0-9\.]*),([0-9\.]*),([\d]{2})([\d]{2})([\d]{2})")
for filename in files(path):
    print(filename)
    with open(path + filename, 'r') as f:
        for l in f:
            l=l.strip()
            m = rmc.match(l)
            if m:
                DD=int(m.group(13))
                MM=int(m.group(14))
                YY=int(m.group(15))
                hh=int(m.group(1))
                mm=int(m.group(2))
                ss=int(m.group(3))
                ms=int(m.group(4))*10
                lat=float(m.group(5)) + float(m.group(6))/60
                latH=m.group(7)
                lon=float(m.group(8)) + float(m.group(9))/60
                lonH=m.group(10)

                speed=float(m.group(11)) * 1.852
                direction = None
                if m.group(12):
                    direction=float(m.group(12))

                point = [[lat, lon]]
#                print(point)
                if pre_finish_sector.contains_points(point):
                    print(l)

#                print(l)
#                print(m.groups())
#                if speed > 30:
#                    print(DD,MM,YY, lat, lon, speed, direction)
#                print(lat, lon)
#                print(m.group(5), m.group(7), m.group(9))

