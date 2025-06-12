#!/usr/bin/env bash


die() {
  err_msg="$*"
  echo "ERROR: $err_msg" >&2
  exit 1
}

call() {
  stage="$1"; shift
  echo -e "\n==> $stage"
  resp=$(curl -s -X POST "$@")
  echo "$resp" | jq .
  ok=$(echo "$resp" | jq -r .status)
  [[ "$ok" == "ok" ]] || die "$stage failed: $ok"
}

pkill -f placement_server.py    2>/dev/null

nohup python3 server/placement_server.py     >/dev/null 2>&1 &


design="des"
tech="FreePDK45"

g_idx=0    
p_idx=0
c_idx=0
synth_dir=$(ls -dt designs/"$design"/"$tech"/synthesis/* | head -1)
syn_ver=$(basename "$synth_dir")
impl_ver="${syn_ver}__g${g_idx}_p${p_idx}"
# powerplan_enc="designs/$design/$tech/implementation/$impl_ver/pnr_save/powerplan.enc.dat"
powerplan_enc="designs/$design/$tech/implementation/cpV1_clkP1_drcV1__VenU80_pV1_cV1/pnr_save/powerplan.enc.dat"


call "5. Placement" \
  http://localhost:3337/place/run \
  -H 'Content-Type: application/json' \
  -d "{\"design\":\"$design\",\"tech\":\"$tech\",\"impl_ver\":\"$impl_ver\",\"g_idx\":$g_idx,\"p_idx\":$p_idx,\"restore_enc\":\"$powerplan_enc\",\"top_module\":\"des3\",\"force\":true}"

