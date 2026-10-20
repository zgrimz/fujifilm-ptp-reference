#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
bankprobe.py — ask a Fujifilm body the bank-protocol questions that published sources leave open.

Talks plain PTP over USB (PyUSB + libusb) to a camera in USB RAW CONV./BACKUP RESTORE mode.
Every test prints what it wrote, what the camera answered, and what it read back, and logs the
same to a JSON file you can attach to a report (see CONTRIBUTING.md at
https://github.com/zgrimz/fujifilm-ptp-reference). Serial numbers are never printed or logged.

Requirements:  python3, `pip install pyusb`, and libusb (`brew install libusb` on macOS).
Camera:        USB connection setting = USB RAW CONV./BACKUP RESTORE; auto power off = OFF.
macOS:         another process may already hold the camera. Quit Image Capture, Photos and
               X RAW Studio first.

Before connecting your camera
  Connecting third-party software might void your camera's warranty; see Warranty in the README.
  Writing changes your saved settings. Back the bank up first (every write command here does, to
  backups/) and write only to a bank you can spare.

Commands
  info                         GetDeviceInfo summary and the bank count
  dump                         read every bank (name and 23 settings; live 0xD1A5 is separate); --out writes JSON
  backup   --bank N            save one bank to backups/
  restore  FILE --bank N       put a saved bank back: name first, conditional writes, grain 1
  sweep    --bank N            read the bank, wait while you change ONE menu item, read again, diff
  probe    --bank N P=V ...    write properties (hex code=value, e.g. D193=0 D193=-10), read back
  test     NAME ... --bank N   run the named checks (list with --list-tests)
  guided   --bank N --other-bank M [--set first|confirm]
                               a whole battery in order, read-only sweeps first, with a transcript file;
                               type s at any prompt to skip that test; --skip NAME... leaves tests out.
                               "confirm" is the second round: controls and the questions the first round opened
  selftest                     framing, string and restore-planner checks with no camera

In USB RAW CONV. mode the camera's menu is unavailable while the cable is in, so every menu step is
"unplug, change it, replug"; the prompts say so, and the tool reconnects, reopens the session,
requires confirmation of the same physical camera before recovering a read.
An uncertain write is never replayed automatically; inspect its backup and reconnect explicitly.

Read-only commands may write the selector; they restore its original value when possible.
Write tests require all 23 bank values and the name to be readable, save immutable backups, and
attempt cleanup in finally. Cleanup reports exact, semantic-only, mismatched or unavailable state.
Only explicit live tests back up and restore 0xD1A5. Camera-menu changes outside the snapshot
(e.g. ISO, HEIF, HDR) must be restored manually, including after an interruption.
The documented USB property path has no known bank-clear operation; camera-menu ERASE exists.
"""

import argparse
import copy
from contextlib import contextmanager
from functools import wraps
import datetime as _dt
import json
import os
import struct
import sys
import time

VENDOR_ID = 0x04CB

OP_GET_DEVICE_INFO = 0x1001
OP_OPEN_SESSION = 0x1002
OP_CLOSE_SESSION = 0x1003
OP_GET_PROP = 0x1015
OP_SET_PROP = 0x1016

RC = {
    0x2001: "OK",
    0x2002: "General Error",
    0x2003: "Session Not Open",
    0x2005: "Operation Not Supported",
    0x2006: "Parameter Not Supported",
    0x200A: "DeviceProp Not Supported",
    0x2015: "No Valid ObjectInfo",
    0x201C: "Invalid DeviceProp Value",
    0x201D: "Invalid Parameter",
    0x201E: "Session Already Open",
    0xA001: "vendor-specific",
}

BANK_SELECT = 0xD18C
BANK_NAME = 0xD18D
BANK_FIRST = 0xD18E
BANK_LAST = 0xD1A4
LIVE_IMAGE_SIZE = 0xD1A5
BANK_PROPS = list(range(BANK_FIRST, BANK_LAST + 1))

PROP_NAMES = {
    0xD18C: "Bank selector",
    0xD18D: "Bank name",
    0xD18E: "Image Size",
    0xD18F: "Image Quality",
    0xD190: "Dynamic Range",
    0xD191: "D-Range Priority",
    0xD192: "Film Simulation",
    0xD193: "Mono WC",
    0xD194: "Mono MG",
    0xD195: "Grain Effect",
    0xD196: "Color Chrome Effect",
    0xD197: "Color Chrome FX Blue",
    0xD198: "Smooth Skin Effect",
    0xD199: "White Balance",
    0xD19A: "WB shift R",
    0xD19B: "WB shift B",
    0xD19C: "Color temperature",
    0xD19D: "Highlight Tone",
    0xD19E: "Shadow Tone",
    0xD19F: "Color",
    0xD1A0: "Sharpness",
    0xD1A1: "High ISO NR",
    0xD1A2: "Clarity",
    0xD1A3: "Lens Modulation Optimizer",
    0xD1A4: "Color Space",
    0xD1A5: "0xD1A5 (X RAW Studio's live Image Size)",
}

# Shown as signed in printouts; stored and written as raw u16 throughout.
SIGNED = {0xD190, 0xD193, 0xD194, 0xD19A, 0xD19B, 0xD19D, 0xD19E, 0xD19F, 0xD1A0, 0xD1A2}

FILM_SIMS = {  # this record's table (rawji's values; X-T50 menu-confirmed, GFX100S, X-H2, fujicli)
    1: "PROVIA", 2: "Velvia", 3: "ASTIA", 4: "PRO Neg. Hi", 5: "PRO Neg. Std", 6: "Monochrome",
    7: "Monochrome + Ye", 8: "Monochrome + R", 9: "Monochrome + G", 10: "Sepia", 11: "Classic Chrome",
    12: "ACROS", 13: "ACROS + Ye", 14: "ACROS + R", 15: "ACROS + G", 16: "ETERNA", 17: "Classic Neg.",
    18: "ETERNA Bleach Bypass", 19: "Nostalgic Neg.", 20: "REALA ACE",
}
FILM_SIMS_FUJI_PTP_NOTES = {  # the disputed order in fuji-ptp-notes' unmarked table (GFX100RF)
    4: "Monochrome", 5: "Sepia", 6: "PRO Neg. Hi", 7: "PRO Neg. Std",
    8: "Monochrome + Ye", 9: "Monochrome + R", 10: "Monochrome + G",
}
MONO_WITH_TONING = {6, 7, 8, 9, 12, 13, 14, 15}
MONO_ALL = MONO_WITH_TONING | {10}

WB_KELVIN = 0x8007
GRAIN_OFF_VALUES = {1, 6, 7}


# ----------------------------------------------------------------------------------------------
# PTP framing
# ----------------------------------------------------------------------------------------------

def container(ctype, code, tid, payload=b""):
    return struct.pack("<IHHI", 12 + len(payload), ctype, code, tid) + payload


def params_payload(params):
    return b"".join(struct.pack("<I", p & 0xFFFFFFFF) for p in params)


def ptp_string(text):
    if not text:
        return b"\x00"
    units = text.encode("utf-16-le")
    count = len(units) // 2 + 1
    if count > 255:
        raise ValueError("PTP string too long")
    return bytes([count]) + units + b"\x00\x00"


def parse_ptp_string(buf, offset=0):
    if offset >= len(buf):
        raise ValueError("missing PTP string length")
    count = buf[offset]
    if count == 0:
        return "", offset + 1
    end = offset + 1 + 2 * count
    if end > len(buf):
        raise ValueError("truncated PTP string")
    raw = buf[offset + 1:end]
    if raw[-2:] != b"\x00\x00":
        raise ValueError("unterminated PTP string")
    return raw[:-2].decode("utf-16-le", errors="strict"), end


def parse_u16_array(buf, offset):
    (n,) = struct.unpack_from("<I", buf, offset)
    offset += 4
    vals = list(struct.unpack_from("<%dH" % n, buf, offset))
    return vals, offset + 2 * n


def parse_device_info(buf):
    off = 0
    std, vext_id, vext_ver = struct.unpack_from("<HIH", buf, off)
    off += 8
    vext_desc, off = parse_ptp_string(buf, off)
    (func_mode,) = struct.unpack_from("<H", buf, off)
    off += 2
    ops, off = parse_u16_array(buf, off)
    events, off = parse_u16_array(buf, off)
    props, off = parse_u16_array(buf, off)
    capture_fmts, off = parse_u16_array(buf, off)
    image_fmts, off = parse_u16_array(buf, off)
    manufacturer, off = parse_ptp_string(buf, off)
    model, off = parse_ptp_string(buf, off)
    version, off = parse_ptp_string(buf, off)
    # The serial number follows. It is deliberately not parsed or kept.
    return {
        "length": len(buf), "standard_version": std, "vendor_extension_id": vext_id,
        "vendor_extension_version": vext_ver, "vendor_extension_desc": vext_desc,
        "operations": ops, "events": events, "properties": props,
        "capture_formats": capture_fmts, "image_formats": image_fmts,
        "manufacturer": manufacturer, "model": model, "device_version": version,
    }


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


def show(code, value):
    if value is None:
        return "—"
    if code in SIGNED:
        return "0x%04X (%d)" % (value, s16(value))
    return "0x%04X (%u)" % (value, value)


def rc_name(rc):
    return "0x%04X %s" % (rc, RC.get(rc, "?"))


def same_meaning(code, wrote, read):
    if read is None:
        return False
    if code == 0xD195 and wrote in GRAIN_OFF_VALUES and read in GRAIN_OFF_VALUES:
        return True
    return wrote == read


# ----------------------------------------------------------------------------------------------
# Transport
# ----------------------------------------------------------------------------------------------

class PTPError(Exception):
    pass


class SkipTest(Exception):
    pass


class Camera:
    def __init__(self, timeout_ms=5000, log=None, verbose=False):
        self.timeout = timeout_ms
        self.log = log if log is not None else []
        self.verbose = verbose
        self.dev = self.intf = self.ep_in = self.ep_out = None
        self.tid = 0
        self.pending = b""
        self.info = None
        self.selected_bank = None
        self.experiment = None
        self.write_uncertain = False
        self.cleanup_failed = False
        self.string_bytes = {}

    # -- USB ------------------------------------------------------------------------------------

    def open(self):
        try:
            import usb.core
            import usb.util
        except ImportError:
            sys.exit("pyusb is not installed. Run: pip install pyusb   (and on macOS: brew install libusb)")
        self._usb = usb
        backend = None
        try:
            import usb.backend.libusb1 as libusb1
            backend = libusb1.get_backend()
            if backend is None:  # Homebrew's lib directory is not on the default dyld search path
                for cand in ("/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib",
                             "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib"):
                    if os.path.exists(cand):
                        backend = libusb1.get_backend(find_library=lambda name, c=cand: c)
                        if backend is not None:
                            break
        except ImportError:
            pass
        if backend is None:
            raise PTPError("pyusb found no libusb. Install it (brew install libusb) or point DYLD_LIBRARY_PATH at it.")
        found = None
        for dev in usb.core.find(find_all=True, idVendor=VENDOR_ID, backend=backend):
            for cfg in dev:
                for intf in cfg:
                    if intf.bInterfaceClass == 6:  # Still Image Capture (PTP)
                        found = (dev, cfg, intf)
        if found is None:
            raise PTPError("no Fujifilm body with a PTP interface found. Is it awake, plugged in, and in "
                           "USB RAW CONV./BACKUP RESTORE mode? (A card-reader mode exposes mass storage only.)")
        dev, cfg, intf = found
        try:
            if dev.get_active_configuration().bConfigurationValue != cfg.bConfigurationValue:
                dev.set_configuration(cfg.bConfigurationValue)
        except usb.core.USBError:
            try:
                dev.set_configuration(cfg.bConfigurationValue)
            except usb.core.USBError:
                pass
        try:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)
        except (NotImplementedError, usb.core.USBError):
            pass
        try:
            usb.util.claim_interface(dev, intf.bInterfaceNumber)
        except usb.core.USBError as e:
            raise PTPError("could not claim the PTP interface (%s). Another process probably holds the "
                           "camera: quit Image Capture, Photos and X RAW Studio, replug, and try again." % e)
        eps = intf.endpoints()
        bulk = usb.util.ENDPOINT_TYPE_BULK
        self.ep_in = next(e for e in eps if usb.util.endpoint_type(e.bmAttributes) == bulk
                          and usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        self.ep_out = next(e for e in eps if usb.util.endpoint_type(e.bmAttributes) == bulk
                           and usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.dev, self.intf = dev, intf
        self.tid = 0
        self.pending = b""
        if not hasattr(self, "selected_bank"):
            self.selected_bank = None

    def close(self, graceful=True):
        if self.dev is None:
            return
        if graceful:
            try:
                self.transact(OP_CLOSE_SESSION)
            except Exception:
                pass
        try:
            self._usb.util.release_interface(self.dev, self.intf.bInterfaceNumber)
            self._usb.util.dispose_resources(self.dev)
        except Exception:
            pass
        self.dev = None

    def reconnect(self, prompt_text, graceful=True):
        prior_info = dict(self.info or {})
        self.close(graceful)
        prompt(prompt_text + " Confirm that this is the SAME physical camera; never substitute another body.")
        deadline = time.time() + 600
        while True:
            try:
                self.open()
                self.start_session()
                break
            except PTPError:
                if time.time() > deadline:
                    raise PTPError("the camera did not come back within ten minutes")
                time.sleep(2.0)
        if any((self.info or {}).get(key) != prior_info.get(key) for key in ("model", "device_version")):
            self.write_uncertain = True
            raise PTPError("camera identity/firmware changed; refusing further writes")
        self.write_uncertain = False
        print("    camera back: %s fw %s" % (self.info["model"], self.info["device_version"]))

    # -- PTP ------------------------------------------------------------------------------------

    def _read_container(self):
        buf = self.pending
        while len(buf) < 12:
            buf += bytes(self.ep_in.read(65536, self.timeout))
        length, ctype, code, tid = struct.unpack_from("<IHHI", buf)
        if length < 12:
            raise PTPError("malformed container (length %d)" % length)
        while len(buf) < length:
            buf += bytes(self.ep_in.read(65536, self.timeout))
        self.pending = buf[length:]
        return ctype, code, tid, buf[12:length]

    def transact(self, code, params=(), data=None):
        """Never replay a possibly delivered write. Recover only read transactions."""
        if code == OP_SET_PROP and self.write_uncertain:
            raise PTPError("an earlier write has unknown delivery; no further writes in this session")
        if code == OP_SET_PROP and self.cleanup_failed and list(params) != [BANK_SELECT]:
            raise PTPError("earlier cleanup was not exact; further content writes are blocked")
        try:
            return self._transact_once(code, params, data)
        except KeyboardInterrupt:
            if code == OP_SET_PROP:
                self.write_uncertain = True
                self.log.append({"event": "write outcome unknown", "property": list(params),
                                 "error": "KeyboardInterrupt during transaction", "interrupted": True})
            raise
        except PTPError as e:
            if code == OP_SET_PROP:
                self.write_uncertain = True
                self.log.append({"event": "write outcome unknown", "property": list(params), "error": str(e)})
                raise PTPError("write possibly sent; outcome unknown; automatic replay and further writes blocked: %s" % e) from e
            if not getattr(e, "usb", False) or code != OP_GET_PROP:
                raise
            self._recover()
            return self._transact_once(code, params, data)

    def _recover(self):
        """Wait for the camera to come back, reopen the session and reselect the bank."""
        self.log.append({"event": "camera lost; waiting for it", "at": _dt.datetime.now().isoformat(timespec="seconds")})
        prior_info = dict(self.info or {})
        self.close(graceful=False)
        prompt("A read lost the USB connection. Confirm that the SAME physical camera is connected. Do not substitute another camera.")
        print("    camera off the bus (expected after a menu step). Waiting for it to come back...")
        deadline = time.time() + 600
        while True:
            try:
                self.open()
                self.start_session()
                break
            except PTPError:
                if time.time() > deadline:
                    raise PTPError("the camera did not come back within ten minutes")
                time.sleep(2.0)
        if any((self.info or {}).get(key) != prior_info.get(key) for key in ("model", "device_version")):
            self.write_uncertain = True
            raise PTPError("camera identity/firmware changed during recovery; refusing reselection")
        self.log.append({"event": "same physical camera confirmed by operator", "at": _dt.datetime.now().isoformat(timespec="seconds")})
        self.log.append({"event": "camera back", "at": _dt.datetime.now().isoformat(timespec="seconds")})
        print("    camera back: %s fw %s" % (self.info["model"], self.info["device_version"]))
        if self.selected_bank is not None:
            rc, _ = self.select_bank(self.selected_bank)
            if rc != 0x2001:
                raise PTPError("bank reselection refused after recovery")

    def _transact_once(self, code, params=(), data=None):
        tid = self.tid
        self.tid += 1
        entry = {"tid": tid, "op": "0x%04X" % code, "params": ["0x%X" % p for p in params]}
        if data is not None:
            entry["data_out"] = data.hex()
        try:
            self.ep_out.write(container(1, code, tid, params_payload(params)), self.timeout)
            if data is not None:
                self.ep_out.write(container(2, code, tid, data), self.timeout)
            ctype, rcode, rtid, payload = self._read_container()
            data_in = None
            if rtid != tid:
                raise PTPError("transaction ID mismatch")
            if ctype == 2:
                if rcode != code:
                    raise PTPError("data container operation mismatch")
                data_in = payload
                ctype, rcode, rtid, payload = self._read_container()
            if rtid != tid or len(payload) % 4:
                raise PTPError("malformed or mismatched response container")
            if ctype != 3:
                raise PTPError("expected a response container, got type %d" % ctype)
            if len(payload) > 20:
                raise PTPError("response container has more than five parameters")
            rparams = list(struct.unpack("<%dI" % (len(payload) // 4), payload[: len(payload) // 4 * 4]))
        except self._usb.core.USBError as e:
            entry["usb_error"] = str(e)
            self.log.append(entry)
            err = PTPError("USB error during 0x%04X: %s" % (code, e))
            err.usb = True
            err.errno = getattr(e, "errno", None)
            raise err
        entry["response"] = "0x%04X" % rcode
        if data_in is not None:
            entry["data_in"] = data_in.hex() if code != OP_GET_DEVICE_INFO else "(DeviceInfo, not logged: contains the serial number)"
        self.log.append(entry)
        if self.verbose:
            print("    [%d] 0x%04X %s -> %s%s" % (tid, code, " ".join("0x%X" % p for p in params), rc_name(rcode),
                                                  "" if data_in is None else " data=%s" % data_in[:16].hex()))
        return rcode, data_in, rparams

    def start_session(self):
        self.tid = 0
        rc, data, _ = self.transact(OP_GET_DEVICE_INFO)
        if rc != 0x2001 or data is None:
            raise PTPError("GetDeviceInfo failed: %s" % rc_name(rc))
        self.info = parse_device_info(data)
        self.tid = 0  # OpenSession carries transaction ID 0 (ISO 15740)
        rc, _, _ = self.transact(OP_OPEN_SESSION, [1])
        if rc == 0x201E:  # left open by an earlier run: close it so transaction IDs restart on both sides
            self.tid = 1
            self.transact(OP_CLOSE_SESSION)
            self.tid = 0
            rc, _, _ = self.transact(OP_OPEN_SESSION, [1])
        if rc != 0x2001:
            raise PTPError("OpenSession failed: %s" % rc_name(rc))
        self.tid = 1

    def get_u16(self, code):
        rc, data, _ = self.transact(OP_GET_PROP, [code])
        if rc != 0x2001 or data is None or len(data) != 2:
            return rc, None
        return rc, struct.unpack_from("<H", data)[0]

    def get_str(self, code):
        rc, data, _ = self.transact(OP_GET_PROP, [code])
        if rc != 0x2001 or not data:
            return rc, None
        try:
            text, end = parse_ptp_string(data)
        except (ValueError, UnicodeError, IndexError):
            return rc, None
        if end != len(data):
            return rc, None
        self.string_bytes[code] = bytes(data)
        return rc, text

    def set_u16(self, code, value):
        self._check_write_scope(code)
        if self.experiment is not None and code == 0xD195:
            original = self.experiment.banks[self.selected_bank]["props"][code]
            if original in (6, 7) and value != original:
                raise PTPError("remembered grain size cannot be restored exactly; this probe refuses to change it")
        rc, _, _ = self.transact(OP_SET_PROP, [code], struct.pack("<H", value & 0xFFFF))
        return rc

    def set_str(self, code, text):
        self._check_write_scope(code)
        rc, _, _ = self.transact(OP_SET_PROP, [code], ptp_string(text))
        if self.experiment is not None:
            read_rc, back = self.get_str(code)
            self.experiment.outcomes.append({"code": code, "wrote": text, "rc": rc, "read": back,
                                             "ok": rc == 0x2001 and read_rc == 0x2001 and back == text,
                                             "outcome": "refused" if rc != 0x2001 else "unavailable" if back is None else
                                                        "matched" if back == text else "mismatched"})
        return rc

    def _check_write_scope(self, code):
        exp = self.experiment
        if exp is None or code == BANK_SELECT:
            return
        if code == LIVE_IMAGE_SIZE:
            if exp.live is None:
                raise PTPError("live write requires an explicit live snapshot")
            return
        if code not in BANK_PROPS and code != BANK_NAME:
            raise PTPError("property is outside the bank experiment scope")
        if self.selected_bank not in exp.banks:
            raise PTPError("write target has no original snapshot")
        rc, selected = self.get_u16(BANK_SELECT)
        if rc != 0x2001 or selected != self.selected_bank:
            raise PTPError("selector changed or is unreadable; stopping before content write")
        exp.dirty = True

    # -- Banks ----------------------------------------------------------------------------------

    def select_bank(self, k):
        rc = self.set_u16(BANK_SELECT, k)
        if rc != 0x2001:
            return rc, None
        rc2, back = self.get_u16(BANK_SELECT)
        if rc2 != 0x2001 or back != k:
            raise PTPError("selected bank %d but the selector reads back %r — stopping before writing anywhere" % (k, back))
        self.selected_bank = k
        return rc, back

    def read_bank(self, k=None):
        """Read the selected bank, or bank k after selecting it. Returns {name, props{code: value|None}, refused{code: rc}}."""
        if k is not None:
            rc, _ = self.select_bank(k)
            if rc != 0x2001:
                raise PTPError("selecting bank %d refused: %s" % (k, rc_name(rc)))
        rc, name = self.get_str(BANK_NAME)
        props, refused = {}, {}
        for code in BANK_PROPS:
            rc, v = self.get_u16(code)
            props[code] = v
            if v is None:
                refused[code] = rc
        return {"bank": k, "name": name, "name_raw": self.string_bytes.get(BANK_NAME, b"").hex() if name is not None else None,
                "props": props, "refused": refused}

    def read_live(self):
        rc, value = self.get_u16(LIVE_IMAGE_SIZE)
        return {"namespace": "live", "props": {LIVE_IMAGE_SIZE: value}, "refused": {} if value is not None else {LIVE_IMAGE_SIZE: rc}}

    def write_verify(self, code, value, label=""):
        rc = self.set_u16(code, value)
        _, back = self.get_u16(code)
        row = {"code": code, "wrote": value, "rc": rc, "read": back,
               "ok": rc == 0x2001 and same_meaning(code, value, back)}
        row["outcome"] = ("refused" if rc != 0x2001 else "unavailable" if back is None else
                          "matched" if value == back else "semantic-only" if row["ok"] else "mismatched")
        if self.experiment is not None:
            self.experiment.outcomes.append(dict(row))
        tag = row["outcome"]
        norm = "" if back is None or same_meaning(code, value, back) else "  (read back differs: normalised?)"
        print("    0x%04X %-22s <- %-14s %-9s %s  reads %s%s" % (
            code, PROP_NAMES.get(code, ""), show(code, value), tag, rc_name(rc), show(code, back), norm))
        return row

    def bank_count(self, limit=10):
        with preserve_selector(self) as original:
            n = 0
            for k in range(1, limit + 1):
                rc, _ = self.select_bank(k)
                if rc != 0x2001:
                    break
                n = k
            return n, original


# ----------------------------------------------------------------------------------------------
# Backups and restore
# ----------------------------------------------------------------------------------------------

def backup_path(cam, k):
    os.makedirs("backups", exist_ok=True)
    model = (cam.info or {}).get("model", "camera").replace(" ", "_").replace("/", "-")
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return os.path.join("backups", "bankprobe-%s-C%d-%s.json" % (model, k, ts))


def bank_to_json(cam, bank):
    return {
        "schema_version": 2, "namespace": "bank",
        "model": (cam.info or {}).get("model"), "firmware": (cam.info or {}).get("device_version"),
        "bank": bank["bank"], "taken": _dt.datetime.now().isoformat(timespec="seconds"),
        "name": bank["name"], "name_raw": bank.get("name_raw", ptp_string(bank["name"]).hex() if bank["name"] is not None else None),
        "props": {"0x%04X" % c: (None if v is None else "0x%04X" % v) for c, v in bank["props"].items()},
        "refused": {"0x%04X" % c: "0x%04X" % rc for c, rc in bank["refused"].items()},
    }


def json_to_bank(d):
    if not isinstance(d, dict) or not isinstance(d.get("props"), dict):
        raise PTPError("bank snapshot must be an object with a property object")
    if d.get("schema_version") != 2 or d.get("namespace") != "bank":
        raise PTPError("only version-2 bank snapshots are restorable; legacy/live-containing snapshots need explicit migration")
    if set(d["props"]) != {"0x%04X" % c for c in BANK_PROPS}:
        raise PTPError("snapshot property keys must be the canonical 23 bank codes")
    if any(v is not None and (not isinstance(v, str) or not v.startswith("0x") or len(v) != 6)
           for v in d["props"].values()):
        raise PTPError("snapshot values must be raw four-digit hex u16 strings")
    try:
        props = {int(c, 16): (None if v is None else int(v, 16)) for c, v in d["props"].items()}
        bank = {"bank": d["bank"], "name": d["name"], "name_raw": d.get("name_raw"), "props": props, "refused": {}}
    except (KeyError, TypeError, ValueError) as e:
        raise PTPError("malformed bank snapshot") from e
    validate_snapshot(bank)
    return bank


def validate_snapshot(bank):
    """Conservative preflight: every bank field is required because restore dependencies interact."""
    if type(bank.get("bank")) is not int or not 1 <= bank["bank"] <= 255:
        raise PTPError("invalid bank number")
    if not isinstance(bank.get("name"), str):
        raise PTPError("original bank name unavailable; occupancy is unknown; no content writes")
    try:
        ptp_string(bank["name"])
    except (ValueError, UnicodeError) as e:
        raise PTPError("original name cannot be re-encoded") from e
    if bank.get("name_raw") is not None:
        try:
            raw = bytes.fromhex(bank["name_raw"])
            name, end = parse_ptp_string(raw)
            if name != bank["name"] or end != len(raw):
                raise ValueError("name/raw mismatch")
        except (ValueError, UnicodeError, TypeError) as e:
            raise PTPError("invalid original name bytes") from e
    props = bank.get("props", {})
    if set(props) != set(BANK_PROPS):
        raise PTPError("snapshot must contain exactly the 23 bank properties; live values are separate")
    missing = [c for c in BANK_PROPS if type(props[c]) is not int or not 0 <= props[c] <= 0xFFFF]
    if missing:
        raise PTPError("required originals unavailable/invalid (%s); occupancy is unknown; no content writes" %
                       ", ".join("0x%04X" % c for c in missing))


def save_backup(cam, bank):
    path = backup_path(cam, bank["bank"])
    with open(path, "w") as f:
        json.dump(bank_to_json(cam, bank), f, indent=2)
    print("  backup written: %s" % path)
    return path


def restore_plan(props):
    """Order and conditions for writing a saved bank back. Pure; returns [(code, value, note)]."""
    sim = props.get(0xD192)
    wb = props.get(0xD199)
    prio = props.get(0xD191)
    plan = []

    def add(code, note=""):
        v = props.get(code)
        if v is None:
            return
        if code in (0xD193, 0xD194) and sim not in MONO_WITH_TONING:
            plan.append((code, v, "skip: inactive on this film simulation"))
            return
        if code == 0xD19C and wb != WB_KELVIN:
            plan.append((code, v, "skip: white balance is not Kelvin"))
            return
        if code == 0xD19F and sim in MONO_ALL:
            plan.append((code, v, "skip: refused on monochrome simulations"))
            return
        if code == 0xD195 and v in (6, 7):
            plan.append((code, 1, "grain Off written as 1; the remembered size cannot be restored"))
            return
        plan.append((code, v, note))

    ascending = [c for c in BANK_PROPS if c not in (0xD190, 0xD191, 0xD199, 0xD19A, 0xD19B, 0xD19C, 0xD19D, 0xD19E)]
    # Image Size, Image Quality first; the D-Range Priority order depends on direction.
    add(0xD18E)
    add(0xD18F)
    if prio == 0:
        add(0xD191, "priority off before Dynamic Range")
        add(0xD190)
    for code in ascending:
        if code in (0xD18E, 0xD18F):
            continue
        if code == 0xD19F:
            # keep WB group in X RAW Studio's order: mode, Kelvin, shifts; tones come before Color.
            add(0xD199)
            add(0xD19C)
            add(0xD19A)
            add(0xD19B)
            if prio != 0:
                add(0xD190, "written while the priority is still off")
            add(0xD19D)
            add(0xD19E)
        add(code)
    if prio != 0 and prio is not None:
        add(0xD191, "priority last, after Dynamic Range and the tones")
    return plan


def restore_name(cam, saved):
    raw = saved.get("name_raw")
    if raw is None:
        return cam.set_str(BANK_NAME, saved["name"])
    cam._check_write_scope(BANK_NAME)
    return cam.transact(OP_SET_PROP, [BANK_NAME], bytes.fromhex(raw))[0]


def restore_bank(cam, saved, select=True):
    """Always reselect the snapshot target; verify final state, including skipped/inactive fields.

    The select parameter is retained for callers but cannot bypass target verification.
    A matched final read is byte agreement, not proof of power-cycle persistence.
    """
    validate_snapshot(saved)
    k = saved["bank"]
    print("  restoring bank C%d (%r)" % (k, saved["name"]))
    rc, _ = cam.select_bank(k)
    if rc != 0x2001:
        raise PTPError("restore target selection refused: %s" % rc_name(rc))
    current = cam.read_bank(k)
    rows = []
    # Avoid rewriting unchanged grain Off values (6/7 carry remembered size).
    changed = {c for c in BANK_PROPS if current["props"].get(c) != saved["props"][c]}
    name_changed = current["name"] != saved["name"] or (saved.get("name_raw") is not None and current.get("name_raw") != saved["name_raw"])
    if changed or name_changed:
        rc = restore_name(cam, saved)
        rows.append({"code": BANK_NAME, "rc": rc})
        # DR/tone writes need the CURRENT priority off, even when the saved priority is on.
        needs_dr = bool(changed & {0xD190, 0xD191, 0xD19D, 0xD19E})
        if needs_dr and current["props"].get(0xD191) != 0:
            row = cam.write_verify(0xD191, 0)
            rows.append(row)
            if not row["ok"]:
                raise PTPError("cannot verify priority off; dependent restore writes stopped")
            changed.add(0xD191)
        for code, value, note in restore_plan(saved["props"]):
            if code not in changed:
                continue
            if note.startswith("skip"):
                print("    0x%04X %s; final state will be checked" % (code, note))
                continue
            rows.append(cam.write_verify(code, value))
            if note:
                print("        %s" % note)
        rc = restore_name(cam, saved)
        rows.append({"code": BANK_NAME, "rc": rc})
    final = cam.read_bank(k)
    checks = []
    for code in [BANK_NAME] + BANK_PROPS:
        original = saved["name"] if code == BANK_NAME else saved["props"][code]
        actual = final["name"] if code == BANK_NAME else final["props"].get(code)
        status = ("unavailable" if actual is None else "exact" if actual == original else
                  "semantic-only" if code != BANK_NAME and same_meaning(code, original, actual) else "mismatched")
        if code == BANK_NAME and status == "exact" and saved.get("name_raw") is not None and final.get("name_raw") != saved["name_raw"]:
            status = "semantic-only"
        checks.append({"code": code, "original": original, "read": actual, "status": status})
    exact = all(c["status"] == "exact" for c in checks)
    result = {"bank": k, "exact": exact, "checks": checks, "writes": rows,
              "persistence": "not tested"}
    cam.log.append({"event": "bank restore verification", **result})
    print("  restore: %s; power-cycle persistence not tested" %
          ("all 24 name/settings fields exactly match the snapshot" if exact else
           "; ".join("0x%04X %s" % (c["code"], c["status"]) for c in checks if c["status"] != "exact")))
    return result


@contextmanager
def preserve_selector(cam):
    rc, original = cam.get_u16(BANK_SELECT)
    if rc != 0x2001 or original is None:
        raise PTPError("original selector unavailable; no selection/content writes")
    try:
        yield original
    finally:
        active_error = sys.exc_info()[0] is not None
        try:
            rc, back = cam.select_bank(original)
            if rc != 0x2001 or back != original:
                raise PTPError("selector restoration refused or mismatched")
            cam.log.append({"event": "selector restored", "value": original})
        except (PTPError, KeyboardInterrupt) as e:
            cam.cleanup_failed = True
            cam.log.append({"event": "selector restoration unavailable", "original": original, "error": str(e)})
            print("  ! selector restoration unavailable: %s" % e)
            # Preserve an active exception, but fail a nominally successful operation.
            if not active_error:
                raise


class BankExperiment:
    """Immutable bank originals plus an optional explicitly scoped live original.

    Menu-only state is outside this snapshot. Refused/unknown originals fail closed.
    Finally cleanup is best effort; unknown delivery blocks all subsequent writes.
    """
    def __init__(self, cam, banks, live=False, keep_on_success=False):
        self.cam = cam
        self.bank_numbers = list(dict.fromkeys(banks))
        self.capture_live = live
        self.keep_on_success = keep_on_success
        self.banks = {}
        self.live = None
        self.dirty = False
        self.outcomes = []
        self.cleanup = []

    def __enter__(self):
        cam = self.cam
        if cam.cleanup_failed or cam.write_uncertain:
            raise PTPError("previous cleanup/delivery is unresolved; no further write experiments in this session")
        if cam.experiment is not None:
            raise PTPError("nested bank experiments are not supported")
        # Complete all reads and validation before enabling content writes.
        for k in self.bank_numbers:
            bank = cam.read_bank(k)
            validate_snapshot(bank)
            self.banks[k] = copy.deepcopy(bank)
        if self.capture_live:
            self.live = copy.deepcopy(cam.read_live())
            if self.live["props"][LIVE_IMAGE_SIZE] is None:
                raise PTPError("live Image Size original unavailable; explicit live test refused")
        for bank in self.banks.values():
            save_backup(cam, bank)
        if self.live is not None:
            path = backup_path(cam, self.bank_numbers[0]).replace(".json", "-live.json")
            with open(path, "w") as f:
                json.dump({"schema_version": 2, "namespace": "live", "props":
                           {"0xD1A5": "0x%04X" % self.live["props"][LIVE_IMAGE_SIZE]},
                           "model": (cam.info or {}).get("model"),
                           "firmware": (cam.info or {}).get("device_version")}, f, indent=2)
            print("  explicit live backup written: %s" % path)
        rc, _ = cam.select_bank(self.bank_numbers[0])
        if rc != 0x2001:
            raise PTPError("experiment target selection refused")
        cam.experiment = self
        return self

    def __exit__(self, exc_type, exc, tb):
        cam = self.cam
        cleanup_required = not (self.keep_on_success and exc_type is None)
        cleanup_finished = False
        cleanup_interrupt = None
        try:
            if not cleanup_required:
                print("  retaining successful requested changes; pre-operation backups were saved")
                return False
            for saved in self.banks.values():
                try:
                    result = restore_bank(cam, copy.deepcopy(saved))
                    self.cleanup.append(result)
                except (PTPError, KeyboardInterrupt) as e:
                    if isinstance(e, KeyboardInterrupt):
                        cleanup_interrupt = e
                    result = {"bank": saved["bank"], "exact": False, "status": "unavailable", "error": str(e)}
                    self.cleanup.append(result)
                    cam.log.append({"event": "bank restore unavailable", **result})
                    print("  ! cleanup for C%d unavailable: %s; immutable backup retained" % (saved["bank"], e))
            if self.live is not None:
                try:
                    original = self.live["props"][LIVE_IMAGE_SIZE]
                    _, current = cam.get_u16(LIVE_IMAGE_SIZE)
                    if current != original:
                        cam.write_verify(LIVE_IMAGE_SIZE, original)
                    _, final = cam.get_u16(LIVE_IMAGE_SIZE)
                    status = "exact" if final == original else "unavailable" if final is None else "mismatched"
                    self.cleanup.append({"namespace": "live", "exact": status == "exact", "status": status})
                    cam.log.append({"event": "live restore verification", "status": status, "original": original, "read": final})
                    print("  explicit live restore: %s" % status)
                except (PTPError, KeyboardInterrupt) as e:
                    if isinstance(e, KeyboardInterrupt):
                        cleanup_interrupt = e
                    self.cleanup.append({"namespace": "live", "exact": False, "status": "unavailable", "error": str(e)})
                    print("  ! explicit live restore unavailable: %s" % e)
            cleanup_finished = True
        finally:
            cam.experiment = None
            if cleanup_required and (not cleanup_finished or any(not r["exact"] for r in self.cleanup)):
                cam.cleanup_failed = True
                cam.log.append({"event": "further write experiments blocked", "reason": "cleanup not exact"})
        if exc_type is None and cleanup_interrupt is not None:
            raise cleanup_interrupt
        if exc_type is None and any(not r["exact"] for r in self.cleanup):
            raise PTPError("cleanup not exact; inspect restoration report and saved originals")
        return False


# ----------------------------------------------------------------------------------------------
# Helpers for tests
# ----------------------------------------------------------------------------------------------

def prompt(text):
    print()
    print("  >> " + text)
    try:
        answer = input("     ... press Enter when done (or s + Enter to skip this test): ")
    except EOFError:
        raise PTPError("no terminal to wait on; run this interactively")
    if answer.strip().lower() == "s":
        raise SkipTest()


def menu_prompt(text):
    """A step that needs the camera's menu. In USB RAW CONV. mode the menu is unavailable while the
    cable is in, so every such step is an unplug and a replug; the next command then reconnects."""
    prompt("UNPLUG the USB cable. On the camera: " + text + " Then PLUG the cable back in, wait for the camera's USB screen, and press Enter.")


def ask(text):
    print()
    print("  ?? " + text)
    try:
        return input("     ... type your answer and press Enter: ").strip()
    except EOFError:
        raise PTPError("no terminal to wait on; run this interactively")


def print_bank(bank, title=None):
    if title:
        print("  " + title)
    print("    name: %r" % bank["name"])
    for code in BANK_PROPS:
        v = bank["props"][code]
        extra = ""
        if code == 0xD192 and v in FILM_SIMS:
            extra = "  " + FILM_SIMS[v]
        if v is None:
            extra = "  refused %s" % rc_name(bank["refused"][code])
        print("    0x%04X %-22s %s%s" % (code, PROP_NAMES.get(code, ""), show(code, v), extra))


def diff_banks(before, after):
    changed = []
    if before["name"] != after["name"]:
        changed.append((BANK_NAME, before["name"], after["name"]))
    for code in BANK_PROPS:
        if before["props"][code] != after["props"][code]:
            changed.append((code, before["props"][code], after["props"][code]))
    return changed


def print_diff(changed):
    if not changed:
        print("    no property changed")
    for code, a, b in changed:
        if code == BANK_NAME:
            print("    0xD18D name: %r -> %r" % (a, b))
        else:
            print("    0x%04X %-22s %s -> %s" % (code, PROP_NAMES.get(code, ""), show(code, a), show(code, b)))


class Tee:
    """Copies everything printed to a transcript file as well."""
    def __init__(self, path):
        self.stdout = sys.stdout
        self.file = open(path, "a")

    def write(self, text):
        self.stdout.write(text)
        self.file.write(text)
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()


class Report:
    def __init__(self):
        self.findings = []
        self.context = {}

    def add(self, test, verdict, detail=None):
        def missing(value):
            if isinstance(value, dict):
                return any(v is None or missing(v) for k, v in value.items() if k not in {"expected", "unverified_interpretation"})
            if isinstance(value, (tuple, list)):
                return any(v is None or missing(v) for v in value)
            return False
        interpretation = None
        if detail is not None and missing(detail):
            interpretation, verdict = verdict, "inconclusive: required observations are unavailable; see raw results"
        if self.context.get("auto_update") == "unknown":
            verdict += "; AUTO UPDATE unknown, persistence interpretation limited"
        self.findings.append({"test": test, "verdict": verdict, "detail": detail,
                              "context": dict(self.context), "unverified_interpretation": interpretation})
        print("  => %s" % verdict)


def need_bank(args):
    if args.bank is None:
        sys.exit("this needs --bank N (a bank you can spare; it is backed up first and restored afterwards)")
    if not 1 <= args.bank <= 255:
        raise PTPError("bank must be in 1..255")
    return args.bank


# ----------------------------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------------------------

def test_filmsim(cam, args, rep):
    """Read-only. Menu sweep of the disputed film simulation values."""
    k = need_bank(args)
    steps = [("PRO Neg. Hi", 4), ("PRO Neg. Std", 5), ("MONOCHROME", 6), ("MONOCHROME + Ye", 7),
             ("SEPIA", 10), ("ACROS", 12), ("ACROS + Ye", 13), ("ACROS + R", 14), ("ACROS + G", 15)]
    print("  Settles: fuji-ptp-notes' order for 4–10, and fujifilm-ptp-recipes' 13/14 (errata).")
    print("  For each step, set bank C%d's FILM SIMULATION in the camera's saved settings "
          "(EDIT/SAVE CUSTOM SETTING, or with AUTO UPDATE CUSTOM SETTING on) and save." % k)
    before = cam.read_bank(k)
    results = []
    for label, expected in steps:
        menu_prompt("set C%d's FILM SIMULATION to %s and save it." % (k, label))
        after = cam.read_bank(k)
        changed = diff_banks(before, after)
        v = after["props"][0xD192]
        other = [c for c, _, _ in changed if c != 0xD192]
        verdict = "matches this record" if v == expected else "DIFFERS from this record (expected 0x%02X)" % expected
        alt = ""
        if FILM_SIMS_FUJI_PTP_NOTES.get(v, "").lower() == label.lower():
            alt = "; matches fuji-ptp-notes' order instead"
        print("    %-16s 0xD192 = %s  %s%s%s" % (label, show(0xD192, v), verdict, alt,
                                                 "  (other properties moved too: %s)" % ", ".join("0x%04X" % c for c in other) if other else ""))
        results.append({"menu": label, "value": v, "expected": expected, "others_changed": other})
        before = after
    ok = all(r["value"] == r["expected"] for r in results)
    rep.add("filmsim", "every value matches this record's table" if ok else "at least one value differs; see rows", results)


def test_d1a3(cam, args, rep):
    """Read-only. Which property moves with LMO, Long Exposure NR and Color Space."""
    k = need_bank(args)
    print("  Settles: whether 0xD1A3 is Long Exposure NR (FilmKit, grawji) or Lens Modulation Optimizer (libfuji, fujicli, both peers), "
          "and the 0xD1A3/0xD1A4 value mappings.")
    before = cam.read_bank(k)
    print_bank(before, "bank C%d now:" % k)
    items = ["LENS MODULATION OPTIMIZER (toggle it, and note whether it now shows ON or OFF)",
             "LONG EXPOSURE NR (toggle it, and note ON or OFF)",
             "COLOR SPACE (switch it, and note sRGB or Adobe RGB)", "the same item back to where it was"]
    results = []
    for item in items:
        menu_prompt("in C%d's saved settings change ONLY %s, and save." % (k, item))
        after = cam.read_bank(k)
        changed = diff_banks(before, after)
        print_diff(changed)
        results.append({"menu": item, "changed": [("0x%04X" % c, a, b) for c, a, b in changed]})
        before = after
    rep.add("d1a3", "see which property moved with each menu item above", results)


def test_dr_placeholder(cam, args, rep):
    """Read-only. Compare DR readback through a priority Off/On/Off menu sequence."""
    k = need_bank(args)
    print("  Examines fujifilm-ptp-recipes' placeholder interpretation of 0xFFFF (errata, DR Auto); "
          "readback alone may not distinguish masking from a stored-setting change.")
    menu_prompt("set C%d's saved settings to ISO 500 or higher, DYNAMIC RANGE = 100%%, D RANGE PRIORITY = OFF." % k)
    b0 = cam.read_bank(k)
    print("    0xD190 = %s   0xD191 = %s" % (show(0xD190, b0["props"][0xD190]), show(0xD191, b0["props"][0xD191])))
    if b0["props"][0xD190] != 100 or b0["props"][0xD191] != 0:
        raise PTPError("precondition not met: this trial requires readable DR100 with priority off")
    menu_prompt("set C%d's D RANGE PRIORITY to STRONG (or AUTO) and save." % k)
    b1 = cam.read_bank(k)
    print_diff(diff_banks(b0, b1))
    v = b1["props"][0xD190]
    menu_prompt("set C%d's D RANGE PRIORITY back to OFF and save." % k)
    b2 = cam.read_bank(k)
    print_diff(diff_banks(b1, b2))
    priority_on = b1["props"][0xD191]
    priority_off_again = b2["props"][0xD191]
    restored_dr = b2["props"][0xD190]
    if priority_on not in (1, 2, 0x8000) or priority_off_again != 0:
        verdict = "inconclusive: priority On then Off was not confirmed by both readbacks"
    elif v is None or restored_dr is None:
        verdict = "inconclusive: required DR readbacks are unavailable"
    elif v == 0xFFFF and restored_dr == 100:
        verdict = ("0xD190 read DR100 -> 0xFFFF -> DR100 with priority Off -> On -> Off; "
                   "consistent with a temporary placeholder, but readback alone does not prove masking")
    elif v == 0xFFFF:
        verdict = ("inconclusive: 0xD190 read 0xFFFF with priority on but did not return to DR100 after Off; "
                   "a stored-setting change is still possible")
    elif v == 100 and restored_dr == 100:
        verdict = ("0xD190 stayed at DR100 through confirmed priority Off -> On -> Off; "
                   "no 0xFFFF placeholder observed in this trial")
    else:
        verdict = "inconclusive: DR changed during the Off/On/Off sequence; see raw readbacks"
    rep.add("dr-placeholder", verdict, {"off": show(0xD190, b0["props"][0xD190]), "on": show(0xD190, v),
                                        "off_again": show(0xD190, restored_dr),
                                        "readbacks": {
                                            label: {"0xD190": bank["props"][0xD190],
                                                    "0xD191": bank["props"][0xD191]}
                                            for label, bank in (("off", b0), ("on", b1), ("off_again", b2))
                                        }})


def read_bank_and_live(cam, k):
    bank = cam.read_bank(k)
    bank["live"] = cam.read_live()
    return bank


def test_d1a5(cam, args, rep):
    """Read-only. Does 0xD1A5 follow the bank select?"""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("d1a5 needs --other-bank M as well: two banks whose Image Size differs")
    print("  Measures this body's 0xD1A5 readback when bank selection changes; X RAW Studio's live-write path is established.")
    menu_prompt("set C%d's IMAGE SIZE to L 1:1 and C%d's to L 3:2 in their saved settings." % (k, j))
    a = read_bank_and_live(cam, k)
    b = read_bank_and_live(cam, j)
    _, no_select = cam.get_u16(LIVE_IMAGE_SIZE)
    print("    C%d: 0xD18E = %s  0xD1A5 = %s" % (k, show(0xD18E, a["props"][0xD18E]), show(0xD1A5, a["live"]["props"][LIVE_IMAGE_SIZE])))
    print("    C%d: 0xD18E = %s  0xD1A5 = %s" % (j, show(0xD18E, b["props"][0xD18E]), show(0xD1A5, b["live"]["props"][LIVE_IMAGE_SIZE])))
    print("    0xD1A5 read with C%d still selected: %s" % (j, show(0xD1A5, no_select)))
    if a["props"][0xD18E] == b["props"][0xD18E]:
        verdict = "inconclusive: both banks hold the same Image Size (%s)" % show(0xD18E, a["props"][0xD18E])
    elif a["live"]["props"][LIVE_IMAGE_SIZE] != b["live"]["props"][LIVE_IMAGE_SIZE]:
        verdict = "0xD1A5 readback changed with bank selection in this trial; this does not reclassify its established live-write path"
    else:
        verdict = "0xD1A5 is the same whichever bank is selected: consistent with the live Image Size reading"
    rep.add("d1a5", verdict, {"C%d" % k: [a["props"][0xD18E], a["live"]["props"][LIVE_IMAGE_SIZE]],
                              "C%d" % j: [b["props"][0xD18E], b["live"]["props"][LIVE_IMAGE_SIZE]]})


def test_selector(cam, args, rep):
    """Writes only the selector. Does 0xD18C survive a cable reconnect, and a bank change on the body?"""
    k = need_bank(args)
    print("  Adds: whether the selector persists on this body as it does on a GFX100RF (fuji-ptp-notes).")
    _, before = cam.get_u16(BANK_SELECT)
    print("    0xD18C before: %s" % show(BANK_SELECT, before))
    rc, _ = cam.select_bank(k)
    print("    selected C%d: %s" % (k, rc_name(rc)))
    cam.reconnect("Unplug the USB cable, wait a few seconds, plug it back in.")
    _, after_cable = cam.get_u16(BANK_SELECT)
    print("    0xD18C after reconnect: %s" % show(BANK_SELECT, after_cable))
    menu_prompt("switch to a different custom bank.")
    cam.selected_bank = None  # a recovery after the menu drop must not reselect, or it would mask the answer
    _, after_menu = cam.get_u16(BANK_SELECT)
    print("    0xD18C after a bank change on the camera: %s" % show(BANK_SELECT, after_menu))
    verdict = ("the selector survived the cable reconnect (%s); after a bank change on the body it read %s" % (
        show(BANK_SELECT, after_cable), show(BANK_SELECT, after_menu))
               if after_cable == k else "the selector did not survive the cable reconnect (%s)" % show(BANK_SELECT, after_cable))
    rep.add("selector", verdict, {"before": before, "selected": k, "after_cable": after_cable, "after_menu": after_menu})


def _backup_and_select(cam, k):
    if cam.experiment is None or k not in cam.experiment.banks:
        raise PTPError("write probe requires the experiment guard and immutable original snapshot")
    bank = cam.read_bank(k)
    validate_snapshot(bank)
    print_bank(bank, "bank C%d current test baseline (original backup retained separately):" % k)
    return bank, None


def test_dr_zero(cam, args, rep):
    """Write. Is 0 accepted on 0xD190 (fujifilm-ptp-recipes' DR Auto)?"""
    k = need_bank(args)
    print("  Settles: whether 0 means anything on 0xD190 (errata, DR Auto).")
    saved, _ = _backup_and_select(cam, k)
    if saved["props"][0xD191] != 0:
        print("    the priority is on in this bank; turning it off first")
        if cam.write_verify(0xD191, 0)["rc"] != 0x2001:
            rep.add("dr-zero", "could not turn the priority off (base ISO?); choose a bank at ISO 500+ with the priority off", None)
            return
    rows = [cam.write_verify(0xD190, 0), cam.write_verify(0xD190, 0xFFFF), cam.write_verify(0xD190, 100)]
    z = rows[0]
    if z["rc"] != 0x2001:
        verdict = "0 is refused on 0xD190 (%s); 0xFFFF %s" % (rc_name(z["rc"]), "accepted" if rows[1]["rc"] == 0x2001 else "refused")
    else:
        verdict = "0 is accepted on 0xD190 and reads back %s; check the camera's menu for what it shows" % show(0xD190, z["read"])
    rep.add("dr-zero", verdict, rows)


def test_toning(cam, args, rep):
    """Write. Zero, off-grid and range-edge values on the toning axes under ACROS, then under Sepia."""
    k = need_bank(args)
    print("  Settles: zero on 0xD193/0xD194 (X-H2 accepted; fuji-ptp-notes reports a GFX100RF refusal with conflicting provenance), the 10-step grid, and the Sepia open question.")
    saved, _ = _backup_and_select(cam, k)
    rows = []
    print("  under ACROS:")
    rows.append(cam.write_verify(0xD192, 12))
    values = [0, 10, -10 & 0xFFFF, 5, 9, -9 & 0xFFFF, 180, -180 & 0xFFFF, 190]
    for code in (0xD193, 0xD194):
        for v in values:
            rows.append(cam.write_verify(code, v))
    print("  under SEPIA:")
    rows.append(cam.write_verify(0xD192, 10))
    for code in (0xD193, 0xD194):
        rows.append(cam.write_verify(code, 10))
        rows.append(cam.write_verify(code, 0))
    zero = [r for r in rows[1:19] if r["wrote"] == 0]
    offgrid = [r for r in rows[1:19] if r["wrote"] in (5, 9, (-9) & 0xFFFF)]
    sepia = rows[20:]
    verdict = "under ACROS zero was %s; off-grid values were %s; under Sepia writes were %s" % (
        "accepted" if all(r["rc"] == 0x2001 for r in zero) else "refused",
        "refused" if all(r["rc"] != 0x2001 for r in offgrid) else "accepted (no 10-step grid here)",
        "accepted" if all(r["rc"] == 0x2001 for r in sepia) else ("refused" if all(r["rc"] != 0x2001 for r in sepia) else "mixed"))
    rep.add("toning", verdict, rows)


def test_name_last(cam, args, rep):
    """Write. Settings first, then the name, then a power cycle. Do the settings persist?"""
    k = need_bank(args)
    print("  Settles: whether a name written AFTER the settings commits them (both peers write it last).")
    saved, _ = _backup_and_select(cam, k)
    cur = saved["props"][0xD192]
    new = 2 if cur != 2 else 1
    test_name = "PROBE NAME LAST"
    print("  writing the film simulation (no name), then the name:")
    r1 = cam.write_verify(0xD192, new)
    rc = cam.set_str(BANK_NAME, test_name)
    _, back = cam.get_str(BANK_NAME)
    print("    0xD18D name <- %r  %s  reads %r" % (test_name, rc_name(rc), back))
    cam.reconnect("Switch the camera OFF, wait five seconds, switch it ON (a cable reconnect is not enough).")
    after = cam.read_bank(k)
    print("    after the power cycle: 0xD192 = %s (%s), name = %r" % (
        show(0xD192, after["props"][0xD192]), FILM_SIMS.get(after["props"][0xD192], "?"), after["name"]))
    if after["props"][0xD192] == new and after["name"] == test_name:
        verdict = "the setting written BEFORE the name survived the power cycle, and so did the name"
    elif after["props"][0xD192] == cur:
        verdict = "the setting read its original value after the cycle; the name %s; this trial alone does not establish a commit mechanism" % (
            "stuck" if after["name"] == test_name else "was lost too")
    else:
        verdict = "unexpected state after the power cycle; see the raw values"
    rep.add("name-last", verdict, {"wrote_sim": new, "after_sim": after["props"][0xD192], "after_name": after["name"]})


def test_heif(cam, args, rep):
    """Write. Is Clarity refused while the image format is HEIF, and is the format bank state?"""
    k = need_bank(args)
    print("  Settles: whether the GFX100RF's Clarity-versus-HEIF refusal holds here, and where the format lives.")
    saved, _ = _backup_and_select(cam, k)
    cur = saved["props"][0xD1A2] or 0
    alt = ((cur + 10) if s16(cur) < 50 else (cur - 10)) & 0xFFFF
    menu_prompt("with the camera on C%d, set the file format to HEIF (IMAGE QUALITY SETTING)." % k)
    b1 = cam.read_bank(k)
    print_diff(diff_banks(saved, b1))
    rows_heif = [cam.write_verify(0xD1A2, cur), cam.write_verify(0xD1A2, alt)]
    menu_prompt("set the file format back to JPEG.")
    b2 = cam.read_bank(k)
    print_diff(diff_banks(b1, b2))
    rows_jpeg = [cam.write_verify(0xD1A2, alt), cam.write_verify(0xD1A2, cur)]
    verdict = "under HEIF Clarity writes were %s; under JPEG %s; 0xD18F %s between the two" % (
        "refused" if all(r["rc"] != 0x2001 for r in rows_heif) else "accepted",
        "accepted" if all(r["rc"] == 0x2001 for r in rows_jpeg) else "refused",
        "changed" if b1["props"][0xD18F] != b2["props"][0xD18F] else "did not change")
    rep.add("heif", verdict, {"heif": rows_heif, "jpeg": rows_jpeg, "d18f_heif": b1["props"][0xD18F], "d18f_jpeg": b2["props"][0xD18F]})


def test_mono_colour(cam, args, rep):
    """Write. Are the colour-only properties refused on a monochrome bank?"""
    k = need_bank(args)
    print("  Settles: whether 0xD196/0xD197/0xD19A/0xD19B are refused under ACROS (fujifilm-ptp-recipes skips them by policy).")
    saved, _ = _backup_and_select(cam, k)
    rows = [cam.write_verify(0xD192, 12)]
    for code in (0xD196, 0xD197):
        v = saved["props"][code] or 1
        rows.append(cam.write_verify(code, v))
        rows.append(cam.write_verify(code, 2 if v != 2 else 1))
    for code in (0xD19A, 0xD19B):
        v = saved["props"][code] or 0
        rows.append(cam.write_verify(code, v))
        rows.append(cam.write_verify(code, (s16(v) + 1 if s16(v) < 9 else s16(v) - 1) & 0xFFFF))
    rows.append(cam.write_verify(0xD19F, saved["props"][0xD19F] or 0))
    refused = sorted({"0x%04X" % r["code"] for r in rows[1:] if r["rc"] != 0x2001})
    rep.add("mono-colour", "refused under ACROS: %s" % (", ".join(refused) if refused else "none"), rows)


def test_d1a5_write(cam, args, rep):
    """Write. Write Image Size on one bank, read 0xD1A5 on another."""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("d1a5-write needs --other-bank M as well")
    print("  Settles: the 0xD1A5 question by writing rather than by menu.")
    saved, _ = _backup_and_select(cam, k)
    other = read_bank_and_live(cam, j)
    cam.select_bank(k)
    target = 9 if saved["props"][0xD18E] != 9 else 7
    r = cam.write_verify(0xD18E, target)
    if r["rc"] != 0x2001:
        rep.add("d1a5-write", "0xD18E refused on C%d (%s): a bank mode such as Sports Finder fixes Image Size; pick another bank" % (k, rc_name(r["rc"])), r)
        return
    _, a5_k = cam.get_u16(LIVE_IMAGE_SIZE)
    cam.select_bank(j)
    _, e_j = cam.get_u16(0xD18E)
    _, a5_j = cam.get_u16(LIVE_IMAGE_SIZE)
    print("    C%d: 0xD18E <- %s, 0xD1A5 reads %s" % (k, show(0xD18E, target), show(0xD1A5, a5_k)))
    print("    C%d: 0xD18E reads %s, 0xD1A5 reads %s" % (j, show(0xD18E, e_j), show(0xD1A5, a5_j)))
    if a5_k == target and a5_j == target and e_j != target:
        verdict = "0xD1A5 took C%d's new Image Size and shows it while C%d is selected too: not a per-bank value" % (k, j)
    elif a5_k == target and a5_j != target:
        verdict = "0xD1A5 followed C%d's write and differed when C%d was selected in this trial; path identity is unchanged" % (k, j)
    elif a5_k != target:
        verdict = "0xD1A5 did not move when C%d's 0xD18E was written (%s); no causal relationship established by this trial" % (k, show(0xD1A5, a5_k))
    else:
        verdict = "inconclusive (both banks ended with the same Image Size)"
    rep.add("d1a5-write", verdict, {"a5_k": a5_k, "a5_j": a5_j, "e_j": e_j, "target": target})
    cam.select_bank(k)


def _menu_sweep(cam, k, steps, code, rep, name, intro):
    """steps: [(menu label, expected value or None)]. Reads the bank after each menu step."""
    print("  " + intro)
    before = cam.read_bank(k)
    results = []
    for label, expected in steps:
        menu_prompt("set C%d's %s and save it." % (k, label))
        after = cam.read_bank(k)
        changed = diff_banks(before, after)
        v = after["props"][code]
        others = [c for c, _, _ in changed if c != code]
        if expected is None:
            note = ""
        elif v == expected:
            note = "as predicted"
        else:
            note = "PREDICTED 0x%04X" % expected
        print("    %-28s 0x%04X = %-14s %s%s" % (label, code, show(code, v), note,
                                                 "  (also moved: %s)" % ", ".join("0x%04X" % c for c in others) if others else ""))
        results.append({"menu": label, "value": v, "expected": expected,
                        "others": [("0x%04X" % c, a, b) for c, a, b in changed if c != code]})
        before = after
    return results


def test_d1a3_meaning(cam, args, rep):
    """Read-only. Which of 1/2 is ON for LMO, and which is sRGB for Color Space."""
    k = need_bank(args)
    r1 = _menu_sweep(cam, k, [("LENS MODULATION OPTIMIZER to ON", 1), ("LENS MODULATION OPTIMIZER to OFF", 2)], 0xD1A3, rep, "d1a3",
                     "Confirms 0xD1A3: 1 = ON, 2 = OFF.")
    r2 = _menu_sweep(cam, k, [("COLOR SPACE to Adobe RGB", 2), ("COLOR SPACE to sRGB", 1)], 0xD1A4, rep, "d1a4",
                     "Settles 0xD1A4: which of 1/2 is sRGB.")
    ok = all(r["value"] == r["expected"] for r in r1 + r2)
    rep.add("d1a3-meaning", "LMO 1=ON 2=OFF and Color Space 1=sRGB 2=Adobe RGB, as predicted" if ok else "a value did not match the prediction; see rows", r1 + r2)


def test_wb_sweep(cam, args, rep):
    """Read-only. The white balance modes no body has menu-confirmed."""
    k = need_bank(args)
    steps = [("WHITE BALANCE to AUTO WHITE PRIORITY", 0x8020), ("WHITE BALANCE to AUTO AMBIENCE PRIORITY", 0x8021),
             ("WHITE BALANCE to UNDERWATER", 0x0008), ("WHITE BALANCE to SHADE", 0x8006),
             ("WHITE BALANCE to FLUORESCENT LIGHT 1", 0x8001), ("WHITE BALANCE to INCANDESCENT", 0x0006),
             ("WHITE BALANCE to AUTO", 0x0002),
             ("WHITE BALANCE to CUSTOM 1 (if the camera will not select it without measuring one, type s now; the steps before are kept)", 0x8008)]
    results = _menu_sweep(cam, k, steps, 0xD199, rep, "wb-sweep",
                          "Settles the open question on 0x8020 Auto White Priority, and confirms the other published values.")
    ok = all(r["value"] == r["expected"] for r in results)
    rep.add("wb-sweep", "every white balance value matches the record" if ok else "a value differs; see rows", results)


def test_imagesize_sweep(cam, args, rep):
    """Read-only. Image Size values against the size x aspect decode, watching 0xD1A5 too."""
    k = need_bank(args)
    steps = [("IMAGE SIZE to L 16:9", 8), ("IMAGE SIZE to L 1:1", 9), ("IMAGE SIZE to M 3:2", 4),
             ("IMAGE SIZE to S 3:2", 1), ("IMAGE SIZE to L 3:2", 7)]
    print("  Checks fujifilm-ptp-recipes' size x aspect decode of 0xD18E on hardware, and whether 0xD1A5 follows a saved bank.")
    before = read_bank_and_live(cam, k)
    results = []
    for label, expected in steps:
        menu_prompt("set C%d's %s (saved settings) and save it." % (k, label))
        after = read_bank_and_live(cam, k)
        v, a5 = after["props"][0xD18E], after["live"]["props"][LIVE_IMAGE_SIZE]
        others = [c for c, _, _ in diff_banks(before, after) if c not in (0xD18E, 0xD1A5)]
        print("    %-22s 0xD18E = %-12s %-16s 0xD1A5 = %s%s" % (label, show(0xD18E, v), "as predicted" if v == expected else "PREDICTED %d" % expected,
                                                               show(0xD1A5, a5), "  (also moved: %s)" % ", ".join("0x%04X" % c for c in others) if others else ""))
        results.append({"menu": label, "d18e": v, "expected": expected, "d1a5": a5})
        before = after
    ok = all(r["d18e"] == r["expected"] for r in results)
    followed = all(r["d1a5"] == r["d18e"] for r in results)
    rep.add("imagesize-sweep", "%s; 0xD1A5 %s the saved bank's Image Size" % (
        "every Image Size value matches the decode" if ok else "a value differs from the decode; see rows",
        "followed" if followed else "did not follow"), results)


def test_imagequality_sweep(cam, args, rep):
    """Read-only. What 0xD18F holds for each Image Quality setting."""
    k = need_bank(args)
    start = cam.read_bank(k)["props"][0xD18F]
    steps = [("IMAGE QUALITY to FINE", None), ("IMAGE QUALITY to NORMAL", None), ("IMAGE QUALITY to FINE + RAW", None),
             ("IMAGE QUALITY to NORMAL + RAW", None), ("IMAGE QUALITY to RAW", None)]
    results = _menu_sweep(cam, k, steps, 0xD18F, rep, "imagequality-sweep",
                          "Maps 0xD18F (the bank held %s before). X RAW Studio's tables suggest 2/3 for FINE/NORMAL and 4/5 with RAW." % show(0xD18F, start))
    menu_prompt("set C%d's IMAGE QUALITY back to what it was (it read %s) and save it." % (k, show(0xD18F, start)))
    rep.add("imagequality-sweep", "values recorded per setting; see rows", results)


def test_d1a5_live(cam, args, rep):
    """Read, then one write. Is 0xD1A5 the camera's live Image Size?"""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("d1a5-live needs --other-bank M as well")
    print("  Measures this body's response through X RAW Studio's established live Image Size path; menu/readback agreement is an observation, not a path-identity test.")
    menu_prompt("first make sure AUTO UPDATE CUSTOM SETTING is DISABLE (IQ menu). Put the camera on C%d. Then in the SHOOTING menu (not EDIT/SAVE CUSTOM SETTING) set IMAGE SIZE to L 1:1, so the live setting changes but nothing is saved to a bank." % k)
    a = read_bank_and_live(cam, k)
    b = read_bank_and_live(cam, j)
    print("    C%d: 0xD18E = %s  0xD1A5 = %s" % (k, show(0xD18E, a["props"][0xD18E]), show(0xD1A5, a["live"]["props"][LIVE_IMAGE_SIZE])))
    print("    C%d: 0xD18E = %s  0xD1A5 = %s" % (j, show(0xD18E, b["props"][0xD18E]), show(0xD1A5, b["live"]["props"][LIVE_IMAGE_SIZE])))
    live9 = a["live"]["props"][LIVE_IMAGE_SIZE] == 9 and b["live"]["props"][LIVE_IMAGE_SIZE] == 9
    if live9:
        verdict = "0xD1A5 reads 9 (L 1:1) on both banks after the live change%s: consistent with the LIVE Image Size" % (
            "" if a["props"][0xD18E] != 9 else " (C%d's own 0xD18E became 9 too, so the bank was saved as well)" % k)
    else:
        verdict = "after the reported menu change 0xD1A5 reads %s; menu/readback agreement was not observed%s" % (
            show(0xD1A5, a["live"]["props"][LIVE_IMAGE_SIZE]),
            "; C%d's 0xD18E reads 9 as well; the cause is unresolved" % k if a["props"][0xD18E] == 9 else "")
    print("  => " + verdict)
    r = cam.write_verify(LIVE_IMAGE_SIZE, 7)
    answer = ""
    if r["rc"] == 0x2001:
        answer = ask("0xD1A5 was just written to 7 (L 3:2) over USB. Unplug the cable, open the SHOOTING menu and read IMAGE SIZE, plug the cable back in, then type what it showed (3:2 or 1:1).")
        print("    live IMAGE SIZE after the write, as read on the camera: %r" % answer)
    menu_prompt("set the live IMAGE SIZE back to what you normally use.")
    rep.add("d1a5-live", verdict + ("; after writing 7 the camera showed %r" % answer if answer else ""),
            {"d18e": [a["props"][0xD18E], b["props"][0xD18E]], "d1a5": [a["live"]["props"][LIVE_IMAGE_SIZE], b["live"]["props"][LIVE_IMAGE_SIZE]], "write": r, "camera_showed": answer})


def test_selector_reset(cam, args, rep):
    """Selector only. Does a bank change on the body reset 0xD18C, and what does a read without a select address?"""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("selector-reset needs --other-bank M as well")
    print("  Settles whether changing the bank on the body resets 0xD18C (as on a GFX100RF), and which bank an unselected read addresses.")
    body = ask("Which custom bank is the camera on right now? Type the number (1-7).")
    _, before = cam.get_u16(BANK_SELECT)
    print("    0xD18C on connect: %s (camera reportedly on C%s)" % (show(BANK_SELECT, before), body))
    sims = {}
    for bank in (k, j):
        sims[bank] = cam.read_bank(bank)["props"][0xD192]
    cam.select_bank(k)
    print("    selected C%d" % k)
    cam.reconnect("Unplug the cable, wait five seconds, plug it back in. Do NOT change the bank on the camera.")
    cam.selected_bank = None
    _, after_cable = cam.get_u16(BANK_SELECT)
    print("    0xD18C after a cable reconnect, no reselect: %s" % show(BANK_SELECT, after_cable))
    menu_prompt("switch the camera to C%d." % j)
    cam.selected_bank = None
    _, after_change = cam.get_u16(BANK_SELECT)
    _, sim_noselect = cam.get_u16(0xD192)
    print("    0xD18C after switching the body to C%d, no reselect: %s" % (j, show(BANK_SELECT, after_change)))
    print("    0xD192 read without a select: %s (C%d holds %s, C%d holds %s)" % (
        show(0xD192, sim_noselect), k, show(0xD192, sims[k]), j, show(0xD192, sims[j])))
    if after_cable != k:
        verdict = "the selector did not survive the cable reconnect (%s)" % show(BANK_SELECT, after_cable)
    elif after_change == j:
        verdict = "a bank change on the body resets 0xD18C to the body's bank (%d), as on the GFX100RF" % j
    elif after_change == k:
        verdict = "0xD18C kept %d through a bank change on the body: sticky regardless" % k
    else:
        verdict = "0xD18C read %s after the bank change; see values" % show(BANK_SELECT, after_change)
    rep.add("selector-reset", verdict, {"body_before": body, "on_connect": before, "after_cable": after_cable,
                                        "after_change": after_change, "sim_noselect": sim_noselect, "sims": sims})


def test_heif_scope(cam, args, rep):
    """Write. Is the Clarity-under-HEIF refusal camera-wide or per bank?"""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("heif-scope needs --other-bank M as well")
    print("  Settles whether the HEIF gate on Clarity follows the camera's live format or the bank.")
    saved, _ = _backup_and_select(cam, k)
    other = cam.read_bank(j)
    menu_prompt("put the camera on C%d and set the file format to HEIF (IMAGE QUALITY SETTING). Leave C%d alone." % (j, k))
    rows = {}
    for bank, cur in ((k, saved["props"][0xD1A2]), (j, other["props"][0xD1A2])):
        cam.select_bank(bank)
        print("  C%d under HEIF:" % bank)
        rows["heif_C%d" % bank] = cam.write_verify(0xD1A2, cur or 0)
    menu_prompt("set the file format back to JPEG.")
    for bank, cur in ((k, saved["props"][0xD1A2]), (j, other["props"][0xD1A2])):
        cam.select_bank(bank)
        print("  C%d under JPEG:" % bank)
        rows["jpeg_C%d" % bank] = cam.write_verify(0xD1A2, cur or 0)
    hk, hj = rows["heif_C%d" % k]["rc"], rows["heif_C%d" % j]["rc"]
    if hk != 0x2001 and hj != 0x2001:
        verdict = "under HEIF both banks refused Clarity: the gate is the camera's live format, not the bank's"
    elif hk == 0x2001 and hj == 0x2001:
        verdict = "under HEIF both banks accepted Clarity: no gate seen this time (was the format really HEIF?)"
    else:
        verdict = "under HEIF C%d %s and C%d %s: the gate follows the bank" % (
            k, "refused" if hk != 0x2001 else "accepted", j, "refused" if hj != 0x2001 else "accepted")
    rep.add("heif-scope", verdict, rows)
    cam.select_bank(k)


def test_iso_threshold(cam, args, rep):
    """Write. Where DR200 and DR400 start being accepted: ISO 125, 250, 500."""
    k = need_bank(args)
    print("  Settles the DR200 threshold (ISO 250 was never tried) with D-Range Priority off.")
    saved, _ = _backup_and_select(cam, k)
    if saved["props"][0xD191] not in (0, None):
        print("    the priority is on in this bank; turning it off first")
        cam.write_verify(0xD191, 0)
    original = saved["props"][0xD190]
    results = {}
    for iso in ("125 (base)", "250", "500"):
        menu_prompt("set C%d's ISO to %s (saved settings), leave DYNAMIC RANGE and D RANGE PRIORITY alone, and save." % (k, iso))
        print("  ISO %s:" % iso)
        results[iso] = [cam.write_verify(0xD190, v) for v in (100, 200, 400, 0xFFFF)]
        if original is not None:
            cam.write_verify(0xD190, original)
    def accepted(iso, v):
        return any(r["wrote"] == v and r["rc"] == 0x2001 for r in results[iso])
    verdict = "; ".join("ISO %s: DR200 %s, DR400 %s" % (iso, "ok" if accepted(iso, 200) else "refused", "ok" if accepted(iso, 400) else "refused") for iso in results)
    rep.add("iso-threshold", verdict, results)
    menu_prompt("set C%d's ISO back to what it was and save." % k)


def test_d18e_gates(cam, args, rep):
    """Write. Do Digital Tele-Converter and HDR make a bank refuse Image Size, as Sports Finder Mode does?"""
    k = need_bank(args)
    print("  Settles two open questions: which bank modes fix Image Size.")
    saved, _ = _backup_and_select(cam, k)
    cur = saved["props"][0xD18E]
    rows = {}
    menu_prompt("in C%d's saved settings turn DIGITAL TELE-CONV. ON (any magnification) and save. If this body has no such item, type s." % k)
    rows["tele_on"] = cam.write_verify(0xD18E, cur)
    menu_prompt("turn DIGITAL TELE-CONV. OFF again in C%d and save." % k)
    rows["tele_off"] = cam.write_verify(0xD18E, cur)
    menu_prompt("turn HDR ON for C%d (DRIVE SETTING, HDR) and save. If HDR is not stored per bank on this body, type s to end the test here; the tele-converter result is kept." % k)
    rows["hdr_on"] = cam.write_verify(0xD18E, cur)
    menu_prompt("turn HDR OFF again and save.")
    rows["hdr_off"] = cam.write_verify(0xD18E, cur)
    verdict = "Digital Tele-Converter on: 0xD18E %s; HDR on: 0xD18E %s" % (
        "refused" if rows["tele_on"]["rc"] != 0x2001 else "accepted",
        "refused" if rows["hdr_on"]["rc"] != 0x2001 else "accepted")
    rep.add("d18e-gates", verdict, rows)


def test_no_name_control(cam, args, rep):
    """Write. The control for name-last: record a setting written with NO name write before and after power cycle."""
    k = need_bank(args)
    print("  Control for name-last: record whether a write without a name survives a power cycle, with AUTO UPDATE recorded.")
    saved, _ = _backup_and_select(cam, k)
    cur = saved["props"][0xD192]
    new = 2 if cur != 2 else 1
    r = cam.write_verify(0xD192, new)
    cam.reconnect("Switch the camera OFF, wait five seconds, switch it ON (no name was written this time).")
    after = cam.read_bank(k)
    v = after["props"][0xD192]
    if v == cur:
        verdict = "the original value was read after the power cycle; this observation alone does not prove that a name write commits settings"
    elif v == new:
        verdict = "the new value was read after the power cycle without a name write in this trial"
    else:
        verdict = "unexpected value %s after the power cycle" % show(0xD192, v)
    rep.add("no-name-control", verdict, {"wrote": new, "after": v, "original": cur})


def _commit_fresh(cam, args, rep, name, graceful):
    k = need_bank(args)
    print("  Settles what makes a bank persist. Run this FIRST after a power-on, before any other test, so no name has been written since.")
    cam.reconnect("Switch the camera OFF, wait five seconds, switch it ON, so this session starts fresh. (Plug the cable back in if you pulled it.)")
    saved, _ = _backup_and_select(cam, k)
    cur = saved["props"][0xD192]
    new = 2 if cur != 2 else 1
    r = cam.write_verify(0xD192, new)
    if graceful:
        cam.reconnect("The session is being CLOSED first. Now switch the camera OFF, wait five seconds, switch it ON.", graceful=True)
    else:
        cam.reconnect("The session is left OPEN. PULL the USB cable now, then switch the camera OFF, wait five seconds, switch it ON, and plug the cable back in.", graceful=False)
    after = cam.read_bank(k)
    v = after["props"][0xD192]
    how = "with the session closed first" if graceful else "with the cable pulled and the session left open"
    if v == cur:
        verdict = "the setting written with no name was LOST at power cycle %s" % how
    elif v == new:
        verdict = "the setting written with no name PERSISTED through the power cycle %s" % how
    else:
        verdict = "unexpected value %s after the power cycle" % show(0xD192, v)
    rep.add(name, verdict, {"wrote": new, "after": v, "original": cur, "graceful": graceful})


def test_commit_fresh_pull(cam, args, rep):
    """Write. Fresh power-on, one property with no name, cable pulled with the session open, power cycle."""
    _commit_fresh(cam, args, rep, "commit-fresh-pull", graceful=False)


def test_commit_fresh_close(cam, args, rep):
    """Write. Fresh power-on, one property with no name, session closed, power cycle."""
    _commit_fresh(cam, args, rep, "commit-fresh-close", graceful=True)


def test_live_vs_saved(cam, args, rep):
    """Read-only. Does a USB read of the bank the body is on show its saved contents, or the body's live, unsaved copy?"""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("live-vs-saved needs --other-bank M as well")
    print("  Settles whether reading the bank the camera is on shows the saved bank or its current, possibly unsaved, state.")
    menu_prompt("check that AUTO UPDATE CUSTOM SETTING is DISABLE. Put the camera on C%d. In the SHOOTING menu (not EDIT/SAVE CUSTOM SETTING) set IMAGE SIZE to L 1:1 and do NOT save it to the bank." % k)
    a1 = cam.read_bank(k)["props"][0xD18E]
    print("    body on C%d with live Image Size L 1:1: C%d's 0xD18E reads %s" % (k, k, show(0xD18E, a1)))
    marker = ask("Look at the camera: does it mark C%d as modified (an asterisk or dot by the bank name, or EDIT/SAVE CUSTOM SETTING showing it differs from the saved one)? Type what you see." % k)
    menu_prompt("switch the camera to C%d. Touch nothing else." % j)
    a2 = cam.read_bank(k)["props"][0xD18E]
    b2 = cam.read_bank(j)["props"][0xD18E]
    print("    body on C%d: C%d's 0xD18E reads %s, C%d's reads %s" % (j, k, show(0xD18E, a2), j, show(0xD18E, b2)))
    menu_prompt("switch the camera back to C%d. Touch nothing else." % k)
    a3 = cam.read_bank(k)["props"][0xD18E]
    print("    body back on C%d: C%d's 0xD18E reads %s" % (k, k, show(0xD18E, a3)))
    if a1 == 9 and a2 != 9:
        verdict = "with the body on C%d the read showed the live, unsaved value (9); with the body elsewhere it showed the saved value (%s): a read of the body's current bank shows its live state" % (k, show(0xD18E, a2))
    elif a1 == 9 and a2 == 9:
        verdict = "C%d read 9 whichever bank the body was on: the shooting-menu change was stored in the bank itself" % k
    elif a1 != 9:
        verdict = "C%d's 0xD18E stayed %s under a live Image Size of L 1:1: the read shows the saved bank, not the live state" % (k, show(0xD18E, a1))
    else:
        verdict = "see values"
    rep.add("live-vs-saved", verdict + "; camera marker: %r" % marker, {"on_k": a1, "on_j": [a2, b2], "back_on_k": a3, "marker": marker})
    menu_prompt("set the live IMAGE SIZE back to L 3:2, and if C%d shows as modified, reset it to its saved settings." % k)


def test_working_copy(cam, args, rep):
    """Write. Three experiments on where a USB write lands: reset after a bare write; name first then a write; a write then the name."""
    k = need_bank(args)
    print("  Settles whether the camera's reset discards a bare USB write, and whether X RAW Studio's name-first order leaves settings unsaved.")
    menu_prompt("put the camera on C%d. If C%d shows unsaved changes (a red dot), reset it to its saved settings first, so it shows none." % (k, k))
    saved, _ = _backup_and_select(cam, k)
    cur = saved["props"][0xD192]
    new = 2 if cur != 2 else 1
    name = saved["name"] or "C%d" % k
    detail = {"original": cur, "wrote": new}

    print("  A. a bare property write, then the camera's reset:")
    cam.write_verify(0xD192, new)
    detail["A_marker"] = ask("UNPLUG the cable and look at C%d: is the unsaved-changes marker (red dot) showing? Plug the cable back in, then type yes or no." % k)
    menu_prompt("reset C%d to its saved settings on the camera." % k)
    a = cam.read_bank(k)["props"][0xD192]
    detail["A_after_reset"] = a
    print("    after the reset C%d's 0xD192 reads %s: the bare write was %s" % (k, show(0xD192, a), "REVERTED" if a == cur else ("kept" if a == new else "something else")))

    print("  B. the name first, then the property (X RAW Studio's order):")
    cam.set_str(BANK_NAME, name)
    cam.write_verify(0xD192, new)
    detail["B_marker"] = ask("UNPLUG the cable and look at C%d: is the unsaved-changes marker showing now? Plug the cable back in, then type yes or no." % k)
    menu_prompt("reset C%d to its saved settings on the camera." % k)
    b = cam.read_bank(k)["props"][0xD192]
    detail["B_after_reset"] = b
    print("    after the reset C%d's 0xD192 reads %s: name-first left the write %s" % (k, show(0xD192, b), "UNSAVED (reverted)" if b == cur else ("saved" if b == new else "something else")))

    print("  C. the property, then the name:")
    cam.write_verify(0xD192, new)
    cam.set_str(BANK_NAME, name)
    detail["C_marker"] = ask("UNPLUG the cable and look at C%d: is the unsaved-changes marker showing now? Plug the cable back in, then type yes or no." % k)
    menu_prompt("reset C%d to its saved settings on the camera." % k)
    c = cam.read_bank(k)["props"][0xD192]
    detail["C_after_reset"] = c
    print("    after the reset C%d's 0xD192 reads %s: name-last left the write %s" % (k, show(0xD192, c), "saved" if c == new else ("UNSAVED (reverted)" if c == cur else "something else")))

    def reset_observation(value):
        return "unavailable" if value is None else "original value read" if value == cur else "new value read" if value == new else "unexpected value"
    verdict = "after reset, bare write: %s; name first: %s; name last: %s" % (
        reset_observation(a), reset_observation(b), reset_observation(c))
    rep.add("working-copy", verdict, detail)
    print("  After automatic cleanup finishes, check the original recipe and unsaved markers on the camera; persistence is not guaranteed by readback.")


def _look_markers(k, step):
    """Two explicit questions about the camera's modified markers, always in the same two places."""
    print("  -- %s: look at the camera --" % step)
    q = ask("UNPLUG the cable. Press the Q button and look at the custom-setting tile for C%d: is there a red dot on it? Type yes or no (plug the cable back in first)." % k)
    m = ask("UNPLUG the cable again if needed. MENU, IQ, EDIT/SAVE CUSTOM SETTING, look at the C%d row: red dot? Then open C%d and look at its items: a red dot on any item, and which? Type what you see (plug the cable back in first)." % (k, k))
    print("    Q menu: %r   custom-setting menu: %r" % (q, m))
    return {"q_menu": q, "settings_menu": m}


def _reset_and_read(cam, k, code):
    menu_prompt("in EDIT/SAVE CUSTOM SETTING, select C%d and choose the option that DISCARDS the changes and returns C%d to its saved settings (RESET), not the one that saves the current changes into it. Note which options the camera offered." % (k, k))
    offered = ask("Which options did the camera offer for C%d there (for example SAVE / RESET / EDIT)? Type them." % k)
    v = cam.read_bank(k)["props"][code]
    return v, offered


def test_markers(cam, args, rep):
    """Write. Where the camera shows a modified bank, for each way of changing it, with the camera's reset as the judge."""
    k = need_bank(args)
    print("  Establishes, with the same two looks at every step, where the camera marks a modified bank and what its reset keeps.")
    print("  Five scenarios, each ending with the camera's reset of C%d and a read. Answer the two questions literally each time." % k)
    saved, _ = _backup_and_select(cam, k)
    sim0, size0 = saved["props"][0xD192], saved["props"][0xD18E]
    new_sim = 2 if sim0 != 2 else 1
    name = saved["name"] or "C%d" % k
    results = {"original_sim": sim0, "original_size": size0, "new_sim": new_sim}

    menu_prompt("put the camera on C%d and, in EDIT/SAVE CUSTOM SETTING, reset C%d to its saved settings so it is clean." % (k, k))
    results["0_baseline"] = _look_markers(k, "0. baseline, nothing changed")

    print("  1. a change made on the camera itself, not saved")
    menu_prompt("with the body on C%d, in the SHOOTING menu (not EDIT/SAVE), set IMAGE SIZE to L 1:1 and do not save it." % k)
    v = cam.read_bank(k)["props"][0xD18E]
    print("    C%d's 0xD18E now reads %s" % (k, show(0xD18E, v)))
    r = {"read": v}
    r.update(_look_markers(k, "1. after the shooting-menu change"))
    r["after_reset"], r["reset_options"] = _reset_and_read(cam, k, 0xD18E)
    print("    after the reset 0xD18E reads %s (%s)" % (show(0xD18E, r["after_reset"]), "reverted" if r["after_reset"] == size0 else "kept"))
    results["1_camera_change"] = r

    print("  2. a bare USB write, no name")
    cam.write_verify(0xD192, new_sim)
    r = {}
    r.update(_look_markers(k, "2. after the bare USB write"))
    r["after_reset"], r["reset_options"] = _reset_and_read(cam, k, 0xD192)
    print("    after the reset 0xD192 reads %s (%s)" % (show(0xD192, r["after_reset"]), "reverted" if r["after_reset"] == sim0 else "kept"))
    results["2_bare_write"] = r

    print("  3. a USB write, then the name")
    cam.write_verify(0xD192, new_sim)
    cam.set_str(BANK_NAME, name)
    r = {}
    r.update(_look_markers(k, "3. after write then name"))
    r["after_reset"], r["reset_options"] = _reset_and_read(cam, k, 0xD192)
    print("    after the reset 0xD192 reads %s (%s)" % (show(0xD192, r["after_reset"]), "kept" if r["after_reset"] == new_sim else "reverted"))
    results["3_write_then_name"] = r
    if r["after_reset"] == new_sim:
        cam.write_verify(0xD192, sim0)
        cam.set_str(BANK_NAME, name)
        print("    (put the film simulation back to %s and saved it, so the next scenario starts clean)" % show(0xD192, sim0))
        menu_prompt("reset C%d once more so it is clean, and confirm no red dot in either place before continuing." % k)

    print("  4. the name first, then a USB write (X RAW Studio's order)")
    cam.set_str(BANK_NAME, name)
    cam.write_verify(0xD192, new_sim)
    r = {}
    r.update(_look_markers(k, "4. after name then write"))
    r["after_reset"], r["reset_options"] = _reset_and_read(cam, k, 0xD192)
    print("    after the reset 0xD192 reads %s (%s)" % (show(0xD192, r["after_reset"]), "kept" if r["after_reset"] == new_sim else "reverted"))
    results["4_name_then_write"] = r
    if r["after_reset"] == new_sim:
        cam.write_verify(0xD192, sim0)
        cam.set_str(BANK_NAME, name)
        menu_prompt("reset C%d once more so it is clean before the last scenario." % k)

    print("  5. the name alone, nothing else written")
    cam.set_str(BANK_NAME, name)
    results["5_name_only"] = _look_markers(k, "5. after a name write alone")

    def kept(key, code_orig, new):
        return "kept" if results[key]["after_reset"] == new else ("reverted" if results[key]["after_reset"] == code_orig else "?")
    verdict = "camera change: %s; bare write: %s; write then name: %s; name then write: %s" % (
        "reverted" if results["1_camera_change"]["after_reset"] == size0 else "kept",
        kept("2_bare_write", sim0, new_sim), kept("3_write_then_name", sim0, new_sim), kept("4_name_then_write", sim0, new_sim))
    rep.add("markers", verdict + " (markers per step in the log)", results)
    print("  After automatic cleanup, inspect the camera markers manually; cleanup does not establish persistence.")


def test_bank_switch(cam, args, rep):
    """Write. Where a USB write lands, judged by switching the body away and back instead of SAVE/RESET."""
    k = need_bank(args)
    j = args.other_bank
    if j is None:
        sys.exit("bank-switch needs --other-bank M as well")
    print("  Settles where a USB write lands without using the camera's SAVE/RESET options, which are easy to confuse.")
    print("  The judge is what the camera itself shoots with after leaving the bank and coming back, read off the Q menu.")
    saved, _ = _backup_and_select(cam, k)
    sim0 = saved["props"][0xD192]
    new_sim = 2 if sim0 != 2 else 1
    name = saved["name"] or "C%d" % k
    sims = {1: "PROVIA", 2: "Velvia"}
    results = {"original_sim": sim0, "new_sim": new_sim}

    menu_prompt("put the camera on C%d. In EDIT/SAVE CUSTOM SETTING, if C%d offers RESET THE CHANGES, choose it, so C%d is clean. Do not touch anything else." % (k, k, k))
    results["0_q_menu_sim"] = ask("UNPLUG the cable. Press Q and read the FILM SIMULATION tile: which simulation does the camera show for C%d right now? Plug the cable back in, then type it." % k)

    print("  A. a bare USB write, then the body switched to C%d and back to C%d" % (j, k))
    cam.write_verify(0xD192, new_sim)
    results["A_q_before_switch"] = ask("UNPLUG the cable. Press Q: which FILM SIMULATION does the camera show now, before switching banks? Plug the cable back in, then type it.")
    menu_prompt("switch the camera to C%d, then back to C%d. Do not save or reset anything." % (j, k))
    results["A_read_after_switch"] = cam.read_bank(k)["props"][0xD192]
    print("    C%d's 0xD192 after the switch reads %s" % (k, show(0xD192, results["A_read_after_switch"])))
    results["A_q_after_switch"] = ask("UNPLUG the cable. Press Q: which FILM SIMULATION does the camera show now? And in EDIT/SAVE CUSTOM SETTING, is C%d marked with a red dot? Plug the cable back in, then type both." % k)

    print("  B. the name written now, after the write, then the body switched away and back")
    cam.set_str(BANK_NAME, name)
    results["B_q_after_name"] = ask("UNPLUG the cable. Press Q: which FILM SIMULATION does the camera show now? Plug the cable back in, then type it.")
    menu_prompt("switch the camera to C%d, then back to C%d. Do not save or reset anything." % (j, k))
    results["B_read_after_switch"] = cam.read_bank(k)["props"][0xD192]
    print("    C%d's 0xD192 after the switch reads %s" % (k, show(0xD192, results["B_read_after_switch"])))
    results["B_q_after_switch"] = ask("UNPLUG the cable. Press Q: which FILM SIMULATION does the camera show now? Any red dot on C%d in EDIT/SAVE CUSTOM SETTING? Plug the cable back in, then type both." % k)

    print("  C. the name first, then a USB write, then the body switched away and back")
    cam.write_verify(0xD192, sim0)
    cam.set_str(BANK_NAME, name)
    menu_prompt("switch the camera to C%d, then back to C%d, so C%d starts clean again." % (j, k, k))
    cam.set_str(BANK_NAME, name)
    cam.write_verify(0xD192, new_sim)
    results["C_q_before_switch"] = ask("UNPLUG the cable. Press Q: which FILM SIMULATION does the camera show now, before switching banks? Plug the cable back in, then type it.")
    menu_prompt("switch the camera to C%d, then back to C%d. Do not save or reset anything." % (j, k))
    results["C_read_after_switch"] = cam.read_bank(k)["props"][0xD192]
    print("    C%d's 0xD192 after the switch reads %s" % (k, show(0xD192, results["C_read_after_switch"])))
    results["C_q_after_switch"] = ask("UNPLUG the cable. Press Q: which FILM SIMULATION does the camera show now? Any red dot on C%d in EDIT/SAVE CUSTOM SETTING? Plug the cable back in, then type both." % k)

    want = sims.get(new_sim, show(0xD192, new_sim))
    verdict = "after a bare write and a bank switch the camera shows %r (wrote %s); after write+name %r; after name+write %r. 0xD192 read %s / %s / %s." % (
        results["A_q_after_switch"], want, results["B_q_after_switch"], results["C_q_after_switch"],
        show(0xD192, results["A_read_after_switch"]), show(0xD192, results["B_read_after_switch"]), show(0xD192, results["C_read_after_switch"]))
    rep.add("bank-switch", verdict, results)
    print("  After automatic cleanup finishes, check the original recipe and unsaved markers on the camera; persistence is not guaranteed by readback.")


def test_name_timing(cam, args, rep):
    """Write. What lets a name write clear the camera's unsaved marker: nothing, time, a new PTP session, or a reconnect."""
    k = need_bank(args)
    print("  Settles what a writer must do so the camera does not mark a written bank as unsaved.")
    print("  Four scenarios, each: one film simulation write, then the name, then one look at the camera.")
    before = ask("Before touching anything: on the camera, MENU > IQ > EDIT/SAVE CUSTOM SETTING > C%d. Which FILM SIMULATION does C%d show, is there a red dot on it, "
                 "and at the end of the last test did you choose RESET THE CHANGES? Type all three (unplug to look, plug back in to type)." % (k, k))
    menu_prompt("in EDIT/SAVE CUSTOM SETTING, if C%d has a red dot anywhere, choose SAVE THE CHANGES for C%d so nothing is marked. If there is no dot, change nothing." % (k, k))
    saved, _ = _backup_and_select(cam, k)
    sim0 = saved["props"][0xD192]
    alt = 2 if sim0 != 2 else 1
    name = saved["name"] or "C%d" % k
    results = {"before_test": before, "start_sim": sim0}
    scenarios = [
        ("1-same-session", "the name straight after the write, in the same session (the control)"),
        ("2-wait-10s", "the name 10 seconds after the write, in the same session"),
        ("3-new-ptp-session", "CloseSession and OpenSession over the same cable, then the name"),
        ("4-reconnect", "the cable unplugged and replugged with the camera untouched, then the name"),
    ]
    current = sim0
    for key, desc in scenarios:
        new = alt if current == sim0 else sim0
        print()
        print("  %s: %s" % (key, desc))
        cam.write_verify(0xD192, new)
        if key == "2-wait-10s":
            print("    waiting 10 seconds...")
            time.sleep(10)
        elif key == "3-new-ptp-session":
            rc = cam.transact(OP_CLOSE_SESSION)[0]
            print("    CloseSession  %s" % rc_name(rc))
            cam.start_session()
            print("    OpenSession again")
            cam.select_bank(k)
        elif key == "4-reconnect":
            cam.reconnect("UNPLUG the USB cable, wait five seconds, and plug it back in. Do NOT touch the camera's buttons or menus.", graceful=False)
            cam.select_bank(k)
        rc = cam.set_str(BANK_NAME, name)
        print("    0xD18D name <- %r  %s" % (name, rc_name(rc)))
        seen = ask("UNPLUG the cable. MENU > IQ > EDIT/SAVE CUSTOM SETTING > open C%d. Is there a red dot on FILM SIMULATION, and which simulation does it show? "
                   "Then, ONLY if there was a dot, choose SAVE THE CHANGES for C%d (it keeps %s). Plug the cable back in and type what you saw BEFORE saving, "
                   "e.g. 'dot, Velvia' or 'no dot, ACROS'." % (k, k, FILM_SIMS.get(new, new)))
        print("    camera showed: %r" % seen)
        results[key] = {"wrote": new, "seen": seen}
        current = new
    verdict = "same session: %r; after 10 s: %r; new PTP session: %r; after a reconnect: %r" % tuple(
        results[key]["seen"] for key, _ in scenarios)
    rep.add("name-timing", verdict, results)
    print("  After automatic cleanup finishes, check the original recipe and unsaved markers on the camera; persistence is not guaranteed by readback.")


def test_reset_check(cam, args, rep):
    """Write. What RESET THE CHANGES does to a USB write, with and without a name, and what opening the item does."""
    k = need_bank(args)
    print("  Settles whether the camera's RESET THE CHANGES undoes a USB write, and what opening the item on the camera does.")
    print("  Three scenarios. Follow each prompt exactly, especially whether to open items or not.")
    menu_prompt("in EDIT/SAVE CUSTOM SETTING, if C%d has a red dot anywhere, choose SAVE THE CHANGES for C%d, so nothing is marked." % (k, k))
    saved, _ = _backup_and_select(cam, k)
    sim0 = saved["props"][0xD192]
    alt = 2 if sim0 != 2 else 1
    name = saved["name"] or "C%d" % k
    results = {"start_sim": sim0}

    def other(v):
        return alt if v == sim0 else sim0

    def outcome(before, new, after):
        return "REVERTED by RESET" if after == before else ("kept" if after == new else "changed to %s" % show(0xD192, after))

    no_open = ("UNPLUG the cable. MENU > IQ > EDIT/SAVE CUSTOM SETTING. Do NOT use EDIT/CHECK and do NOT open any item inside C%d. "
               "Is there a red dot on the C%d row? Then select C%d and choose RESET THE CHANGES (confirm if asked). "
               "Plug the cable back in and type: red dot yes/no, and whether RESET THE CHANGES could be chosen." % (k, k, k))

    print()
    print("  R. a bare USB write, then RESET THE CHANGES with no item opened")
    before = cam.read_bank(k)["props"][0xD192]
    new = other(before)
    cam.write_verify(0xD192, new)
    seen = ask(no_open)
    after = cam.read_bank(k)["props"][0xD192]
    results["R"] = {"before": before, "wrote": new, "seen": seen, "after": after}
    print("    after RESET 0xD192 reads %s: %s" % (show(0xD192, after), outcome(before, new, after)))

    print()
    print("  N. a USB write and then the name, then RESET THE CHANGES with no item opened")
    before = after
    new = other(before)
    cam.write_verify(0xD192, new)
    rc = cam.set_str(BANK_NAME, name)
    print("    0xD18D name <- %r  %s" % (name, rc_name(rc)))
    seen = ask(no_open)
    after = cam.read_bank(k)["props"][0xD192]
    results["N"] = {"before": before, "wrote": new, "seen": seen, "after": after}
    print("    after RESET 0xD192 reads %s: %s" % (show(0xD192, after), outcome(before, new, after)))

    print()
    print("  V. a bare USB write, then the item opened and closed on the camera, then RESET if it is offered")
    before = after
    new = other(before)
    cam.write_verify(0xD192, new)
    seen = ask("UNPLUG the cable. MENU > IQ > EDIT/SAVE CUSTOM SETTING. First: is there a red dot on the C%d row? Then select C%d > EDIT/CHECK, open FILM SIMULATION, "
               "do NOT change it, and back out. Is the red dot on FILM SIMULATION still there? Back out to C%d's options: can RESET THE CHANGES be chosen, or is it greyed out? "
               "If it can be chosen, choose it. Plug the cable back in and type all of that." % (k, k, k))
    after = cam.read_bank(k)["props"][0xD192]
    results["V"] = {"before": before, "wrote": new, "seen": seen, "after": after}
    print("    afterwards 0xD192 reads %s: %s" % (show(0xD192, after), outcome(before, new, after)))

    verdict = "bare write + RESET: %s; write + name + RESET: %s; bare write + item opened: %s (camera: %r)" % (
        outcome(results["R"]["before"], results["R"]["wrote"], results["R"]["after"]),
        outcome(results["N"]["before"], results["N"]["wrote"], results["N"]["after"]),
        outcome(results["V"]["before"], results["V"]["wrote"], results["V"]["after"]), results["V"]["seen"])
    rep.add("reset-check", verdict, results)
    print("  After automatic cleanup finishes, check the original recipe and unsaved markers on the camera; persistence is not guaranteed by readback.")


def test_power_dot(cam, args, rep):
    """Write. Does the camera's red-dot flag on a pushed bank survive a power cycle?"""
    k = need_bank(args)
    print("  Settles whether the red dot a USB push leaves on a bank is still there after the camera is switched off and on.")
    look = ("UNPLUG the cable. MENU > IQ > EDIT/SAVE CUSTOM SETTING > C%d > EDIT/CHECK, and look at the list of items. "
            "Do NOT open FILM SIMULATION or any other item (opening an item may affect the marker; avoid that variable). Is there a red dot on the C%d row, "
            "and on FILM SIMULATION in the list? Back out without changing anything, plug the cable back in, and type what you saw." % (k, k))
    menu_prompt("in EDIT/SAVE CUSTOM SETTING, if C%d has a red dot anywhere, choose SAVE THE CHANGES for C%d, so nothing is marked." % (k, k))
    saved, _ = _backup_and_select(cam, k)
    sim0 = saved["props"][0xD192]
    new = 2 if sim0 != 2 else 1
    name = saved["name"] or "C%d" % k

    print("  A push: the film simulation, then the name")
    cam.write_verify(0xD192, new)
    rc = cam.set_str(BANK_NAME, name)
    print("    0xD18D name <- %r  %s" % (name, rc_name(rc)))
    before = ask(look)
    print("    before the power cycle the camera showed: %r" % before)

    cam.reconnect("Switch the camera OFF, wait five seconds, and switch it back ON. Leave the cable plugged in (or plug it back in), and wait for the camera's USB screen.")
    v = cam.read_bank(k)["props"][0xD192]
    print("    after the power cycle C%d's 0xD192 reads %s (%s)" % (k, show(0xD192, v), "the push survived" if v == new else "NOT the pushed value"))
    after = ask(look)
    print("    after the power cycle the camera showed: %r" % after)

    rep.add("power-dot", "before the power cycle: %r; after: %r; value after: %s" % (before, after, show(0xD192, v)),
            {"wrote": new, "original": sim0, "before": before, "after": after, "value_after": v})
    print("  After automatic cleanup finishes, check the original recipe and unsaved markers on the camera; persistence is not guaranteed by readback.")


# The two encodings of a name-less 0xD18D: the standard one-byte empty string, and the count-plus-NUL
# form an unnamed X-T50 bank answers.
EMPTY_NAME_FORMS = {b"\x00": "one-byte empty", b"\x01\x00\x00": "count and NUL"}


def _name_form(cam, original_raw):
    """Read 0xD18D and say which form it holds; the finding records the form, not the name."""
    rc, text = cam.get_str(BANK_NAME)
    if rc != 0x2001 or text is None:
        return rc, None
    raw = cam.string_bytes[BANK_NAME]
    return rc, EMPTY_NAME_FORMS.get(raw) or ("original" if raw == original_raw else "other")


def _write_name_bytes(cam, raw, original_raw):
    """Write 0xD18D as exact bytes: one of the two empty encodings, or the bank's own original."""
    if raw not in EMPTY_NAME_FORMS and raw != original_raw:
        raise PTPError("only an empty encoding or the bank's original name bytes may be written")
    cam._check_write_scope(BANK_NAME)
    rc, _, _ = cam.transact(OP_SET_PROP, [BANK_NAME], raw)
    label = raw.hex() if raw in EMPTY_NAME_FORMS else "original"
    if cam.experiment is not None:
        cam.experiment.outcomes.append({"code": BANK_NAME, "wrote": label, "rc": rc, "ok": rc == 0x2001,
                                        "outcome": "accepted" if rc == 0x2001 else "refused"})
    print("    0xD18D name <- %-8s %s" % (label, rc_name(rc)))
    return rc


def test_empty_name(cam, args, rep):
    """Write. Does an empty name hold when a bank setting is written after it, and does 01 00 00 clear a name too?"""
    k = need_bank(args)
    print("  Settles: whether 0xD18D = 00 still reads empty after a bank-setting write follows it, and whether")
    print("  the three-byte form 01 00 00 clears a name as well. No menu steps.")
    saved, _ = _backup_and_select(cam, k)
    if not saved["name"]:
        raise PTPError("C%d has no name, so a cleared name would not show; name the bank on the camera first" % k)
    original_raw = bytes.fromhex(saved["name_raw"])
    sim = saved["props"][0xD192]
    other = 2 if sim != 2 else 1
    forms = {}
    for raw in EMPTY_NAME_FORMS:
        result = forms[raw.hex()] = {}

        def read(step):
            rc, form = _name_form(cam, original_raw)
            result[step] = form
            print("      name reads: %s" % (form or "unavailable (%s)" % rc_name(rc)))

        print("  %s, then a Film Simulation write and back, then the original name:" % EMPTY_NAME_FORMS[raw])
        result["write_rc"] = _write_name_bytes(cam, raw, original_raw)
        read("written")
        cam.write_verify(0xD192, other)
        read("after_setting")
        cam.write_verify(0xD192, sim)
        read("after_setting_back")
        result["restore_rc"] = _write_name_bytes(cam, original_raw, original_raw)
        read("name_restored")

    def said(key):
        result = forms[key]
        return "%s %s; reads %s, after a setting write %s, after writing it back %s" % (
            key, rc_name(result["write_rc"]), result["written"], result["after_setting"], result["after_setting_back"])
    rep.add("empty-name", "%s. %s" % (said("00"), said("010000")),
            {"bank": k, "setting": "0xD192", "setting_values": [sim, other], "forms": forms})


TESTS = {
    "filmsim": (test_filmsim, "read-only", "menu sweep of the disputed film simulation values (4–10, 13/14)"),
    "d1a3": (test_d1a3, "read-only", "which property moves with LMO, Long Exposure NR, Color Space"),
    "dr-placeholder": (test_dr_placeholder, "read-only", "DR and priority readbacks through Off/On/Off on a DR100 bank"),
    "d1a5": (test_d1a5, "read-only", "does 0xD1A5 follow the bank select (needs --other-bank)"),
    "selector": (test_selector, "selector only", "does 0xD18C survive a cable reconnect"),
    "dr-zero": (test_dr_zero, "WRITE", "is 0 accepted on 0xD190"),
    "toning": (test_toning, "WRITE", "zero / off-grid / ±180 on 0xD193–0xD194 under ACROS, then Sepia"),
    "name-last": (test_name_last, "WRITE", "settings, then name, then a power cycle"),
    "heif": (test_heif, "WRITE", "Clarity while the format is HEIF, then JPEG"),
    "mono-colour": (test_mono_colour, "WRITE", "colour-only properties under ACROS"),
    "d1a5-write": (test_d1a5_write, "WRITE", "write Image Size on one bank, read 0xD1A5 on another (needs --other-bank)"),
    "d1a3-meaning": (test_d1a3_meaning, "read-only", "which of 1/2 is ON for LMO and sRGB for Color Space"),
    "wb-sweep": (test_wb_sweep, "read-only", "Auto White Priority, Ambience Priority, Underwater, Shade, Fluorescent 1, Incandescent, Custom 1"),
    "imagesize-sweep": (test_imagesize_sweep, "read-only", "Image Size values against the size x aspect decode"),
    "imagequality-sweep": (test_imagequality_sweep, "read-only", "0xD18F for FINE, NORMAL, with and without RAW"),
    "d1a5-live": (test_d1a5_live, "one write", "change the LIVE Image Size with no bank saved; does 0xD1A5 follow (needs --other-bank)"),
    "selector-reset": (test_selector_reset, "selector only", "does a bank change on the body reset 0xD18C (needs --other-bank)"),
    "heif-scope": (test_heif_scope, "WRITE", "is the HEIF gate on Clarity camera-wide or per bank (needs --other-bank)"),
    "iso-threshold": (test_iso_threshold, "WRITE", "DR200/DR400 acceptance at ISO 125, 250, 500"),
    "d18e-gates": (test_d18e_gates, "WRITE", "Digital Tele-Converter and HDR as Image Size gates"),
    "no-name-control": (test_no_name_control, "WRITE", "is a setting written with no name lost at a power cycle"),
    "commit-fresh-pull": (test_commit_fresh_pull, "WRITE", "fresh power-on, one property, no name, cable pulled, power cycle (run alone)"),
    "commit-fresh-close": (test_commit_fresh_close, "WRITE", "fresh power-on, one property, no name, session closed, power cycle (run alone)"),
    "live-vs-saved": (test_live_vs_saved, "read-only", "does reading the body's current bank show its saved or its live state (needs --other-bank)"),
    "working-copy": (test_working_copy, "WRITE", "does the camera's reset discard a bare write; does name-first or name-last save it"),
    "markers": (test_markers, "WRITE", "where the camera marks a modified bank, for each way of changing it, judged by its reset"),
    "bank-switch": (test_bank_switch, "WRITE", "where a USB write lands, judged by switching the body away and back and reading the Q menu (needs --other-bank)"),
    "name-timing": (test_name_timing, "WRITE", "does a name write clear the camera's red dot when sent straight after, 10 s after, in a new PTP session, or after a reconnect"),
    "reset-check": (test_reset_check, "WRITE", "what RESET THE CHANGES does to a USB write, with and without a name, and what opening the item does"),
    "power-dot": (test_power_dot, "WRITE", "does the red dot a push leaves survive a power cycle"),
    "empty-name": (test_empty_name, "WRITE", "does 0xD18D = 00 stay empty after a bank-setting write; does 01 00 00 clear a name"),
}

def record_test_context(cam, args, name):
    value = getattr(args, "auto_update", None)
    if value is None:
        value = ask("Before this trial, check AUTO UPDATE CUSTOM SETTING without changing it. Type on, off, or unknown (reconnect the same camera if you unplug to check).")
    value = value.strip().lower()
    auto = value if value in ("on", "off") else "unknown"
    state = getattr(args, "camera_state", None)
    if state is None:
        state = ask("Record the camera's shooting bank, ISO, JPEG/HEIF format, and any relevant mode/unsaved marker. Use unknown for anything not checked. Keep AUTO UPDATE unchanged during this trial.")
    context = {"test": name, "auto_update": auto, "auto_update_reported": value,
               "camera_state_reported": state, "bank": args.bank,
               "model": (cam.info or {}).get("model"), "firmware": (cam.info or {}).get("device_version"),
               "evidence": "operator-reported state; protocol observations recorded separately"}
    cam.log.append({"event": "experiment context", **context})
    print("  AUTO UPDATE: %s; camera state: %s" % (auto, state))
    return context


def guarded_test(name, fn, kind):
    @wraps(fn)
    def guarded(cam, args, rep):
        k = need_bank(args)
        if name in {"d1a5", "d1a5-write", "d1a5-live", "selector-reset", "heif-scope", "live-vs-saved", "bank-switch"}:
            other = getattr(args, "other_bank", None)
            if type(other) is not int or not 1 <= other <= 255 or other == k:
                raise PTPError("this test needs a distinct valid --other-bank")
        rep.context = record_test_context(cam, args, name)
        if name in {"d1a5-live", "live-vs-saved"} and rep.context["auto_update"] != "off":
            raise PTPError("this unsaved-live experiment requires operator-confirmed AUTO UPDATE off; rerun after setting it")
        with preserve_selector(cam):
            if kind not in {"WRITE", "one write"}:
                return fn(cam, args, rep)
            banks = [k] + ([args.other_bank] if name == "heif-scope" else [])
            exp = BankExperiment(cam, banks, live=name in {"d1a5-write", "d1a5-live"})
            start = len(rep.findings)
            try:
                with exp:
                    fn(cam, args, rep)
            finally:
                for finding in rep.findings[start:]:
                    finding["write_outcomes"] = list(exp.outcomes)
                    finding["cleanup"] = list(exp.cleanup)
                    if any(not r.get("ok", True) for r in exp.outcomes):
                        finding["verdict"] = "trial contains refused, mismatched or unavailable writes; interpret only the raw observations"
                if name in {"heif", "heif-scope", "iso-threshold", "d18e-gates", "d1a5-live", "markers", "working-copy", "reset-check", "power-dot", "bank-switch", "name-timing"}:
                    print("  Manual camera state (ISO, format, modes, shooting bank, unsaved markers) is outside automatic cleanup. Restore/check it on the camera, including after interruption.")
    return guarded


for _test_name, (_test_fn, _test_kind, _test_desc) in list(TESTS.items()):
    _guarded = guarded_test(_test_name, _test_fn, _test_kind)
    TESTS[_test_name] = (_guarded, _test_kind, _test_desc)
    globals()[_test_fn.__name__] = _guarded


CONFIRM_ORDER = ["d1a3-meaning", "wb-sweep", "imagesize-sweep", "imagequality-sweep", "d1a5-live", "selector-reset",
                 "heif-scope", "iso-threshold", "d18e-gates", "no-name-control"]


# ----------------------------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------------------------

def cmd_info(cam, args):
    i = cam.info
    print("  model %s  firmware %s  vendor extension 0x%08X %r" % (
        i["model"], i["device_version"], i["vendor_extension_id"], i["vendor_extension_desc"]))
    print("  DeviceInfo %d bytes; %d operations, %d events, %d properties" % (
        i["length"], len(i["operations"]), len(i["events"]), len(i["properties"])))
    bank_block = [p for p in i["properties"] if BANK_SELECT <= p <= BANK_LAST]
    print("  bank selector/name/settings advertised: %d of 25" % len(bank_block))
    for code in (0xD186, 0xD187):
        rc, s = cam.get_str(code)
        print("  0x%04X -> %s" % (code, repr(s) if s is not None else rc_name(rc)))
    n, original = cam.bank_count()
    print("  banks selectable: %d (selector was %s)" % (n, show(BANK_SELECT, original)))


def cmd_dump(cam, args):
    n, original = cam.bank_count()
    banks = []
    for k in range(1, n + 1):
        b = cam.read_bank(k)
        print_bank(b, "C%d" % k)
        banks.append(bank_to_json(cam, b))
    if original is not None:
        cam.set_u16(BANK_SELECT, original)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(banks, f, indent=2)
        print("  written: %s" % args.out)
    return banks


def cmd_backup(cam, args):
    k = need_bank(args)
    bank = cam.read_bank(k)
    print_bank(bank, "C%d" % k)
    save_backup(cam, bank)


def unique_json_object(pairs):
    """Reject duplicate keys at every nesting level before a restore touches the camera."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise PTPError("duplicate JSON key in snapshot: %r" % key)
        result[key] = value
    return result


def cmd_restore(cam, args):
    k = need_bank(args)
    try:
        with open(args.file) as f:
            document = json.load(f, object_pairs_hook=unique_json_object)
        saved = json_to_bank(document)
    except (OSError, ValueError, TypeError) as e:
        raise PTPError("cannot read a valid bank snapshot: %s" % e) from e
    if saved["bank"] != k:
        raise PTPError("snapshot target differs from --bank; cross-bank restore is not supported")
    if any(document.get(key) != (cam.info or {}).get(info_key) for key, info_key in
           (("model", "model"), ("firmware", "device_version"))):
        raise PTPError("snapshot model/firmware differs; restore refused (matching metadata alone does not prove physical identity)")
    with preserve_selector(cam):
        with BankExperiment(cam, [k], keep_on_success=True):
            result = restore_bank(cam, saved)
            if not result["exact"]:
                raise PTPError("requested restore was not exact; rolling back to the pre-operation snapshot")
    return result


def cmd_sweep(cam, args):
    k = need_bank(args)
    before = cam.read_bank(k)
    print_bank(before, "C%d" % k)
    while True:
        try:
            menu_prompt("change ONE item in C%d's saved settings and save it (Ctrl-C here to stop)." % k)
        except KeyboardInterrupt:
            print()
            return
        after = cam.read_bank(k)
        print_diff(diff_banks(before, after))
        before = after


def parse_probe_writes(items):
    """Validate the entire list before even changing the selector."""
    writes = []
    for item in items:
        code_s, separator, value_s = item.partition("=")
        try:
            if not separator:
                raise ValueError("expected CODE=VALUE")
            code = int(code_s, 16)
            if code not in BANK_PROPS and code != BANK_NAME:
                raise ValueError("only bank name/settings are allowed; selectors and live properties are forbidden")
            if code == BANK_NAME:
                ptp_string(value_s)
                value = value_s
            else:
                value = int(value_s, 0)
                if not -32768 <= value <= 65535:
                    raise ValueError("value outside signed/raw u16 range")
                value &= 0xFFFF
        except (ValueError, UnicodeError) as e:
            raise PTPError("invalid probe write %r: %s" % (item, e)) from e
        writes.append((code, value))
    if not writes:
        raise PTPError("probe requires at least one write")
    return writes


def cmd_probe(cam, args):
    writes = parse_probe_writes(args.writes)
    k = need_bank(args)
    rows = []
    with preserve_selector(cam):
        with BankExperiment(cam, [k], keep_on_success=getattr(args, "no_restore", False)) as exp:
            original_grain = exp.banks[k]["props"][0xD195]
            if original_grain in (6, 7) and any(code == 0xD195 and value != original_grain for code, value in writes):
                raise PTPError("remembered grain size cannot be restored exactly; the whole probe list is refused")
            for code, value in writes:
                if code == BANK_NAME:
                    rc = cam.set_str(BANK_NAME, value)
                    read_rc, back = cam.get_str(BANK_NAME)
                    row = {"code": code, "wrote": value, "rc": rc, "read": back,
                           "ok": rc == 0x2001 and read_rc == 0x2001 and back == value}
                    print("    name <- %r  %s  reads %r" % (value, rc_name(rc), back))
                else:
                    row = cam.write_verify(code, value)
                rows.append(row)
            if getattr(args, "no_restore", False) and any(not r["ok"] for r in rows):
                raise PTPError("probe had refused/mismatched/unverified writes; rolling back despite --no-restore")
    return rows


def run_tests(cam, args, names):
    rep = Report()
    for name in names:
        fn, kind, desc = TESTS[name]
        print()
        print("== %s (%s): %s" % (name, kind, desc))
        try:
            fn(cam, args, rep)
        except SkipTest:
            rep.add(name, "skipped")
            if cam.cleanup_failed or cam.write_uncertain:
                raise PTPError("skipped trial left cleanup/delivery unresolved; sequence stopped")
        except PTPError as e:
            rep.add(name, "ABORTED: %s" % e)
            rep.findings[-1]["status"] = "aborted"
            print("  inspect cleanup results and immutable backups before attempting any further write")
            if cam.write_uncertain or cam.cleanup_failed:
                raise
        except KeyboardInterrupt:
            rep.add(name, "interrupted")
            raise
    print()
    print("== findings")
    for f in rep.findings:
        print("  %-14s %s" % (f["test"], f["verdict"]))
    return rep.findings


def cmd_test(cam, args):
    return run_tests(cam, args, args.tests)


GUIDED_ORDER = ["filmsim", "d1a3", "dr-placeholder", "selector",
                "dr-zero", "toning", "mono-colour", "heif", "d1a5-write", "name-last"]


def cmd_guided(cam, args):
    k = need_bank(args)
    if args.other_bank is None:
        sys.exit("guided needs --other-bank M as well: a distinct second bank (heif-scope writes and backs up both banks)")
    order = CONFIRM_ORDER if args.set == "confirm" else GUIDED_ORDER
    names = [n for n in order if n not in (args.skip or [])]
    print()
    print("Guided run on %s fw %s. Test bank C%d; second bank C%d. Write tests preflight and back up every target, then attempt verified cleanup." % (
        cam.info["model"], cam.info["device_version"], k, args.other_bank))
    print("Order: %s" % ", ".join(names))
    print("At any prompt, type s and Enter to skip that test. Read recovery requires confirmation of the same camera. Uncertain writes stop without replay.")
    print()
    print("== info")
    cmd_info(cam, args)
    print()
    print("== dump of every bank (before anything is written)")
    args.out = None
    banks = cmd_dump(cam, args)
    findings = run_tests(cam, args, names)
    print()
    print("== dump of every bank (after)")
    banks_after = cmd_dump(cam, args)
    return {"findings": findings, "banks_before": banks, "banks_after": banks_after}


def selector_guarded(fn):
    @wraps(fn)
    def guarded(cam, args):
        with preserve_selector(cam):
            return fn(cam, args)
    return guarded


for _command_name in ("cmd_info", "cmd_dump", "cmd_backup", "cmd_sweep"):
    globals()[_command_name] = selector_guarded(globals()[_command_name])


# ----------------------------------------------------------------------------------------------
# Self-test (no camera)
# ----------------------------------------------------------------------------------------------

def selftest():
    assert container(1, 0x1016, 3, params_payload([0xD18C])) == bytes.fromhex("10000000 0100 1610 03000000 8CD10000".replace(" ", ""))
    assert ptp_string("C1") == bytes.fromhex("03 4300 3100 0000".replace(" ", ""))
    assert ptp_string("") == b"\x00"
    assert parse_ptp_string(ptp_string("SAVEPCAP"))[0] == "SAVEPCAP"
    assert parse_ptp_string(b"\x00")[0] == ""
    # DeviceInfo round trip
    def arr(vals):
        return struct.pack("<I", len(vals)) + b"".join(struct.pack("<H", v) for v in vals)
    di = (struct.pack("<HIH", 100, 6, 0) + ptp_string("fujifilm.co.jp: 1.0; ") + struct.pack("<H", 0)
          + arr([0x1001, 0x1002]) + arr([]) + arr([0xD18C, 0xD18D]) + arr([0x3801]) + arr([0x3801, 0xF802])
          + ptp_string("FUJIFILM") + ptp_string("X-T50") + ptp_string("1.32") + ptp_string("SERIAL"))
    info = parse_device_info(di)
    assert info["model"] == "X-T50" and info["device_version"] == "1.32" and info["properties"] == [0xD18C, 0xD18D]
    assert "SERIAL" not in json.dumps(info)
    assert s16(0xFFF6) == -10 and s16(0x0014) == 20
    assert same_meaning(0xD195, 1, 6) and same_meaning(0xD195, 1, 7) and not same_meaning(0xD195, 2, 6)
    # restore planner: priority off -> 0xD191 before 0xD190; Kelvin skipped when WB is not Kelvin; grain 6 -> 1
    props = {c: 0 for c in BANK_PROPS}
    props.update({0xD18E: 7, 0xD18F: 4, 0xD190: 100, 0xD191: 0, 0xD192: 11, 0xD195: 6, 0xD199: 4, 0xD19C: 5300})
    assert len(BANK_PROPS) == 23 and LIVE_IMAGE_SIZE not in BANK_PROPS
    plan = restore_plan(props)
    order = [c for c, v, n in plan if not n.startswith("skip")]
    assert order.index(0xD191) < order.index(0xD190), order
    assert order.index(0xD199) < order.index(0xD19A) < order.index(0xD19B)
    assert dict((c, n) for c, v, n in plan)[0xD19C].startswith("skip")
    assert dict((c, n) for c, v, n in plan)[0xD193].startswith("skip")
    assert dict((c, v) for c, v, n in plan)[0xD195] == 1
    assert set(order) == set(BANK_PROPS) - {0xD193, 0xD194, 0xD19C}
    # priority on -> Dynamic Range and tones before 0xD191, which is last; Color skipped on ACROS; Kelvin written
    props.update({0xD191: 0x8000, 0xD192: 12, 0xD199: 0x8007})
    plan = restore_plan(props)
    order = [c for c, v, n in plan if not n.startswith("skip")]
    assert order[-1] == 0xD191 and order.index(0xD190) < order.index(0xD191) and order.index(0xD19E) < order.index(0xD191)
    assert order.index(0xD199) < order.index(0xD19C) < order.index(0xD19A)
    assert 0xD19F not in order and 0xD193 in order
    assert set(order) == set(BANK_PROPS) - {0xD19F}
    # bank JSON round trip
    cam = Camera()
    cam.info = {"model": "X-T50", "device_version": "1.32"}
    bank = {"bank": 3, "name": "A", "props": dict(props), "refused": {}}
    assert json_to_bank(json.loads(json.dumps(bank_to_json(cam, bank))))["props"] == props
    print("selftest: ok")


# ----------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", type=int, help="the bank to read or test (C1 = 1)")
    ap.add_argument("--other-bank", type=int, help="a second bank, for the 0xD1A5 tests")
    ap.add_argument("--auto-update", choices=["on", "off", "unknown"], help="operator-checked AUTO UPDATE state (otherwise asked for each test)")
    ap.add_argument("--camera-state", help="operator-reported shooting bank, ISO, format and relevant modes (otherwise asked)")
    ap.add_argument("--timeout", type=int, default=5000, help="USB timeout in ms (default 5000)")
    ap.add_argument("--log", help="JSON log of every transaction and finding (default bankprobe-<time>.json)")
    ap.add_argument("--verbose", "-v", action="store_true", help="print every transaction")
    ap.add_argument("--list-tests", action="store_true")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--bank", type=int, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    common.add_argument("--other-bank", type=int, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    common.add_argument("--auto-update", choices=["on", "off", "unknown"], default=argparse.SUPPRESS)
    common.add_argument("--camera-state", default=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("info", parents=[common])
    p = sub.add_parser("dump", parents=[common]); p.add_argument("--out")
    sub.add_parser("backup", parents=[common])
    p = sub.add_parser("restore", parents=[common], description="Attempts to restore a saved snapshot to bank N: selects the bank (0xD18C) and, when changes are needed, writes the name (0xD18D) before and after the applicable differing settings (0xD18E–0xD1A4), following dependency rules and skipping inactive fields. Reads the bank back to verify the name and all 23 settings, including skipped fields. The current bank is saved to backups/ first, and a snapshot whose model or firmware differs is refused.")
    p.add_argument("file")
    sub.add_parser("sweep", parents=[common])
    p = sub.add_parser("probe", parents=[common], description="Writes the properties you list to bank N and reads each back: selects the bank (0xD18C), then writes the name (0xD18D) or settings (0xD18E–0xD1A4) given, never the selector or live 0xD1A5; the bank is saved to backups/ first and a restore is attempted afterward, unless --no-restore keeps changes that all verified. A restore is best effort: after a failure or an interruption it can be unavailable, and the backup is retained.")
    p.add_argument("writes", nargs="+", metavar="CODE=VALUE")
    p.add_argument("--no-restore", action="store_true", help="keep the written values when every write verified; a refused, mismatched or unverified write still attempts a restore. A restore is best effort: after a failure or an interruption it can be unavailable, and the backup is retained")
    p = sub.add_parser("test", parents=[common]); p.add_argument("tests", nargs="+", choices=sorted(TESTS))
    p = sub.add_parser("guided", parents=[common]); p.add_argument("--skip", nargs="*", choices=sorted(TESTS), help="tests to leave out")
    p.add_argument("--set", choices=["first", "confirm"], default="first", help="which battery: the first run, or the confirmation round")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.list_tests:
        for name, (fn, kind, desc) in TESTS.items():
            print("  %-14s %-13s %s" % (name, kind, desc))
        return 0
    if args.cmd is None:
        ap.print_help()
        return 2
    if args.cmd == "selftest":
        selftest()
        return 0

    log = []
    cam = Camera(timeout_ms=args.timeout, log=log, verbose=args.verbose)
    findings = None
    extra = {}
    started = _dt.datetime.now()
    stamp = started.strftime("%Y%m%d-%H%M%S")
    transcript = None
    if args.cmd in ("guided", "test"):
        transcript = "bankprobe-%s.txt" % stamp
        sys.stdout = Tee(transcript)
        print("bankprobe transcript %s: %s" % (started.isoformat(timespec="seconds"), " ".join(sys.argv[1:])))
    try:
        cam.open()
        cam.start_session()
        print("connected: %s fw %s" % (cam.info["model"], cam.info["device_version"]))
        if args.cmd == "info":
            cmd_info(cam, args)
        elif args.cmd == "dump":
            cmd_dump(cam, args)
        elif args.cmd == "backup":
            cmd_backup(cam, args)
        elif args.cmd == "restore":
            cmd_restore(cam, args)
        elif args.cmd == "sweep":
            cmd_sweep(cam, args)
        elif args.cmd == "probe":
            cmd_probe(cam, args)
        elif args.cmd == "test":
            findings = cmd_test(cam, args)
        elif args.cmd == "guided":
            extra = cmd_guided(cam, args)
            findings = extra.pop("findings")
    except PTPError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted; if a write test was running, restore the bank from backups/ with the restore command", file=sys.stderr)
        return 130
    finally:
        cam.close()
        path = args.log or "bankprobe-%s.json" % stamp
        with open(path, "w") as f:
            json.dump({"model": (cam.info or {}).get("model"), "firmware": (cam.info or {}).get("device_version"),
                       "started": started.isoformat(timespec="seconds"), "command": sys.argv[1:],
                       "findings": findings, **extra, "transactions": log}, f, indent=1)
        print("log: %s" % path)
        if transcript:
            print("transcript: %s" % transcript)
            print("review and sanitize both files, and anything in backups/, before sharing them: they can hold bank names and recipe contents")
    return 1 if findings and any(f.get("status") == "aborted" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
