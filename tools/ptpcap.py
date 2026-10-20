#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Zachary Grimshaw
"""Decode USB PTP captures; --recover enables explicitly reported packet-boundary recovery.

No camera access. JSON exports omit DeviceInfo, object pixels, and upload bytes.
See captures/reproduction.md for public inputs, hashes, and reproduction commands.
"""
import argparse
import collections
from dataclasses import dataclass
import hashlib
import json
import struct
import sys

OPS = {0x1001: 'GetDeviceInfo', 0x1002: 'OpenSession', 0x1003: 'CloseSession',
       0x1007: 'GetObjectHandles', 0x1008: 'GetObjectInfo', 0x1009: 'GetObject',
       0x100B: 'DeleteObject', 0x1014: 'GetDevicePropDesc',
       0x1015: 'GetDevicePropValue', 0x1016: 'SetDevicePropValue',
       0x900C: 'SendObjectInfo', 0x900D: 'SendObject2'}
RESP = {0x2001: 'OK', 0x2002: 'GeneralError', 0x2005: 'OperationNotSupported',
        0x200A: 'DevicePropNotSupported', 0x2019: 'DeviceBusy',
        0x201B: 'InvalidDevicePropFormat', 0x201C: 'InvalidDevicePropValue'}
PRESET_RANGE = range(0xD18C, 0xD1A6)  # selector/name/23 bank fields + live Image Size
MAGICS = {b'\xd4\xc3\xb2\xa1': ('<', False), b'\xa1\xb2\xc3\xd4': ('>', False),
          b'\x4d\x3c\xb2\xa1': ('<', True), b'\xa1\xb2\x3c\x4d': ('>', True)}
MAX_CONTAINER = 200_000_000


class CaptureError(ValueError):
    pass


class CapturedBytes(bytes):
    def __new__(cls, data, truncated=False, stream=(0, 0)):
        obj = super().__new__(cls, data)
        obj.truncated = truncated
        obj.stream = stream
        return obj


def exact(f, size):
    data = f.read(size)
    if len(data) != size:
        raise CaptureError('truncated capture structure')
    return data


def read_pcap(path):
    with open(path, 'rb') as f:
        header = exact(f, 24)
        if header[:4] not in MAGICS:
            raise CaptureError('unknown pcap magic')
        endian, nano = MAGICS[header[:4]]
        linktype = struct.unpack_from(endian + 'I', header, 20)[0] & 0xffff
        while True:
            h = f.read(16)
            if not h:
                return
            if len(h) != 16:
                raise CaptureError('truncated pcap packet header')
            sec, frac, caplen, original = struct.unpack(endian + 'IIII', h)
            if caplen > 512_000_000 or caplen > original:
                raise CaptureError('invalid pcap packet length')
            yield sec * 1e6 + (frac / 1000 if nano else frac), linktype, CapturedBytes(exact(f, caplen), caplen < original)


