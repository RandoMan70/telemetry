#!/usr/bin/env python3

import argparse
import sys


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


def checksum_ubx(data):
    CK_A = 0
    CK_B = 0
    for b in data:
        CK_A = (CK_A + b) % 256
        CK_B = (CK_B + CK_A) % 256

    return bytes([CK_A, CK_B])


def retrieve_ubx(buffer: SlidingBuffer):
    start = buffer.lookup(2)

    if start != b'\xb5\x62':
        return None

    header = buffer.lookup(6)
    payload_length = (header[5] << 8) + header[4]
    frame_length = payload_length + 8

    frame = buffer.lookup(frame_length)
    if len(frame) != frame_length:
        print("Too short ubx frame", len(frame), frame_length, payload_length)
        return None

    frame_checksum = frame[-2:]
    payload_checksum = checksum_ubx(frame[2:-2])

    if frame_checksum != payload_checksum:
        print("Invalid ubx checksum", frame_checksum, payload_checksum)
        return None

    buffer.commit(frame_length)
    return frame


def retrieve_nmea(buffer: SlidingBuffer):
    start = buffer.lookup(1)

    if start != b'$':
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


def nmea_extract_timestamp(line):
    cmd = line[:6]
    if not cmd.startswith('$G') or not cmd.endswith('RMC'):
        return None, None

    parts=line.split(',')
    return parts[1], parts[9]


class OutputDir:
    def __init__(self, path: str):
        self.__path = path
        self.__current_suffix: Optional[str] = None
        self.__current_file: Optional[file] = None

    def get_file(self, suffix: str):
        assert suffix is not None
        if self.__current_suffix == suffix:
            return self.__current_file

        if self.__current_file is not None:
            self.__current_file.close()

        self.__current_suffix = suffix
        self.__current_file = open(self.__path + '/' + suffix, 'wb')

        return self.__current_file

def __main__():
    parser = argparse.ArgumentParser(description="Process ubx+nmea dumps")
    parser.add_argument("--infile", type=str, required=True)
    parser.add_argument("--outfile", type=str)
    parser.add_argument("--outdir", type=str)
    parser.add_argument("--verbose", type=bool)
    args = parser.parse_args()
    suffix = None

    with open(args.infile, 'rb') as f:
        buffer = SlidingBuffer(f)
        outfile = None
        outdir = None

        if args.outfile is not None:
            outfile = open(args.outfile, 'wb')

        if args.outdir is not None:
            outdir = OutputDir(args.outdir)

        while not buffer.eof():
            ubx_sentence = None

            nmea_sentence = retrieve_nmea(buffer)
            if nmea_sentence is not None:
                time, date = nmea_extract_timestamp(nmea_sentence)
                if time is not None and date is not None and time != '' and date != '':
                    suffix = '{}-{}-{}_{}-{:02d}'.format(date[4:6], date[2:4], date[:2], time[:2], int(int(time[2:4]) / 5) * 5)

                if outfile is not None:
                    outfile.write(nmea_sentence.encode())

                if outdir is not None and suffix is not None:
                    outdir.get_file(suffix).write(nmea_sentence.encode())

                if args.verbose:
                    print(nmea_sentence.strip())
                continue

            ubx_sentence = retrieve_ubx(buffer)
            if ubx_sentence is not None:
                if outfile is not None:
                    outfile.write(ubx_sentence)

                if outdir is not None and suffix is not None:
                    outdir.get_file(suffix).write(ubx_sentence)

                if args.verbose:
                    print("<UBX>")
                continue

            print("Sliding one byte forward for next try")
            buffer.commit(1)


__main__()
