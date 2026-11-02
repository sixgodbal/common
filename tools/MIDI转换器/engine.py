# -*- coding: utf-8 -*-
"""MIDI 转换器 —— 合成与编码核心。

不依赖任何外部程序：
- MIDI 解析：内置 SMF（标准 MIDI 文件）解析器，支持 format 0/1/2、节奏变化、延音踏板、弯音
- MIDI 音源：读取 Windows 自带的 GM 音色库 gm.dls（DLS Level 1），用 numpy 离线合成
- 音频读写：soundfile（WAV/MP3/FLAC/OGG）
- MP3 编码：lameenc（优先），缺少时退回 soundfile

所有函数都在后台线程里调用，不要直接碰 tkinter。
"""

import os
import struct
import wave
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import soundfile as _sf
except Exception:  # pragma: no cover - 依赖缺失时给出更友好的提示
    _sf = None

GM_DLS_PATHS = (
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "drivers", "gm.dls"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SysWOW64", "drivers", "gm.dls"),
)

MIDI_EXTS = {".mid", ".midi", ".rmi", ".kar"}
AUDIO_EXTS = {
    ".wav", ".wave", ".mp3", ".flac", ".ogg", ".oga", ".aif", ".aiff",
    ".au", ".w64", ".caf", ".voc", ".snd",
}
SUPPORTED_EXTS = MIDI_EXTS | AUDIO_EXTS

DEFAULT_SR = 44100
MAX_MIDI_SECONDS = 30 * 60
MP3_RATES = {8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000}


def is_midi_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in MIDI_EXTS:
        return True
    if ext in AUDIO_EXTS:
        return False
    try:
        with open(path, "rb") as f:
            head = f.read(12)
        return head[:4] == b"MThd" or (head[:4] == b"RIFF" and head[8:12] == b"RMID")
    except OSError:
        return False


