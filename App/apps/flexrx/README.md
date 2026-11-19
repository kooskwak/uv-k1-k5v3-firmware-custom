# FLEX RX (overlay app)

Receives **FLEX** pager transmissions at **1600 bit/s, 2-level FSK** (FLEX
1600/2), as the Dutch **P2000** network sends them on **169.650 MHz**, and
shows the pages: capcode, text, type. The counterpart of
[POCSAG RX](../pocsagrx/README.md), with the same receiver and screen.

## Status

| Part | State |
|---|---|
| Format | From the POCSAG/FLEX modem firmware (`flexutils.cpp`, `bitutils.cpp`): sync words A1-A4, B, FIW, BIW, address and vector words, alphanumeric and numeric messages, 8-word block interleaving, BCH (31,21) + parity |
| PC test (`test/`) | The app's own C, run against a mock API fed by `test/flex.py` (FLEX 1600/2 transmitter + audio channel), with the CPU time of the BCH and the screen modelled. See "Test results" |
| Radio app (`flexrx_app.c`) | v0.1, 3504 B of 4 KiB, stack below POCSAG RX's: **receives P2000 on the radio** (2026-11-03) |
| v0.2: keyword beeps | 3768 B. Key 4 (saved, on by default): a page holding a keyword beeps its count. PC test: right count for each keyword, once per message, any case; not checked on the radio yet |

## Versions

Own builds end in `b` (`V.00.04b`); published ones have no letter (`V.00.02`).
The catalog holds 0.1.

## Use

1. Tune the VFO to **169.650 MHz**, **FM, wide**.
2. Launch FLEX RX.

The screen follows POCSAG RX: the capcode in bold (7 digits, as P2000 writes
them) with the counters at its right (pages received, page shown / pages
kept), the text under it on 5 rows (no frequency on screen since V.00.04b),
and the bottom line `-89dBm ALN +3  last 02m15`: level, type (ALN
alphanumeric, NUM numeric), the other capcodes the same message went to in
that frame (P2000 sends one alert to several capcodes: it is kept once), time
since the page came. A new page wakes the backlight and blinks the green LED
twice.

Until a first page, and with key 3 after it, the bottom line reads
`1600/2 fr73 ok88 n1234`: the mode of the last sync heard (`1600/2`, `3200/2`,
`3200/4`, `6400/4`; `-` until one), the frame number of its frame information
word, the codewords read in the last 1600/2 frame (of 88), and the 1600/2
frames read. A network in another mode still shows it (the first sync and the
FIW are always sent at 1600/2): only 1600/2 frames are decoded.

| Key | Action |
|---|---|
| UP / DOWN | Scroll the text a row when it overflows (normal view); at either end, the newer / older page (UV-K1: LEFT / RIGHT). 8 pages kept |
| * | Normal view (18 characters a row, 5 rows) / compact view (32 tiny characters a row: a whole 112-character page); saved |
| 1 | Speaker on / off (saved, off by default). Not gated by the squelch |
| 2 | Clear the pages and the counters |
| 3 | After a page: toggle level, type and age / frame counters |
| MENU | The capcode menu (V.00.05b): 4 capcodes, saved. In it: UP / DOWN the row, 0-9 type (7 digits), * clear the row, MENU or EXIT back |
| 4 | Keyword and capcode beeps on / off (saved, on by default); a bell after the title while on. While on, only a keyword page wakes the backlight (the LED blinks for every page) |
| EXIT | Quit |

A FLEX network sends frame after frame without a gap, so while it is heard
the screen is redrawn once a frame (every 1.875 s), in the bit sync that starts
the next one: a key is read at once, but what it changes shows at the next
frame.

## Keyword beeps

A page whose text holds one of your keywords, in any case, beeps (1500 Hz,
with the green LED) as many times as listed for it; a page holding several
beeps the most. The list is `KEYWORDS` in `gen_assets.py` (letters only, 1-9
beeps each), empty in this repository: add your own words and rebuild. A message sent to several capcodes beeps once. While key 4 is on, only these
pages wake the backlight; the other pages are drawn with the light as it is.
The green LED blinks for every page (v0.3). The beeps come
right after the page is drawn, and the tone takes the receiver off RX for
their length (0.2 s a beep, through the speaker whatever key 1 says): the next
frame is lost, the one after is read again.

