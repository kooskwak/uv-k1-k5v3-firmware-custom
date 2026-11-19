#!/usr/bin/env python3
"""FLEX 1600/2 transmitter model for FLEX RX tests (format as in the
POCSAG/FLEX modem firmware, flexutils.cpp): words are built as 21 data bits
with the first-sent bit in bit 0, BCH-encoded as POCSAG (first-sent bit in
bit 31 of the codeword), interleaved 8 words per 256-bit block.

  python3 flex.py out.raw [--hp 300] [--noise 0.3] [--clock 0] [--invert]
       [--seed 1] [--flips 0]  -> 12.8 kHz unsigned 12-bit samples (uint16 LE)
"""
import argparse, math, random, struct

A1 = 0x78F35939
D21 = 0x1FFFFF

def rev(v, n):
    r = 0
    for _ in range(n):
        r = (r << 1) | (v & 1); v >>= 1
    return r

def bch(w):                      # 21 data bits (first sent = bit 0) -> codeword
    cw = rev(w & D21, 21) << 11
    t = cw
    for _ in range(21):
        if t & 0x80000000: t ^= 0xED200000
        t = (t << 1) & 0xFFFFFFFF
    cw |= t >> 21
    if bin(cw).count("1") & 1: cw |= 1
    return cw

def with_chk(w):                  # set bits 0-3: nibbles of 0-19 + bit 20 = 15
    w &= ~0xF
    s = (w >> 20) & 1
    for i in range(1, 5): s += (w >> (4 * i)) & 15
    return w | ((15 - s) & 15)

def bits32(cw):
    return [(cw >> (31 - i)) & 1 for i in range(32)]

def alpha_words(text, first=True):
    ch = [ord(c) & 0x7F for c in text]
    if first:
        sig = (~sum(ch)) & 0x7F
        ch = [sig] + ch
    while len(ch) % 3: ch.append(0x03)
    return [ch[i] | (ch[i+1] << 7) | (ch[i+2] << 14) for i in range(0, len(ch), 3)]