def read_pcapng(path):
    with open(path, 'rb') as f:
        endian, interfaces, section = '<', [], -1
        while True:
            h = f.read(8)
            if not h:
                return
            if len(h) != 8:
                raise CaptureError('truncated pcapng block header')
            if h[:4] == b'\x0a\x0d\x0d\x0a':
                bom = exact(f, 4)
                if bom not in (b'\x4d\x3c\x2b\x1a', b'\x1a\x2b\x3c\x4d'):
                    raise CaptureError('invalid pcapng byte order')
                endian = '<' if bom[0] == 0x4d else '>'
                blen = struct.unpack_from(endian + 'I', h, 4)[0]
                if blen < 28 or blen % 4 or blen > 512_000_000:
                    raise CaptureError('invalid section block length')
                rest = bom + exact(f, blen - 12)
                interfaces = []
                section += 1
                btype = 0x0a0d0d0a
            else:
                btype, blen = struct.unpack(endian + 'II', h)
                if blen < 12 or blen % 4 or blen > 512_000_000:
                    raise CaptureError('invalid pcapng block length')
                rest = exact(f, blen - 8)
            if struct.unpack_from(endian + 'I', rest, len(rest)-4)[0] != blen:
                raise CaptureError('pcapng trailing block length differs')
            body = rest[:-4]
            if btype == 1:
                if len(body) < 8:
                    raise CaptureError('short interface block')
                linktype = struct.unpack_from(endian + 'H', body)[0]
                scale, offset, pos = 1e-6, 0, 8
                while pos + 4 <= len(body):
                    code, size = struct.unpack_from(endian + 'HH', body, pos)
                    pos += 4
                    if not code:
                        break
                    if pos + size > len(body):
                        raise CaptureError('truncated interface option')
                    if code == 9 and size == 1:
                        v = body[pos]
                        scale = 2.0 ** -(v & 127) if v & 128 else 10.0 ** -v
                    if code == 14 and size == 8:
                        offset = struct.unpack_from(endian + 'q', body, pos)[0]
                    pos += (size + 3) & ~3
                interfaces.append((linktype, scale, offset))
            elif btype == 6:
                if len(body) < 20:
                    raise CaptureError('short enhanced packet block')
                iface, hi, lo, caplen, original = struct.unpack_from(endian + 'IIIII', body)
                if iface >= len(interfaces) or caplen > original or caplen > len(body)-20:
                    raise CaptureError('invalid enhanced packet length/interface')
                linktype, scale, offset = interfaces[iface]
                yield (((hi << 32) | lo) * scale + offset) * 1e6, linktype, CapturedBytes(body[20:20+caplen], caplen < original, (section, iface))


def read_capture(path):
    with open(path, 'rb') as f:
        magic = f.read(4)
    if magic in MAGICS:
        return read_pcap(path)
    if magic == b'\x0a\x0d\x0d\x0a':
        return read_pcapng(path)
    raise CaptureError('input is neither pcap nor pcapng')


def bulk_frame(linktype, frame):
    """Return (device key, endpoint, direction, captured payload), or None.

    USBPcap/usbmon headers supply device and endpoint isolation. Payloads may be
    shorter than the transfer's declared length when capture packets were lost.
    """
    if linktype == 249:
        if len(frame) < 27:
            return None
        hlen = struct.unpack_from('<H', frame)[0]
        ep, transfer = frame[21], frame[22]
        dlen = struct.unpack_from('<I', frame, 23)[0]
        if transfer != 3 or not dlen or hlen < 27 or hlen > len(frame):
            return None
        bus, device = struct.unpack_from('<HH', frame, 17)
        return (linktype, *getattr(frame, 'stream', (0, 0)), bus, device), ep, ('IN' if ep & 128 else 'OUT'), CapturedBytes(frame[hlen:hlen+dlen], getattr(frame, 'truncated', False) or dlen > len(frame)-hlen)
    if linktype in (189, 220):
        hlen = 64 if linktype == 220 else 48
        if len(frame) < hlen or frame[9] != 3 or frame[15] != 0:
            return None  # xfer_type=bulk, flag_data=0 means captured data exists
        ep, device = frame[10], frame[11]
        bus = struct.unpack_from('<H', frame, 12)[0]
        dlen = struct.unpack_from('<I', frame, 36)[0]
        if not dlen:
            return None
        return (linktype, *getattr(frame, 'stream', (0, 0)), bus, device), ep, ('IN' if ep & 128 else 'OUT'), CapturedBytes(frame[hlen:hlen+dlen], getattr(frame, 'truncated', False) or dlen > len(frame)-hlen)
    return None


def bulk_payload(linktype, frame):
    item = bulk_frame(linktype, frame)
    return (item[2], item[3]) if item else None


