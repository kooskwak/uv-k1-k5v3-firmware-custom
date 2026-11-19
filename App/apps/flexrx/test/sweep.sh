#!/usr/bin/env bash
# Sweep: audio high-pass corner x noise, plus clock / polarity / bit-error cases.
# Prints, per case, the pages decoded out of 5 and the exact-text count.
cd "$(dirname "$0")"
EXPECT=(
"1420003 ALN +2 \"A1 Ambulance met spoed naar Damrak 1 Amsterdam 13154\""
"1234560 NUM +0 \"0123456789-\""
"1234567 ALN +0 \"P 2 BRT-02 Test bericht FLEX RX\""
"0100001 ALN +0 \"Lange tekst: abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz0123456789\""
"1530001 ALN +0 \"Eind\""
)
run() {
  python3 flex.py /tmp/sw.raw "$@" || return
  out=$(./host /tmp/sw.raw ../flexrx_assets.bin)
  n=$(echo "$out" | head -1 | awk '{print $4}')
  ok=0; for e in "${EXPECT[@]}"; do echo "$out" | grep -qF "  $e" && ok=$((ok+1)); done
  extra=$(( $(echo "$out" | grep -c '^  ') - ok ))
  printf '%-34s pages %s  exact %d/5  other %d  frames %s\n' "$*" "$n" "$ok" "$extra" "$(echo "$out" | head -1 | awk '{print $2}')"
}
for hp in 30 100 300 1000 1500; do for nz in 0 0.3 0.6; do run --hp $hp --noise $nz --seed 3; done; done
run --hp 300 --noise 0.3 --clock 0.005
run --hp 300 --noise 0.3 --clock -0.005
run --hp 300 --noise 0.3 --clock 0.01
run --hp 300 --noise 0.3 --clock -0.01
run --hp 300 --noise 0.3 --invert
run --hp 300 --flips 8
run --hp 300 --noise 0.3 --flips 8
run --hp 300 --lp 2000 --noise 0.3