NUM = {c: i for i, c in enumerate("0123456789 U -][")}
def numeric_words(digits):
    bits = [0, 0]                 # 2 bits of the checksum (not checked)
    for c in digits:
        v = NUM[c]
        bits += [(v >> k) & 1 for k in range(4)]
    target = -(-len(bits) // 21) * 21
    while len(bits) < target:     # fill with 0xC
        bits += [(0xC >> k) & 1 for k in range(4)]
    bits = bits[:target]
    return [sum(b << k for k, b in enumerate(bits[i:i+21])) for i in range(0, target, 21)]

def phase(msgs):
    """msgs: list of (ric list, 'A'|'N', text). One 88-word phase."""
    naddr = sum(len(r) for r, _, _ in msgs)
    vo = 1 + naddr
    w = [D21 if i % 2 == 0 else 0 for i in range(88)]   # idle fill, as the modem's
    w[0] = with_chk((0 << 8) | (vo << 10) | (4 << 18))      # BIW: ao=1
    mw = vo + naddr                                         # messages after vectors
    ai = 1
    for rics, kind, text in msgs:
        if kind == 'A':
            body = [ (3 << 11) | (5 << 13) ] + alpha_words(text)   # header: frag 3, msg 5
            vtype = 5
            vec = lambda: with_chk((vtype << 4) | (mw << 7) | (len(body) << 14))
        else:
            body = numeric_words(text)
            vtype = 3
            vec = lambda: with_chk((vtype << 4) | (mw << 7) | ((len(body) - 1) << 14))
        for r in rics:
            w[ai] = r + 0x8000
            w[vo + ai - 1] = vec()
            ai += 1
        for k, b in enumerate(body): w[mw + k] = b
        mw += len(body)
    assert mw <= 88
    return w

def frame_bits(frame_no, cycle, words, flips, rng):
    fiw = with_chk((cycle << 4) | (frame_no << 8))
    b = bits32(0xAAAAAAAA) + bits32(A1) + [(0x5555 >> (15 - i)) & 1 for i in range(16)] \
        + bits32(A1 ^ 0xFFFFFFFF) + bits32(bch(fiw))
    for byte in (0xAE, 0xD8, 0x45, 0x12, 0x7B):
        b += [(byte >> (7 - i)) & 1 for i in range(8)]
    cws = [bch(x) for x in words]
    for k in range(flips):        # random wrong bits, one per chosen word
        i = rng.randrange(88); cws[i] ^= 1 << rng.randrange(32)
    for blk in range(11):
        for col in range(32):
            for wd in range(8):
                b.append((cws[blk * 8 + wd] >> (31 - col)) & 1)
    assert len(b) == 3000
    return b

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--hp", type=float, default=300.0, help="audio high-pass corner, Hz")
    ap.add_argument("--lp", type=float, default=3000.0)
    ap.add_argument("--noise", type=float, default=0.0, help="rms noise / deviation")
    ap.add_argument("--clock", type=float, default=0.0, help="TX clock error, fraction")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--plan", default="std", choices=["std", "kw"], help="kw: keyword-beep pages")
    ap.add_argument("--noiseonly", type=float, default=0.0, help="seconds of noise, no signal")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    plan = [
        [([1420003, 1420004, 120901], 'A', "A1 Ambulance met spoed naar Damrak 1 Amsterdam 13154")],
        [],
        [([1234560], 'N', "0123456789-"), ([1234567], 'A', "P 2 BRT-02 Test bericht FLEX RX")],
        [([100001], 'A', "Lange tekst: " + "abcdefghijklmnopqrstuvwxyz0123456789" * 2)],
        [],
        [([1530001], 'A', "Eind")],
    ]
    if a.noiseonly:
        n = int(a.noiseonly * 12800)
        out = [max(0, min(4095, int(round(2048 + 500 * rng.gauss(0, 1))))) for _ in range(n)]
        open(a.out, "wb").write(struct.pack(f"<{n}H", *out)); return
    if a.plan == "kw":
        # Pages for the keyword and capcode alerts: put words of these texts
        # in KEYWORDS (gen_assets.py) or their capcodes in CAPS (host.c).
        plan = [
            [([1520001, 1520002, 1520003], 'A', "A1 Teststraat Alfa 1234 Rit 1")],
            [],
            [([1530010], 'A', "P 1 Bravo Charlie test")],
            [],
            [([1530020], 'A', "A2 Delta 8899")],
            [],
            [([1530030], 'A', "P 2 echo foxtrot")],
            [],
            [([1530040], 'A', "B1 Golf Ambulance")],
            [],
        ]
    bits = [rng.randint(0, 1) for _ in range(800)]         # noise-like start
    for f in range(a.frames):
        msgs = plan[f % len(plan)]
        bits += frame_bits(f % 128, (f // 128) % 15, phase(msgs), a.flips, rng)
    bits += [rng.randint(0, 1) for _ in range(800)]

    FS = 12800.0
    n = int(len(bits) / 1600.0 * FS / (1 + a.clock))
    out = []
    # first-order low-passes (transmitter shaping and receiver) and high-pass
    alp = 1 - math.exp(-2 * math.pi * a.lp / FS)
    ahp = math.exp(-2 * math.pi * a.hp / FS)
    y1 = y2 = 0.0; hp_prev_x = hp_y = 0.0
    for k in range(n):
        t = k / FS * 1600.0 * (1 + a.clock)
        x = 1.0 if bits[min(int(t), len(bits) - 1)] else -1.0
        if a.invert: x = -x
        y1 += alp * (x - y1); y2 += alp * (y1 - y2)
        hp_y = ahp * (hp_y + y2 - hp_prev_x); hp_prev_x = y2
        v = hp_y + rng.gauss(0, a.noise)
        code = int(round(2048 + 500 * v))
        out.append(max(0, min(4095, code)))
    with open(a.out, "wb") as f:
        f.write(struct.pack(f"<{len(out)}H", *out))

if __name__ == "__main__":
    main()