def is_supported(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in SUPPORTED_EXTS:
        return True
    if ext:
        return False
    try:
        with open(path, "rb") as f:
            head = f.read(12)
        return head[:4] in (b"MThd", b"RIFF")
    except OSError:
        return False


# ---------------------------------------------------------------- DLS 音色库
@dataclass
class Sample:
    rate: int
    data: np.ndarray
    loop_start: int = 0
    loop_len: int = 0


@dataclass
class Region:
    key_lo: int
    key_hi: int
    vel_lo: int
    vel_hi: int
    unity: int
    fine: float
    att_db: float
    sample_idx: int
    gain_db: float = 0.0
    has_gain: bool = False
    loop_start: int = 0
    loop_len: int = 0

    def matches(self, key: int, vel: int) -> bool:
        return self.key_lo <= key <= self.key_hi and self.vel_lo <= vel <= self.vel_hi


@dataclass
class Instrument:
    name: str
    bank: int
    program: int
    is_drum: bool
    regions: List[Region]
    gain_db: float = 0.0


def _chunks(data: bytes, start: int, end: int):
    """遍历 RIFF chunk（只做一层；LIST 的子块由调用方继续展开）。"""
    p = start
    while p + 8 <= end:
        cid = data[p:p + 4]
        size = struct.unpack_from("<I", data, p + 4)[0]
        body = p + 8
        stop = min(body + size, end)
        typ = data[body:body + 4] if cid == b"LIST" and size >= 4 else None
        yield cid, typ, body, stop
        p = body + size + (size & 1)


def _find_lists(data: bytes, start: int, end: int, types, out=None):
    """递归查找指定类型的 LIST（如 ins / rgn / wave / lart）。"""
    if out is None:
        out = []
    for cid, typ, a, b in _chunks(data, start, end):
        if typ in types:
            out.append((typ, a, b))
        if cid == b"LIST":
            _find_lists(data, a + 4, b, types, out)
    return out


def _parse_art1(data: bytes, a: int, b: int) -> Tuple[Optional[float], Optional[float]]:
    """从 art1 里取静态增益 / 声像连接（source = 0）。"""
    gain = None
    pan = None
    try:
        _cb, n = struct.unpack_from("<II", data, a)
        for k in range(min(n, 64)):
            off = a + 8 + k * 12
            src, _ctl, dst, _tr, scale = struct.unpack_from("<HHHHi", data, off)
            if src != 0:
                continue
            if dst == 0x0104 and gain is None:
                gain = scale / 6553600.0
            elif dst == 0x0105 and pan is None:
                pan = scale / 6553600.0
    except Exception:
        pass
    return gain, pan


class DLSBank:
    """Windows GM DLS 音色库。首次加载约 20~50ms，之后常驻内存。"""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            for p in GM_DLS_PATHS:
                if os.path.isfile(p):
                    path = p
                    break
        if not path or not os.path.isfile(path):
            raise RuntimeError("找不到 Windows 自带的音色库 gm.dls")
        self.path = path
        self.waves: List[Sample] = []
        self.melodic: Dict[Tuple[int, int], Instrument] = {}
        self.drums: Dict[int, Instrument] = {}
        self._load()

    def _load(self):
        data = open(self.path, "rb").read()
        if data[:4] != b"RIFF":
            raise RuntimeError("音色库格式不正确")

        waves: List[Sample] = []
        for _typ, a, b in _find_lists(data, 12, len(data), {b"wave"}):
            fmt = None
            raw = None
            for cid, _t, aa, bb in _chunks(data, a + 4, b):
                if cid == b"fmt ":
                    tag, ch, rate, _avg, _align, bits = struct.unpack_from("<HHIIHH", data, aa)
                    fmt = (tag, ch, rate, bits)
                elif cid == b"data":
                    raw = data[aa:bb]
            if not fmt or raw is None or fmt[0] != 1:
                continue
            arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            if fmt[1] == 2:
                arr = arr.reshape(-1, 2).mean(axis=1)
            waves.append(Sample(fmt[2], arr))
        self.waves = waves

        for _typ, a, b in _find_lists(data, 12, len(data), {b"ins "}):
            name = ""
            bank_raw = program = 0
            inst_gain = 0.0
            regions: List[Region] = []
            for cid, tt, aa, bb in _chunks(data, a + 4, b):
                if cid == b"insh":
                    _nreg, bank_raw, program = struct.unpack_from("<III", data, aa)
                elif cid == b"LIST" and tt == b"INFO":
                    for c2, _t2, a2, b2 in _chunks(data, aa + 4, bb):
                        if c2 == b"INAM":
                            name = data[a2:b2].split(b"\0")[0].decode("latin1", "replace").strip()
                elif cid == b"LIST" and tt == b"lart":
                    for c2, _t2, a2, b2 in _chunks(data, aa + 4, bb):
                        if c2 == b"art1":
                            g, _p = _parse_art1(data, a2, b2)
                            if g is not None:
                                inst_gain = g
                elif cid == b"LIST" and tt == b"lrgn":
                    for _c2, t2, a2, b2 in _chunks(data, aa + 4, bb):
                        if t2 != b"rgn ":
                            continue
                        r = {}
                        for c3, t3, a3, b3 in _chunks(data, a2 + 4, b2):
                            if c3 == b"rgnh":
                                r["key_lo"], r["key_hi"], r["vel_lo"], r["vel_hi"] = struct.unpack_from("<4H", data, a3)
                            elif c3 == b"wsmp":
                                _cb, unity, fine, att, _opts, loops = struct.unpack_from("<IHHiII", data, a3)
                                if fine >= 32768:
                                    fine -= 65536
                                r.update(unity=unity, fine=float(fine), att=att)
                                if loops:
                                    _lcb, _lt, ls, ll = struct.unpack_from("<IIII", data, a3 + 20)
                                    r.update(loop_start=ls, loop_len=ll)
                            elif c3 == b"wlnk":
                                r["sample_idx"] = struct.unpack_from("<I", data, a3 + 8)[0]
                            elif c3 == b"LIST" and t3 == b"lart":
                                for c4, _t4, a4, b4 in _chunks(data, a3 + 4, b3):
                                    if c4 == b"art1":
                                        g, p = _parse_art1(data, a4, b4)
                                        if g is not None:
                                            r["gain_db"] = g
                                            r["has_gain"] = True
                                        if p is not None:
                                            r["pan"] = p
                        if "sample_idx" not in r:
                            continue
                        sidx = r["sample_idx"]
                        if sidx >= len(self.waves):
                            continue
                        regions.append(Region(
                            key_lo=r.get("key_lo", 0), key_hi=r.get("key_hi", 127),
                            vel_lo=r.get("vel_lo", 0), vel_hi=r.get("vel_hi", 127),
                            unity=r.get("unity", 60), fine=r.get("fine", 0.0),
                            att_db=r.get("att", 0) / 6553600.0,
                            sample_idx=sidx,
                            gain_db=r.get("gain_db", 0.0),
                            has_gain=r.get("has_gain", False),
                            loop_start=r.get("loop_start", 0),
                            loop_len=r.get("loop_len", 0),
                        ))
            is_drum = bool(bank_raw & 0x80000000)
            bank = 0 if is_drum else (bank_raw >> 8)
            inst = Instrument(name, bank, program, is_drum, regions, inst_gain)
            if is_drum:
                self.drums.setdefault(program, inst)
            else:
                self.melodic.setdefault((bank, program), inst)

    def pick(self, bank: int, program: int, is_drum: bool, key: int, vel: int):
        if is_drum:
            inst = self.drums.get(program) or self.drums.get(0)
        else:
            inst = self.melodic.get((bank, program)) or self.melodic.get((0, program))
            if inst is None:
                inst = self.melodic.get((0, 0))
        if inst is None or not inst.regions:
            return None, None
        reg = None
        for r in inst.regions:
            if r.matches(key, vel):
                reg = r
                break
        if reg is None:
            if is_drum:
                return inst, None
            reg = min(inst.regions, key=lambda r: (
                abs(key - (r.key_lo + r.key_hi) / 2.0)
                + (0 if r.vel_lo <= vel <= r.vel_hi else 1000)
            ))
        return inst, reg


# ---------------------------------------------------------------- MIDI 解析
@dataclass
class Note:
    start: float
    end: float
    channel: int
    key: int
    vel: int
    program: int
    bank: int
    bend_range: float = 2.0
    vol: int = 100
    pan: int = 64
    expr: int = 127


@dataclass
class Song:
    notes: List[Note]
    duration: float
    bend_events: Dict[int, List[Tuple[float, float]]] = field(default_factory=dict)
    track_names: List[str] = field(default_factory=list)
    ppq: int = 96


def _read_varlen(data: bytes, p: int) -> Tuple[int, int]:
    v = 0
    for _ in range(4):
        b = data[p]
        p += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            break
    return v, p


def parse_midi(path: str) -> Song:
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] == b"RIFF" and data[8:12] == b"RMID":
        p = 12
        while p + 8 <= len(data):
            cid = data[p:p + 4]
            size = struct.unpack_from("<I", data, p + 4)[0]
            if cid == b"data":
                data = data[p + 8:p + 8 + size]
                break
            p += 8 + size + (size & 1)
    if data[:4] != b"MThd":
        raise ValueError("不是 MIDI 文件")
    hlen = struct.unpack_from(">I", data, 4)[0]
    _fmt, ntrks, div = struct.unpack_from(">HHH", data, 8)
    p = 8 + hlen
    ppq = div if not div & 0x8000 else 0
    smpte = None
    if div & 0x8000:
        fps = 256 - (div >> 8)
        tpf = div & 0xFF
        smpte = max(1, fps * tpf)

    events = []
    tempo_events = []
    track_names = []
    order = 0
    for _ti in range(ntrks):
        if p + 8 > len(data):
            break
        cid = data[p:p + 4]
        size = struct.unpack_from(">I", data, p + 4)[0]
        body = p + 8
        end = min(body + size, len(data))
        p = body + size
        if cid != b"MTrk":
            continue
        q = body
        tick = 0
        running = None
        while q < end:
            delta, q = _read_varlen(data, q)
            tick += delta
            if q >= end:
                break
            b = data[q]
            if b & 0x80:
                running = b
                q += 1
            else:
                b = running
                if b is None:
                    break
            status = b & 0xF0
            if b == 0xFF:
                if q >= end:
                    break
                mtype = data[q]
                q += 1
                ln, q = _read_varlen(data, q)
                payload = data[q:q + ln]
                q += ln
                if mtype == 0x51 and ln == 3:
                    tempo_events.append((tick, (payload[0] << 16) | (payload[1] << 8) | payload[2]))
                elif mtype == 0x03:
                    track_names.append(payload.decode("utf-8", "replace"))
                continue
            if b in (0xF0, 0xF7):
                ln, q = _read_varlen(data, q)
                q += ln
                continue
            ch = b & 0x0F
            if status in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                if q + 1 >= end:
                    break
                d1, d2 = data[q], data[q + 1]
                q += 2
                if status == 0x90 and d2 > 0:
                    events.append((tick, order, "on", ch, d1, d2))
                elif status == 0x80 or (status == 0x90 and d2 == 0):
                    events.append((tick, order, "off", ch, d1, 0))
                elif status == 0xB0:
                    events.append((tick, order, "cc", ch, d1, d2))
                elif status == 0xE0:
                    val = (d1 | (d2 << 7)) - 8192
                    events.append((tick, order, "bend", ch, val, 0))
            elif status in (0xC0, 0xD0):
                if q >= end:
                    break
                d1 = data[q]
                q += 1
                if status == 0xC0:
                    events.append((tick, order, "prog", ch, d1, 0))
            order += 1

    events.sort(key=lambda e: (e[0], e[1]))
    tempo_events.sort()

    tempo = [(0, 500000)]
    if tempo_events:
        tempo = []
        last_us = None
        for t, us in tempo_events:
            if us == last_us:
                continue
            tempo.append((t, us))
            last_us = us
        if not tempo or tempo[0][0] != 0:
            tempo.insert(0, (0, 500000))
    tempo_times = []
    sec = 0.0
    for i, (t, us) in enumerate(tempo):
        if i:
            pt, pus = tempo[i - 1]
            if smpte:
                sec += (t - pt) / smpte
            else:
                sec += (t - pt) * pus / (1e6 * ppq)
        tempo_times.append((t, sec, us))

    def tick_to_sec(t: int) -> float:
        if smpte:
            return t / smpte
        lo, hi = 0, len(tempo_times)
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if tempo_times[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        st, ss, us = tempo_times[lo]
        return ss + (t - st) * us / (1e6 * ppq)

    def make_state():
        return {
            "prog": 0, "bank": 0, "vol": 100, "pan": 64, "expr": 127,
            "bend": 0.0, "range": 2.0, "rpn": (127, 127), "data": 0,
        }

    ch_state = {}
    active = {}
    sustain = {}
    bend_events = {}
    notes: List[Note] = []
    last_sec = 0.0

    def state(ch):
        s = ch_state.get(ch)
        if s is None:
            s = make_state()
            ch_state[ch] = s
        return s

    def finalize(entry, t):
        notes.append(Note(
            start=entry["start"],
            end=max(entry["start"] + 0.001, t),
            channel=entry["ch"], key=entry["key"], vel=entry["vel"],
            program=entry["prog"], bank=entry["bank"], bend_range=entry["range"],
            vol=entry["vol"], pan=entry["pan"], expr=entry["expr"],
        ))

    def note_on(ch, key, vel, t):
        s = state(ch)
        active.setdefault((ch, key), []).append({
            "start": t, "ch": ch, "key": key, "vel": vel,
            "prog": s["prog"], "bank": s["bank"], "range": s["range"],
            "vol": s["vol"], "pan": s["pan"], "expr": s["expr"], "off": None,
        })

    def note_off(ch, key, t, immediate=False):
        stack = active.get((ch, key))
        if not stack:
            return
        entry = None
        for n in reversed(stack):
            if n["off"] is None:
                entry = n
                break
        if entry is None:
            return
        entry["off"] = t
        if immediate or not sustain.get(ch):
            finalize(entry, t)
            stack.remove(entry)

    def pedal_up(ch, t):
        for (c, _key), stack in list(active.items()):
            if c != ch:
                continue
            for entry in list(stack):
                if entry["off"] is not None:
                    finalize(entry, t)
                    stack.remove(entry)

    def all_off(ch, t):
        for (c, _key), stack in list(active.items()):
            if c != ch:
                continue
            for entry in list(stack):
                finalize(entry, t)
            stack.clear()

    for tick, _ord, kind, ch, d1, d2 in events:
        t = tick_to_sec(tick)
        if t > last_sec:
            last_sec = t
        if kind == "on":
            note_on(ch, d1, d2, t)
        elif kind == "off":
            note_off(ch, d1, t)
        elif kind == "prog":
            state(ch)["prog"] = d1
        elif kind == "bend":
            s = state(ch)
            s["bend"] = d1 / 8192.0 * s["range"]
            bend_events.setdefault(ch, []).append((t, s["bend"]))
        elif kind == "cc":
            s = state(ch)
            if d1 == 0:
                s["bank"] = d2
            elif d1 == 7:
                s["vol"] = d2
            elif d1 == 10:
                s["pan"] = d2
            elif d1 == 11:
                s["expr"] = d2
            elif d1 == 64:
                if d2 >= 64:
                    sustain[ch] = True
                else:
                    sustain[ch] = False
                    pedal_up(ch, t)
            elif d1 == 101:
                s["rpn"] = (d2, s["rpn"][1])
            elif d1 == 100:
                s["rpn"] = (s["rpn"][0], d2)
            elif d1 == 6:
                if s["rpn"] == (0, 0):
                    s["range"] = float(d2)
                    s["bend"] = 0.0
            elif d1 in (120, 123):
                all_off(ch, t)

    end_t = last_sec + 0.3
    for _key, stack in list(active.items()):
        for entry in list(stack):
            finalize(entry, max(end_t, entry["start"] + 0.05))
    active.clear()

    for notes_list in bend_events.values():
        notes_list.sort()

    return Song(notes, last_sec, bend_events, track_names, ppq)


# ---------------------------------------------------------------- 合成器
def _family(program: int, is_drum: bool) -> dict:
    if is_drum:
        return {"attack": 0.001, "release": 0.06, "decay": 0.0, "one_shot": True}
    p = program
    if p < 8:
        return {"attack": 0.002, "release": 0.20, "decay": 2.8}
    if p < 16:
        return {"attack": 0.002, "release": 0.25, "decay": 3.0}
    if p < 24:
        return {"attack": 0.008, "release": 0.12, "decay": 0.0}
    if p < 32:
        return {"attack": 0.002, "release": 0.12, "decay": 2.4}
    if p < 40:
        return {"attack": 0.005, "release": 0.12, "decay": 3.5}
    if p < 48:
        return {"attack": 0.070, "release": 0.45, "decay": 0.0}
    if p < 56:
        return {"attack": 0.090, "release": 0.50, "decay": 0.0}
    if p < 64:
        return {"attack": 0.045, "release": 0.18, "decay": 0.0}
    if p < 72:
        return {"attack": 0.035, "release": 0.18, "decay": 0.0}
    if p < 80:
        return {"attack": 0.045, "release": 0.15, "decay": 0.0}
    if p < 88:
        return {"attack": 0.012, "release": 0.15, "decay": 0.0}
    if p < 96:
        return {"attack": 0.220, "release": 0.70, "decay": 0.0}
    if p < 104:
        return {"attack": 0.070, "release": 0.35, "decay": 0.0}
    if p < 112:
        return {"attack": 0.004, "release": 0.25, "decay": 2.6}
    if p < 120:
        return {"attack": 0.001, "release": 0.15, "decay": 1.6}
    return {"attack": 0.010, "release": 0.30, "decay": 0.0}


class Synth:
    def __init__(self, bank: Optional[DLSBank] = None):
        self.bank = bank or DLSBank()

    def render(self, song: Song, sample_rate: int = DEFAULT_SR, progress=None):
        sr = int(sample_rate)
        total_n = int(max(1.5, song.duration + 2.0) * sr)
        mix = np.zeros((total_n, 2), dtype=np.float32)
        notes = sorted(song.notes, key=lambda n: n.start)
        bend = song.bend_events
        bend_times = {ch: [t for t, _v in evs] for ch, evs in bend.items()}
        two_pi = 1.5707963267948966
        last_pct = -1

        for i, note in enumerate(notes):
            if progress:
                pct = int(i * 100.0 / max(1, len(notes)))
                if pct != last_pct:
                    last_pct = pct
                    progress(pct / 100.0)
            s = int(note.start * sr)
            if s >= total_n:
                continue
            is_drum = note.channel == 9
            inst, reg = self.bank.pick(note.bank, note.program, is_drum, note.key, note.vel)
            if inst is None or reg is None:
                continue
            sample = self.bank.waves[reg.sample_idx]
            nsrc = len(sample.data)
            if nsrc < 4:
                continue
            fam = _family(note.program, is_drum)
            rate_conv = sample.rate / sr

            if fam.get("one_shot"):
                dur = min(6.0, max(0.05, nsrc / float(sample.rate)))
            else:
                dur = max(0.02, note.end - note.start)
            rel = fam["release"]
            n = int((dur + rel) * sr)
            if n < 2:
                continue
            n = min(n, 60 * sr)

            if is_drum:
                base = (2.0 ** (reg.fine / 1200.0)) * rate_conv
            else:
                base = (2.0 ** ((note.key - reg.unity + reg.fine / 100.0) / 12.0)) * rate_conv

            bevs = bend.get(note.channel)
            if bevs and not is_drum:
                lo = bisect_right(bend_times[note.channel], note.start) - 1
                if lo < 0:
                    lo = 0
                ratio = np.full(n, base * (2.0 ** (bevs[lo][1] / 12.0)), dtype=np.float64)
                for bt, bv in bevs[lo + 1:]:
                    if bt >= note.start + dur + rel:
                        break
                    k = max(0, int((bt - note.start) * sr))
                    if k < n:
                        ratio[k:] = base * (2.0 ** (bv / 12.0))
                pos = np.cumsum(ratio)
            else:
                pos = np.arange(n, dtype=np.float64) * base

            looped = (not is_drum) and reg.loop_len > 1 and reg.loop_start + reg.loop_len <= nsrc
            if looped:
                ls = reg.loop_start
                ll = reg.loop_len
                idx_arr = pos.copy()
                over = idx_arr >= ls
                if over.any():
                    idx_arr[over] = ls + np.mod(idx_arr[over] - ls, ll)
            else:
                valid = int(np.searchsorted(pos, nsrc - 1, side="right"))
                if valid < 2:
                    continue
                if valid < n:
                    n = valid
                idx_arr = pos[:n]

            i0 = idx_arr.astype(np.int64)
            frac = (idx_arr - i0).astype(np.float32)
            i1 = i0 + 1
            if looped:
                lend = reg.loop_start + reg.loop_len
                i1[i0 >= lend - 1] = reg.loop_start
            else:
                i1 = np.minimum(i1, nsrc - 1)
            y = sample.data[i0] * (1.0 - frac) + sample.data[i1] * frac

            t = np.arange(n, dtype=np.float32) / sr
            env = np.ones(n, dtype=np.float32)
            a = max(1, int(fam["attack"] * sr))
            if a > 1:
                env[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32)
            decay = fam.get("decay") or 0.0
            if decay > 0 and looped:
                # 循环起点之后继续自然衰减，避免钢琴等长音变成风琴
                loop_t = reg.loop_start / (base * sr)
                if loop_t < dur:
                    k0 = int(loop_t * sr)
                    if k0 < n:
                        env[k0:] *= np.exp(-(t[k0:] - loop_t) / decay).astype(np.float32)
            rel_n = min(n, max(1, int(rel * sr)))
            if rel_n < n:
                k = n - rel_n
                env[k:] *= np.exp(-np.arange(rel_n) / max(1.0, rel_n / 4.0)).astype(np.float32)
            if n > 8:
                fade = min(n, max(2, int(0.005 * sr)))
                env[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
            y *= env

            vel_gain = (note.vel / 127.0) ** 1.5
            vol_gain = max(0.0, min(1.0, note.vol / 127.0)) ** 1.5
            expr_gain = max(0.0, min(1.0, note.expr / 127.0))
            gain_db = reg.gain_db if reg.has_gain else inst.gain_db
            gain_db += reg.att_db
            gain = 10.0 ** (gain_db / 20.0)
            pan = max(0, min(127, note.pan)) / 127.0
            ang = pan * two_pi
            gl = float(np.cos(ang) * 1.4142135623730951)
            gr = float(np.sin(ang) * 1.4142135623730951)
            amp = vel_gain * vol_gain * expr_gain * gain
            y *= amp

            e = min(total_n, s + n)
            m = e - s
            if m <= 1:
                continue
            mix[s:e, 0] += y[:m] * gl
            mix[s:e, 1] += y[:m] * gr

        peak = float(np.max(np.abs(mix))) if total_n else 0.0
        if peak > 1.0:
            mix *= 0.98 / peak
        f = min(total_n, int(0.01 * sr))
        if f > 1:
            mix[:f] *= np.linspace(0.0, 1.0, f, dtype=np.float32)[:, None]
            mix[-f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)[:, None]
        return mix, sr


# ---------------------------------------------------------------- 编码
def _to_int16(mix: np.ndarray) -> np.ndarray:
    return np.clip(mix * 32767.0, -32768, 32767).astype("<i2")


def _write_wav(path: str, mix: np.ndarray, sr: int):
    channels = 1 if mix.ndim == 1 else mix.shape[1]
    step = 1 << 20
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(0, len(mix), step):
            w.writeframes(_to_int16(mix[i:i + step]).tobytes())


def _write_mp3(path: str, mix: np.ndarray, sr: int, bitrate: int):
    channels = 1 if mix.ndim == 1 else int(mix.shape[1])
    try:
        import lameenc
    except Exception:
        if _sf is None:
            raise RuntimeError("缺少 MP3 编码器，请先运行「安装依赖.bat」")
        # 退回 libsndfile 的 MP3 编码（码率不可控，但能用）
        with _sf.SoundFile(path, "w", int(sr), channels, format="MP3",
                           subtype="MPEG_LAYER_III", compression_level=0.6) as f:
            step = 8192
            for i in range(0, len(mix), step):
                f.write(mix[i:i + step])
        return
    enc = lameenc.Encoder()
    enc.set_bit_rate(int(bitrate))
    enc.set_in_sample_rate(int(sr))
    enc.set_channels(channels)
    enc.set_quality(2)
    step = 1 << 20
    with open(path, "wb") as f:
        for i in range(0, len(mix), step):
            pcm = _to_int16(mix[i:i + step])
            f.write(enc.encode(pcm.tobytes()))
        f.write(enc.flush())


def _write_sf(path: str, mix: np.ndarray, sr: int, fmt: str, quality: str, bits: int = 16):
    if _sf is None:
        raise RuntimeError("缺少 soundfile，请先运行「安装依赖.bat」")
    fmt = fmt.lower()
    if fmt == "flac":
        sub, cq = ("PCM_24" if bits and bits > 16 else "PCM_16"), float(quality)
    elif fmt == "ogg":
        sub, cq = "VORBIS", float(quality)
    else:
        raise ValueError("不支持的输出格式：%s" % fmt)
    channels = 1 if mix.ndim == 1 else int(mix.shape[1])
    # 一次性写入超长数组会让 libsndfile 的 Vorbis 编码器爆栈，分块写更稳
    with _sf.SoundFile(path, "w", int(sr), channels, subtype=sub,
                       format=fmt.upper(), compression_level=cq) as f:
        step = 8192
        for i in range(0, len(mix), step):
            f.write(mix[i:i + step])


def encode_audio(path: str, mix: np.ndarray, sr: int, fmt: str, quality: str, bits: int = 16):
    fmt = fmt.lower()
    if fmt == "wav":
        _write_wav(path, mix, sr)
    elif fmt == "mp3":
        _write_mp3(path, mix, sr, int(quality))
    elif fmt in ("flac", "ogg"):
        _write_sf(path, mix, sr, fmt, quality, bits)
    else:
        raise ValueError("不支持的输出格式：%s" % fmt)


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x.astype(np.float32, copy=False)
    n_out = max(1, int(round(len(x) * sr_out / float(sr_in))))
    try:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr_in, sr_out)
        y = resample_poly(x, sr_out // g, sr_in // g, axis=0)
        return y.astype(np.float32, copy=False)
    except Exception:
        pos = np.linspace(0.0, len(x) - 1.0, n_out, dtype=np.float64)
        src = np.arange(len(x), dtype=np.float64)
        if x.ndim == 1:
            return np.interp(pos, src, x).astype(np.float32)
        out = np.empty((n_out, x.shape[1]), dtype=np.float32)
        for c in range(x.shape[1]):
            out[:, c] = np.interp(pos, src, x[:, c])
        return out


# ---------------------------------------------------------------- 对外接口
_bank_cache: Optional[DLSBank] = None


def _bank() -> DLSBank:
    global _bank_cache
    if _bank_cache is None:
        _bank_cache = DLSBank()
    return _bank_cache


def output_sample_rate(fmt: str, quality: str, source_rate: Optional[int] = None) -> int:
    if fmt == "wav":
        return int(quality)
    if fmt == "mp3":
        if source_rate in MP3_RATES:
            return int(source_rate)
        if source_rate and source_rate < 16000:
            return 16000
        if source_rate and source_rate > 48000:
            return 48000
        return DEFAULT_SR
    return int(source_rate or DEFAULT_SR)


def midi_to_audio(src: str, dst: str, fmt: str, quality: str, progress=None):
    song = parse_midi(src)
    if not song.notes:
        raise RuntimeError("MIDI 里没有可播放的音符")
    if song.duration > MAX_MIDI_SECONDS:
        raise RuntimeError("MIDI 太长（超过 30 分钟），暂不支持")
    sr = int(quality) if fmt == "wav" else DEFAULT_SR
    if progress:
        progress(0.01)
    synth = Synth(_bank())
    mix, sr = synth.render(song, sr, progress=(lambda p: progress(0.05 + p * 0.80)) if progress else None)
    if progress:
        progress(0.88)
    encode_audio(dst, mix, sr, fmt, quality)
    if progress:
        progress(1.0)
    return sr, song.duration


def audio_to_audio(src: str, dst: str, fmt: str, quality: str, progress=None):
    if _sf is None:
        raise RuntimeError("缺少 soundfile，请先运行「安装依赖.bat」")
    if progress:
        progress(0.05)
    try:
        info = _sf.info(src)
        src_bits = 24 if info.subtype in ("PCM_24", "PCM_32", "FLOAT", "DOUBLE") else 16
    except Exception:
        src_bits = 16
    try:
        data, sr = _sf.read(src, dtype="float32", always_2d=True)
    except Exception:
        raise RuntimeError("无法读取音频文件（可能已损坏或格式不支持）")
    if data.size == 0:
        raise RuntimeError("音频文件是空的")
    channels = data.shape[1]
    if channels > 2:
        data = data.mean(axis=1, keepdims=True)
        channels = 1
    if progress:
        progress(0.15)
    target = output_sample_rate(fmt, quality, sr)
    if target != sr:
        data = resample(data, sr, target)
        sr = target
    if progress:
        progress(0.45)

    # 太长的静音/单声道交给编码器；这里只做峰值保护
    peak = float(np.max(np.abs(data)))
    if peak > 1.0:
        data = data / peak * 0.99

    if fmt == "wav":
        if channels == 1:
            data = data[:, 0]
        if progress:
            progress(0.7)
        encode_audio(dst, data, sr, fmt, quality, src_bits)
    elif fmt == "mp3":
        if sr not in MP3_RATES:
            data = resample(data, sr, DEFAULT_SR)
            sr = DEFAULT_SR
        if progress:
            progress(0.7)
        encode_audio(dst, data[:, 0] if channels == 1 else data, sr, fmt, quality, src_bits)
    else:
        if progress:
            progress(0.7)
        encode_audio(dst, data[:, 0] if channels == 1 else data, sr, fmt, quality, src_bits)
    if progress:
        progress(1.0)
    return sr


def convert_file(src: str, dst: str, fmt: str, quality: str, progress=None):
    if is_midi_file(src):
        return midi_to_audio(src, dst, fmt, quality, progress)
    return audio_to_audio(src, dst, fmt, quality, progress)


def unique_output_path(src: str, fmt: str) -> str:
    base, ext = os.path.splitext(src)
    candidate = base + "." + fmt
    if os.path.normcase(candidate) == os.path.normcase(src):
        candidate = base + " (转换)." + fmt
    if not os.path.exists(candidate):
        return candidate
    stem = os.path.splitext(candidate)[0]
    for i in range(1, 1000):
        p = "%s (%d).%s" % (stem, i, fmt)
        if os.path.normcase(p) != os.path.normcase(src) and not os.path.exists(p):
            return p
    return "%s (%d).%s" % (stem, os.getpid(), fmt)
