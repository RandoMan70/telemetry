#!/usr/bin/env python3

import json
import re
import sys
from os import walk
import math
import numpy as np
from numpy.linalg import norm
import matplotlib.path as mpltPath
import matplotlib.lines as mpltLines

path = "../telemetry-data/2021-01-31/"

class Transformer:
    def __init__(self):
        self.origin = [None, None]
    def update_origin(self, c):
        if self.origin[0] == None or c[0] < self.origin[0]:
            self.origin[0] = c[0]

        if self.origin[1] == None or c[1] < self.origin[1]:
            self.origin[1] = c[1]


    def to_meters(self, point):
        point[0] = (point[0] - self.origin[0]) * 111320 * math.cos(math.radians(point[1]))
        point[1] = (point[1] - self.origin[1]) * 111319

transformer = Transformer()

class Sectors:

    def __init__(self, file_path):
        self.polys = {}
        self.lines = {}
        self.origin = [None, None]
        with open(file_path) as json_file:
            data = json.load(json_file)
            for feature in data['features']:
                name = feature['properties']['name']
                otype = feature['geometry']['type']

                coord3d = feature['geometry']['coordinates']

                if otype.lower() == 'polygon':
                    coord2d = []
                    for c in coord3d[0]:
                        transformer.update_origin(c)
                        coord2d.append([c[0], c[1]])

                    self.polys[name] =  coord2d
                    print("Loaded polygon {}".format(name))
                if otype.lower() == 'linestring':

                    coord2d = []
                    for c in coord3d:
                        transformer.update_origin(c)
                        coord2d.append([c[0], c[1]])

                    self.lines[name] = coord2d
                    print("Loaded line {}".format(name))

        for n, poly in self.polys.items():
            for point in poly:
                transformer.to_meters(point)

        for n, line in self.lines.items():
            for point in line:
                transformer.to_meters(point)

        # for n, poly in self.polys.items():
        #     print(n)
        #     for p in poly:
        #         print(p)

        # print(self.origin)
        # sys.exit(1)

        self.track = mpltPath.Path(self.polys['Track'])
        self.pre_finish = mpltPath.Path(self.polys['PreFinish_Sector'])
        self.post_finish = mpltPath.Path(self.polys['PostFinish_Sector'])
        self.opposite_marker = mpltPath.Path(self.polys['Opposite_Marker'])
        self.pitlane = mpltPath.Path(self.polys['Pitlane'])
        self.pitlane_gates = mpltPath.Path(self.polys['Pitlane_Gates'])
        self.pitlane_entry = mpltPath.Path(self.polys['Pitlane_entry'])
        self.pitlane_exit = mpltPath.Path(self.polys['Pitlane_Exit'])
        self.paddock = mpltPath.Path(self.polys['Paddock'])
        self.finish_line = self.lines['Finish_Line']

sectors = Sectors("sectors.geojson")

def solve(x1, y1, x2, y2):
    assert y1 <= 0
    assert y2 >= 0
    assert (y2 - y1) > 0
    assert x2 > x1

    return x1 - y1 * (x2 - x1) / (y2 - y1)

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

class StateMngr:
    def __init__(self):
        self.pre_time = None
        self.pre_distance = None
    
    def commit_pre(self, time, distance):
        self.pre_time = time
        self.pre_distance = distance
    
    def commit_post(self, time, distance):
        ret = None
        if self.pre_time != None:
            ret = solve(self.pre_time, self.pre_distance, time, distance)
        
        self.pre_time = None
        self.pre_distance = None
        return ret

class LapMngr():
    def __init__(self, maxtime = 300):
        self.time = None
        self.maxtime = maxtime

    def cross(self, time):
        if self.time == None :
            self.time = time
            return None
        
        if time - self.time > self.maxtime:
            self.time = time
            return None
        
        ret = time - self.time
        self.time = time
        return ret

def format_laptime(time):
    mmss = int(math.floor(time))
    frac = int(round(time % 1 * 100)) 
    mm = int(time / 60)
    ss = int(time % 60)
    return "{}:{:02d}.{:02d}".format(mm, ss, frac)

state_mngr = StateMngr()
lap_mngr = LapMngr()

rmc = re.compile("\$..RMC.([\d]{2})([\d]{2})([\d]{2})\.([\d]{2})\,A,([0-9]*)([0-9]{2}\.[0-9]*),(.),([0-9]*)([0-9]{2}\.[0-9]*),(.),([0-9\.]*),([0-9\.]*),([\d]{2})([\d]{2})([\d]{2})")

for filename in files(path):
    # print(filename)
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

                time = hh*3600+mm*60+ss+ms/1000

                speed=float(m.group(11)) * 1.852
                direction = None
                if m.group(12):
                    direction=float(m.group(12))

                point = [lon, lat]
                transformer.to_meters(point)

                pre_finish = sectors.pre_finish.contains_points([point])
                post_finish = sectors.post_finish.contains_points([point])

                if pre_finish or post_finish:
                    finish_center = np.array(sectors.finish_line[1])
                    finish_direction = np.array(sectors.finish_line[0])
                    moving_point = np.array(point)
                    cross = np.cross(finish_direction - finish_center, moving_point - finish_center)
                    sign = cross/np.abs(cross) 
                    dist = sign * norm(cross)/norm(finish_direction - finish_center)

                if pre_finish:
                    state_mngr.commit_pre(time, dist)
                
                if post_finish:
                    t = state_mngr.commit_post(time, dist)
                    if t != None:
                        laptime = lap_mngr.cross(t)
                        if laptime != None:
                            print("{}:{:02d}:{:02d} {}".format(hh+7, mm, ss, format_laptime(laptime)))
                        else:
                            print("----------")