def header(buf):
    if len(buf) < 12:
        return None
    size, kind, code, tid = struct.unpack_from('<IHHI', buf)
    if size < 12 or size > MAX_CONTAINER or kind not in (1, 2, 3, 4):
        return None
    if kind in (1, 3, 4) and (size > 32 or (size-12) % 4):
        return None
    if kind in (1, 2) and not (0x1000 <= code < 0x2000 or 0x9000 <= code < 0xa000):
        return None
    if kind == 3 and not (0x2000 <= code < 0x3000 or 0xa000 <= code < 0xb000):
        return None
    if kind == 4 and not (0x4000 <= code < 0x5000 or 0xc000 <= code < 0xd000):
        return None
    return size, kind, code, tid


@dataclass
class Container:
    ts: float
    device: tuple
    endpoint: int
    direction: str
    kind: int
    code: int
    tid: int
    payload: bytes
    complete: bool
    expected: int


def decode(path, recover=False, diagnostics=None):
    """Recovery is heuristic, opt-in, at USB packet boundaries only.

    A new response/data header must match an observed command on that device.
    New commands must be complete, correctly directed small containers. No scan
    for headers inside image bytes is performed. Every abandoned container is
    retained as incomplete and reported; it never becomes complete transaction data.
    """
    diagnostics = diagnostics if diagnostics is not None else []
    pending, commands, out, gaps = {}, {}, [], {}

    def emit(key, ts, buf, complete):
        h = header(buf)
        if h is None:
            diagnostics.append({'reason': 'incomplete_or_invalid_header', 'captured_bytes': len(buf)})
            return
        size, kind, code, tid = h
        device, ep, direction = key
        out.append(Container(ts, device, ep, direction, kind, code, tid, bytes(buf[12:]), complete, size-12))
        if kind == 1 and complete:
            commands[(device, tid)] = code
        if not complete:
            diagnostics.append({'reason': 'incomplete_container', 'tid': tid, 'kind': kind,
                                'code': f'0x{code:04X}', 'expected_bytes': size-12,
                                'captured_bytes': max(0, len(buf)-12)})

    for ts, lt, frame in read_capture(path):
        item = bulk_frame(lt, frame)
        if not item:
            continue
        device, ep, direction, buf = item
        key = (device, ep, direction)
        packet_truncated = getattr(buf, 'truncated', False)
        if (key in pending or key in gaps) and recover:
            oldh = header(pending[key][1]) if key in pending else gaps[key]
            h = header(buf)
            if h and oldh:
                size, kind, code, tid = h
                new_cmd = kind == 1 and direction == 'OUT' and len(buf) >= size and tid != oldh[3]
                matched = (device, tid) in commands
                new_resp = kind == 3 and direction == 'IN' and len(buf) >= size and matched
                new_data = kind == 2 and matched and commands[(device, tid)] == code and tid != oldh[3]
                if new_cmd or new_resp or new_data:
                    if key in pending:
                        oldts, old = pending.pop(key)
                        emit(key, oldts, old, False)
                    diagnostics.append({'reason': 'packet_boundary_resync', 'abandoned_tid': oldh[3],
                                        'next_tid': tid, 'next_kind': kind})
                    gaps.pop(key, None)
        if key in gaps:
            # A known missing span cannot be repaired by concatenating later bytes.
            continue
        while buf:
            if key in pending:
                oldts, acc = pending.pop(key)
            else:
                oldts, acc = ts, bytearray()
            if len(acc) < 12:
                take = min(12-len(acc), len(buf))
                acc.extend(buf[:take]); buf = buf[take:]
                if len(acc) < 12:
                    pending[key] = (oldts, acc)
                    break
            h = header(acc)
            if h is None:
                diagnostics.append({'reason': 'invalid_header_at_boundary', 'captured_bytes': len(acc)+len(buf)})
                break
            size = h[0]
            take = min(size-len(acc), len(buf))
            acc.extend(buf[:take]); buf = buf[take:]
            if len(acc) == size:
                emit(key, oldts, acc, True)
            else:
                pending[key] = (oldts, acc)
        if packet_truncated:
            diagnostics.append({'reason': 'known_packet_gap', 'direction': direction})
            if key in pending:
                oldts, old = pending.pop(key)
                oldh = header(old)
                emit(key, oldts, old, False)
                gaps[key] = oldh or (0, 0, 0, None)
            else:
                # Even if an earlier container completed, the following boundary is unknown.
                gaps[key] = (0, 0, 0, None)
    for key, (ts, acc) in pending.items():
        emit(key, ts, acc, False)
    return out


