#!/bin/bash
# TEMPORANEO (issue #393): capire chi manda «Ready for Apple Intelligence» e quando. Non va unito.
USCITA="${2:-screenshot}"
mkdir -p "$USCITA"
IFS=$'\t' read -r UDID NOME IOS <<< "$(python3 -I "$(dirname "$0")/scegli_simulatore.py" iphone)"
echo "Simulatore: $NOME ($IOS) $UDID"
date
xcrun simctl boot "$UDID" 2>/dev/null
xcrun simctl bootstatus "$UDID" -b >/dev/null
date
echo "bootstatus finito"
RR=$(find /Library/Developer/CoreSimulator -maxdepth 9 -name RuntimeRoot -type d 2>/dev/null | head -3)
echo "RuntimeRoot: $RR"
{
  for r in $RR; do
    echo "--- grep stringa in $r"
    grep -rl --include=*.strings --include=*.loctable --include=*.stringsdict "Ready for Apple Intelligence" "$r/System" "$r/Applications" "$r/usr" 2>/dev/null | head -20
    grep -rl "Time to experience the new personal" "$r/System/Library" "$r/Applications" 2>/dev/null | head -20
  done
} > "$USCITA/diag-grep.txt" 2>&1
cat "$USCITA/diag-grep.txt"
xcrun simctl spawn "$UDID" defaults read com.apple.Preferences > "$USCITA/diag-defaults-preferences.txt" 2>&1
xcrun simctl spawn "$UDID" launchctl list > "$USCITA/diag-launchctl.txt" 2>&1
( xcrun simctl spawn "$UDID" log stream --style compact --predicate '(eventMessage CONTAINS[c] "intelligence") OR (process == "usernotificationsd" AND eventMessage CONTAINS "com.apple.Preferences")' > "$USCITA/diag-log-stream.txt" 2>&1 ) &
PID=$!
for i in $(seq 1 40); do
  xcrun simctl io "$UDID" screenshot --type=jpeg "$USCITA/t$(printf %03d $((i*15))).jpg" >/dev/null 2>&1
  sleep 15
done
kill $PID 2>/dev/null
xcrun simctl spawn "$UDID" log show --last 12m --style compact --predicate '(eventMessage CONTAINS[c] "intelligence") OR (process == "usernotificationsd" AND eventMessage CONTAINS "com.apple.Preferences")' > "$USCITA/diag-log-show.txt" 2>&1
wc -l "$USCITA"/diag-*.txt
xcrun simctl shutdown "$UDID" >/dev/null 2>&1
exit 0
