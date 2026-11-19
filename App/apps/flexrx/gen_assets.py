#!/usr/bin/env python3
# FLEX RX read-only assets: the screen texts and the status-bar marks.
#
# The UI texts come first, each padded to a multiple of 4 bytes: draw() reads
# them in one asset_read into a word-aligned stack block, so every text costs a
# 2-byte sp-relative add instead of a literal-pool load and a pool word.
#
#   ./gen_assets.py flexrx_assets.bin flexrx_assets.h
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from app_assets import Assets

TITLE = "FLEX RX"                           # the version is in the .app header

UI = [
    ("T_TITLE",  TITLE),
    ("T_DBM",    "dBm "),                   # "-89dBm ALN +3  last 02m15"
    ("T_ALN",    "ALN"),
    ("T_NUM",    "NUM"),
    ("T_LAST",   "  last "),                # 30 characters at most (a tiny row holds 32)
    ("T_FR",     " fr"),                    # until a first page, or key 3:
    ("T_OK",     " ok"),                    # "1600/2 fr73 ok88/88 n1234"
    ("T_N",      " n"),
    ("T_MODE",   "1600/2"),                 # a sync heard / "-" none yet
    ("T_NONE",   "-"),
    ("T_CAPS",   "CAPCODES"),               # MENU: the capcode menu
    ("T_EMPTY",  "-------"),
    ("T_MHELP",  "0-9 type  * clear  MENU back"),
]

a = Assets("FLEXRX")
ui_size = 0
for name, s in UI:
    pad = -(len(s) + 1) % 4                 # keep every offset word-aligned
    a.text(name, s + "\0" * pad)
    ui_size += len(s) + 1 + pad
a.const("UI_SIZE", ui_size)

# Keyword beeps (key 4): a page whose text holds one of these words, in any
# case, beeps its count (the most of those it holds). Words in capitals,
# letters only, 1-9 beeps. Empty here: add your own and rebuild, e.g.
#   ("WORD", 3),        # a page holding "word" beeps 3 times
KEYWORDS = [
]
kw = b""
for word, beeps in KEYWORDS:
    assert word.isalpha() and word.isupper() and 1 <= beeps <= 9, word
    kw += bytes([beeps]) + word.encode("ascii") + b"\0"
kw += b"\0"
kw += b"\0" * (-len(kw) % 4)
a.raw("KW", kw)
a.const("KW_SIZE", len(kw))
a.const("T_TITLE_CHARS", len(TITLE))

# The status bar from x = 59 (SPK_X), in one asset_read, as POCSAG RX: the
# speaker icon (bit 0 of the index), 3 blank columns, then the scroll marks at
# x = 72, up (bit 1) in bits 0-2, down (bit 2) in bits 4-6. 8 variants.
SPK = [0x1c,0x1c,0x3e,0x7f,0x00,0x22,0x1c,0x41,0x22,0x1c]   # FoxHunt's
UP, DN = [0x04, 0x06, 0x07, 0x06, 0x04], [0x10, 0x30, 0x70, 0x30, 0x10]
tail = []
for i in range(8):
    tail += (SPK if i & 1 else [0] * len(SPK)) + [0] * 3
    tail += [(u if i & 2 else 0) | (d if i & 4 else 0) for u, d in zip(UP, DN)]
a.u8("BMP_TAIL", tail)
a.const("TAIL_W", len(tail) // 8)
# Key 4 on: an outlined bell (POCSAG RX's), at x = 40-47 (TONE_X)
a.u8("BMP_TONE", [0x20, 0x3c, 0x22, 0x61, 0x61, 0x22, 0x3c, 0x20])
if __name__ == "__main__":
    a.main()