def containers(path, recover=False, diagnostics=None):
    return [(c.ts, c.direction, c.kind, c.code, c.tid, c.payload)
            for c in decode(path, recover, diagnostics) if c.complete]


def transactions(path, recover=False, diagnostics=None):
    """Pair by device and transaction instance; preserve repeated IDs across sessions."""
    tx, current, sessions = collections.OrderedDict(), {}, {}
    for c in decode(path, recover, diagnostics):
        identity = (c.device, c.tid)
        if c.kind == 1 and c.complete:
            key = c.tid if c.tid not in tx else f'{c.tid}#{len(tx)}'
            current[identity] = key
            if c.code == 0x1002:
                sessions[c.device] = sessions.get(c.device, 0) + 1
            tx[key] = {'device': list(c.device), 'session': sessions.get(c.device, 0),
                       'transaction_key': str(key), 'tid': c.tid, 'ts': c.ts, 'op': c.code,
                       'params': list(struct.unpack('<'+'I'*(len(c.payload)//4), c.payload)),
                       'out': None, 'in': None, 'in_partial': None, 'resp': None, 'resp_ts': None}
        elif identity in current:
            t = tx[current[identity]]
            if c.kind == 2 and c.code == t['op']:
                if c.complete:
                    t['out' if c.direction == 'OUT' else 'in'] = c.payload
                elif c.direction == 'IN':
                    t['in_partial'] = c.payload
            elif c.kind == 3 and c.complete and c.direction == 'IN':
                t['resp'], t['resp_ts'] = c.code, c.ts
    return tx


def profile_rows(tx):
    previous, rows = {}, []
    for t in tx.values():
        if t['op'] not in (0x1015, 0x1016) or t['params'][:1] != [0xd185]:
            continue
        data = t['out'] if t['op'] == 0x1016 else t['in']
        if data is None or len(data) < 0x1fd or (len(data)-0x1fd) % 4:
            continue
        cells = list(struct.unpack('<'+'i'*((len(data)-0x1fd)//4), data[0x1fd:]))
        stream = (tuple(t.get('device', [])), t.get('session', 0))
        prior = previous.get(stream)
        row = {'device': t.get('device', []), 'session': t.get('session', 0),
               'transaction_key': t.get('transaction_key', str(t['tid'])),
               'tid': t['tid'], 'direction': 'write' if t['op'] == 0x1016 else 'read',
               'bytes': len(data), 'num_params': struct.unpack_from('<H', data)[0],
               'cells': cells, 'response': t['resp']}
        if t['op'] == 0x1016:
            row['changes'] = [] if prior is None else [
                {'cell': i, 'before': prior[i] if i < len(prior) else None, 'after': val}
                for i, val in enumerate(cells) if i >= len(prior) or val != prior[i]]
            row['removed_cells'] = list(range(len(cells), len(prior or [])))
            previous[stream] = cells
        rows.append(row)
    return rows


def jpeg_metadata_envelope(data):
    """Keep only complete EXIF APP1 segments from a JPEG prefix, without pixels.

    Requires sequential markers from SOI; never scans through missing bytes.
    This proves APP1 availability, not pixel integrity or transfer completeness.
    """
    if not data.startswith(b'\xff\xd8'):
        return None
    pos, parts = 2, []
    while pos < len(data):
        if data[pos] != 0xff:
            break
        while pos < len(data) and data[pos] == 0xff:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]; pos += 1
        if marker in (0xda, 0xd9):
            break
        if marker in (0x01, *range(0xd0, 0xd8)):
            continue
        if pos+2 > len(data):
            break
        size = struct.unpack_from('>H', data, pos)[0]
        if size < 2 or pos+size > len(data):
            break
        segment = data[pos+2:pos+size]
        if marker == 0xe1 and segment.startswith(b'Exif\x00\x00'):
            parts.append(b'\xff\xe1'+data[pos:pos+size])
        pos += size
    return b'\xff\xd8'+b''.join(parts)+b'\xff\xd9' if parts else None


def metadata_rows(tx):
    from jpeg_recipe import parse_jpeg
    rows = []
    for t in tx.values():
        if t['op'] != 0x1009:
            continue
        complete = t['in'] is not None
        data = t['in'] if complete else t['in_partial']
        envelope = jpeg_metadata_envelope(data or b'')
        if envelope is None:
            continue
        try:
            result = parse_jpeg(envelope)
        except ValueError as exc:
            result = {'error': str(exc)}
        rows.append({'device': t.get('device', []), 'session': t.get('session', 0),
                     'transaction_key': t.get('transaction_key', str(t['tid'])), 'tid': t['tid'],
                     'data_container_complete': complete, 'operation_response': t['resp'],
                     'transfer_complete': complete and t['resp'] == 0x2001,
                     'pixels_validated': False, 'metadata': result})
    return rows


def hx(data, n=40):
    return data[:n].hex().upper() + ('…' if len(data)>n else '')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--recover', action='store_true', help='heuristic recovery at validated packet boundaries; losses reported')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--profiles', action='store_true', help='JSON profile cells and consecutive-write diffs')
    mode.add_argument('--metadata', action='store_true', help='JSON recipe metadata from complete EXIF segments; no pixels')
    mode.add_argument('--json', action='store_true', help='JSON transaction summaries; no payload bytes')
    args = parser.parse_args(argv)
    issues = []
    try:
        tx = transactions(args.capture, args.recover, issues)
        if not tx:
            raise CaptureError('no PTP transactions found')
        if args.profiles or args.metadata or args.json:
            with open(args.capture, 'rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            rows = profile_rows(tx) if args.profiles else metadata_rows(tx) if args.metadata else [
                {k: v for k, v in t.items() if k not in ('out', 'in', 'in_partial')} |
                {'out_bytes': len(t['out']) if t['out'] is not None else None,
                 'in_bytes': len(t['in']) if t['in'] is not None else None,
                 'partial_in_bytes': len(t['in_partial']) if t['in_partial'] is not None else None}
                for t in tx.values()]
            print(json.dumps({'capture_sha256': digest, 'recovery_enabled': args.recover,
                              'diagnostics': issues, 'rows': rows}, indent=2))
            return 0
        first, prev = next(iter(tx.values()))['ts'], None
        for t in tx.values():
            op, p = t['op'], t['params']
            prop = p[0] if p and op in (0x1014, 0x1015, 0x1016) else None
            if not args.all and not (prop in PRESET_RANGE or t['resp'] not in (None, 0x2001)):
                continue
            dt = (t['ts']-prev)/1000 if prev is not None else 0
            prev = t['ts']
            line = f"{(t['ts']-first)/1e6:9.3f}s +{dt:7.1f}ms tid={t['tid']:<5} {OPS.get(op,hex(op)):20}"
            if prop is not None:
                line += f' 0x{prop:04X}'
            for direction in ('out', 'in'):
                data = t[direction]
                if data is not None:
                    # Explicit allowlist excludes names/firmware/device strings and all objects.
                    safe = prop in range(0xd18e, 0xd1a6) and len(data) <= 40
                    line += f' {direction}={hx(data)}' if safe else f' {direction}=({len(data)} bytes, not shown)'
            response = t['resp']
            line += ' → ' + RESP.get(response, hex(response) if response is not None else 'no-resp')
            if t['resp_ts'] is not None:
                line += f" {(t['resp_ts']-t['ts'])/1000:.0f}ms"
            print(line)
        print('operations:', dict(collections.Counter(OPS.get(t['op'], hex(t['op'])) for t in tx.values())))
        print('recovery:', json.dumps(issues))
        return 0
    except (CaptureError, OSError, ValueError) as exc:
        print(f'ptpcap: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
