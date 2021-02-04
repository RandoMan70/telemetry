#!/usr/bin/env python3

import json
import re
import sys
from os import walk
import numpy as np
from numpy.linalg import norm
import matplotlib.path as mpltPath
import matplotlib.lines as mpltLines

path = "../telemetry-data/2021-01-31/"

class Sectors:
    def __init__(self, file_path):
        self.polys = {}
        self.lines = {}
        with open(file_path) as json_file:
            data = json.load(json_file)
            for feature in data['features']:
                name = feature['properties']['name']
                otype = feature['geometry']['type']

                coord3d = feature['geometry']['coordinates']
                if otype.lower() == 'polygon':
                    coord2d = []
                    for c in coord3d[0]:
                        coord2d.append([c[0], c[1]])

                    self.polys[name] =  mpltPath.Path(coord2d)
                    print("Loaded polygon {}".format(name))
                if otype.lower() == 'linestring':
                    coord2d = []
                    for c in coord3d:
                        coord2d.append([c[0], c[1]])

                    self.lines[name] = coord2d
                    print("Loaded line {}".format(name))

        self.track = self.polys['Track']
        self.pre_finish = self.polys['PreFinish_Sector']
        self.post_finish = self.polys['PostFinish_Sector']
        self.opposite_marker = self.polys['Opposite_Marker']
        self.pitlane = self.polys['Pitlane']
        self.pitlane_gates = self.polys['Pitlane_Gates']
        self.pitlane_entry = self.polys['Pitlane_entry']
        self.pitlane_exit = self.polys['Pitlane_Exit']
        self.paddock = self.polys['Paddock']
        self.finish_line = self.lines['Finish_Line']

#        self.transitions = {}
#        self.transitions[track] = [pitlane_entry, pitlane_exit]
#        self.transitions[pitlane] = [pitlane_entry, pitlane_exit, pitlane_gates]
#        self.transitions[paddock] = [pitlane_gates]
#        self.transitions[pitlane_entry] = [track, pitlane]
#        self.transitions[pitlane_exit] = [track, pitlane]
#        self.transitions[pitlane_gates] = [paddock, pitlane]

sectors = Sectors("sectors.geojson")

# sys.exit(1)


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

                point = [lon, lat]

                pre_finish = sectors.pre_finish.contains_points([point])
                post_finish = sectors.post_finish.contains_points([point])

                if pre_finish or post_finish:
                    finish_center = np.array(sectors.finish_line[0])
                    finish_direction = np.array(sectors.finish_line[1])
                    moving_point = np.array(point)
                    cross = np.cross(finish_direction - finish_center, moving_point - finish_center)
                    sign = cross/np.abs(cross) 
                    dist = sign * norm(cross)/norm(finish_direction - finish_center)

                if pre_finish:
                    print("{}:{}:{}.{} pre_finish {}".format(hh, mm, ss, ms/100, dist))

                if post_finish:
                    print("{}:{}:{}.{} post_finish {}".format(hh, mm, ss, ms/100, dist))
