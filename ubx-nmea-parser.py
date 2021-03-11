#!/usr/bin/env python3

import argparse


class SlidingBuffer:
    def __init__(self, file):
        self.__offset = 0
        self.__file = file
        self.__buffer = bytes()

    def offset(self):
        return self.__offset

    def lookup(self, length) -> bytes:
        while len(self.__buffer) < length:
            sector = self.__file.read(4096)
            if len(sector) == 0:
                break
            self.__buffer += sector

        return self.__buffer[:length]

    def commit(self, length):
        have_bytes = len(self.lookup(length))
        self.__offset += have_bytes
        self.__buffer = self.__buffer[have_bytes:]

    def eof(self):
        if len(self.__buffer) > 0:
            return False

        return len(self.lookup(1)) == 0


def checksum_nmea(line: str):
    cs = 0
    for c in line.encode():
        cs = cs ^ c

    return cs


def retrieve_nmea(buffer: SlidingBuffer):
    start = buffer.lookup(1)

    if start != b'$':
        print("Invalid nmea sync byte")
        return None

    frame = buffer.lookup(128)
    p = frame.find(b'\r\n')
    if p < 0:
        print("No CRLF in nearest 128 NMEA bytes")
        return None

    # Point it right behind full nmea sentence
    p += 2

    line = frame[:p].decode()
    checksum_str = line[-5:-2]
    if checksum_str[0] != '*':
        print("Invalid checksum:", checksum_str)
        return None

    try:
        checksum = int(checksum_str[1:], 16)
    except Exception as e:
        print("Can't convert checksum to integer:", checksum_str[1:], e)
        return None

    if checksum_nmea(line[1:-5]) != checksum:
        print("NMEA checksum does not match")
        return None

    buffer.commit(p)

    return line


def __main__():
    parser = argparse.ArgumentParser(description="Process ubx+nmea dumps")
    parser.add_argument("--infile", type=str, required=True)
    parser.add_argument("--outdir", type=str)
    args = parser.parse_args()

    with open(args.infile, 'rb') as f:
        buffer = SlidingBuffer(f)

        while not buffer.eof():
            nmea_sentence = None
            ubx_sentence = None

            if buffer.lookup(1) == b'$':
                nmea_sentence = retrieve_nmea(buffer)

            if nmea_sentence is not None or ubx_sentence is not None:
                continue

            print("Sliding one byte forward for next try")
            buffer.commit(1)


__main__()