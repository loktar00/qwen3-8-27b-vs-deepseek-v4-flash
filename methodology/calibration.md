# Harness calibration gate (run per model, per harness, BEFORE any head-to-head)

Purpose: prove the harness parses this model's tool calls and the model can drive the
tools. 5/5 required. Failures here are HARNESS/CONFIG events, fixed before comparison —
never scored as model losses. Results published alongside the comparison.

Fixture: a throwaway dir with `notes.txt` (3 lines), `calc.py` (def add(a,b): return a-b),
`data.csv` (5 rows, one malformed), and a `package.json`-free node script `sum.js`.

1. READ — "What is on line 2 of notes.txt?" → must call the read tool, answer exactly.
2. EDIT — "calc.py's add() is wrong; fix it and show the diff." → single-line edit, file changed.
3. RUN+READ OUTPUT — "Run `python calc.py` (prints add(2,3)) and tell me the output." → 5.
4. CHAIN — "Count the valid rows in data.csv, write the count to count.txt, then read it back."
   → 3 tool calls in order, count.txt == 4.
5. RECOVER — "Run `node sum.js 1 2`. If it fails, fix sum.js so it prints the sum of its two
   numeric arguments, re-run, and tell me the output." where sum.js has a syntax error → must
   read the error, fix it, re-run, report 3.

Record: tool calls made, malformed-call errors (harness-side), wall time, tokens.
Pass = all five correct with zero unrecoverable tool-call parse errors.