## Capcode alerts (V.00.05b)

MENU opens a list of 4 capcodes (`>1 0120901`, `-------` for an empty row).
A page to one of them, also as one of the `+N` capcodes of a message, beeps
5 times and wakes the backlight, with key 4 on. They are saved with the
settings: the config of an app is 16 bytes, 4 words, each a capcode in bits
0-23, the view, speaker and beeps in the top bytes of the first three.

The config belongs to the app's name: a build with another name (FLEX RX06)
starts with an empty list and the default settings.

To fit 4 KiB, V.00.05b also shows the age in minutes (`last 125m03`), skips
long addresses (P2000 uses short ones) and looks for the 1600/2 sync only
(key 3 shows `1600/2` or `-`).

## Limits

- **FLEX 1600/2 only.** 3200/2, 3200/4 and 6400/4 are told (key 3), not
  decoded.
- **Alphanumeric and numeric pages** (vector types 3, 4, 5, 7). Tone-only,
  short-message, hex and secure vectors, and temporary addresses are skipped.
  A message split over several frames (fragments) shows as one page per
  fragment.
- **112 characters per page** are kept.
- **A `?` is a character of a codeword no slicer could read** (three wrong
  bits or more). Two wrong bits are corrected at the end of the frame, for up
  to 24 codewords a frame.
- Long addresses use multimon-ng's capcode formula; P2000 uses short ones.
- Pages are kept in RAM only.

## How it decodes

PA4 audio on ADC channel 4 at 12.8 kHz (8 samples a bit), receiver in RAW
(RX HPF300 / LPF3K / de-emphasis and AFC off), DC removal, the sum of the last
4 samples (half a bit), then three hysteresis slicers (1/4, 3/8 and 1/2 of the
peak), each with its DPLL (1/4 of the error per transition).

Each slicer looks, in its last 80 bits, for A, B (`5555`) and /A of each mode
(1600/2: `78F35939`), in either polarity, 10 wrong bits allowed. Then the
frame information word: BCH-checked, and its 4-bit checksum, which also tells
the polarity if the sync was read the other way. Sync 2 (40 bits) is skipped,
then the 11 blocks of 8 interleaved codewords are collected. The slicers of
one transmission share one frame buffer; each codeword is kept from the slicer
that read it cleanly, or else with one bit corrected.

At the end of the frame, codewords none of them read are tried for two wrong
bits; the block information word gives where the addresses and their vectors
are, each vector where its message words are and what they hold. The screen is
drawn right after, during the 20 ms of bit sync that opens the next frame. Keys
are read every 100 ms (a 0.3 ms scan; the bit clocks run on over it, the level
held).

## Test results (`test/`)

`test/sweep.sh` and `test/tune.sh` run the app's decoder over frames of 5
pages (an alert to 3 capcodes, a numeric page, short and 85-character texts),
idle frames between them:

- **clean signal, audio corner 100 to 1500 Hz: every page exact**; 8 random
  wrong bits a frame: every page exact; the other polarity: exact;
- **clock 0.5 % off: exact; 1 % off: 4 of 5**;
- noise of 0.3 x the deviation (white, 6.4 kHz): every page at a 300 Hz
  corner, fewer at 100 Hz, none at 1000 Hz and above, where the audio path
  keeps little of a 1600 bit/s signal;
- **an audio corner of 30 Hz fails** after long runs of equal bits (the same
  limit as POCSAG RX's hysteresis slicers);
- 2 x 60 s of noise: nothing; 40 frames in a row (75 s): 40 read, 34 of 34
  pages.

## Files

- `flexrx_app.c`, `gen_assets.py`, `build.sh`, `app.ld`: the app.
- `test/flex.py`: FLEX 1600/2 transmitter and audio channel (12.8 kHz samples).
- `test/host.c`: runs `flexrx_app.c` on a PC with a mock API
  (`gcc -m32 -I.. -o host host.c`, then `./host file.raw ../flexrx_assets.bin [v]`).
- `test/sweep.sh`, `test/tune.sh`: the case sets above.
