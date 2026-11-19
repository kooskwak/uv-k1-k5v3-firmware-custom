#!/usr/bin/env bash
# tune.sh <sed-expr>...: build a variant of the app and count exact pages over a case set
cd "$(dirname "$0")"
sed "$@" ../flexrx_app.c > v_app.c
sed 's|#include "../flexrx_app.c"|#include "v_app.c"|' host.c > hv.c
gcc -m32 -O1 -w -I.. -o hv hv.c || exit 1
tot=0; line=""
for c in "--hp 30 --noise 0.3" "--hp 100 --noise 0.3" "--hp 300 --noise 0.3" "--hp 300 --noise 0.45" "--hp 1000 --noise 0.15" "--hp 1000 --noise 0.25" "--hp 1500 --noise 0.15" \
         "--hp 300 --noise 0.2 --clock 0.01" "--hp 300 --noise 0.2 --clock -0.01" "--hp 1000 --noise 0.1 --clock 0.01" "--hp 300 --noise 0.3 --invert" "--hp 300 --lp 2000 --noise 0.3"; do
  for s in 1 2; do
    [ -f "/tmp/c_${c// /_}_$s.raw" ] || python3 flex.py "/tmp/c_${c// /_}_$s.raw" $c --seed $s
    out=$(./hv "/tmp/c_${c// /_}_$s.raw" ../flexrx_assets.bin)
    ok=0
    for e in "A1 Ambulance met spoed naar Damrak 1 Amsterdam 13154\"" "\"0123456789-\"" "\"P 2 BRT-02 Test bericht FLEX RX\"" "xyz0123456789abcdefghijklmnopqrstuvwxyz0123456789\"" "\"Eind\""; do
      echo "$out" | grep -qF "$e" && ok=$((ok+1)); done
    tot=$((tot+ok)); line="$line$ok"
  done
  line="$line "
done
echo "total $tot/120  [$line]"
