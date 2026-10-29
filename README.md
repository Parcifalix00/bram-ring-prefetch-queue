# BRAM-ring: two-block prefetch queue candidate

This is an unreleased CPU implementation candidate. On 29 October 2026, the
exact implementation and reference files included here were compiled in a
controlled local check. All eight published vectors passed on every column,
and the SHA-256 abc control passed. The resulting binary SHA-256 was
`d365c1fd8ab72f298953b15f6d07b2b99c82d68e8b9128ed1d1a068f43c4b2fb`,
identical to the candidate used for the earlier local speed comparison.
This revision changes documentation only. There is no reference-machine
performance result, prize qualification, public commit or claim.

## Source and algorithm

Upstream: https://git.nodelabs.ca/nexapow/bram-ring

Frozen upstream revision: `abe3f552fef39b1d7fc52327b2ca5e97134b57b3`.
The rules are published at
https://git.nodelabs.ca/nexapow/bram-ring/-/blob/main/BOUNTY.md .
This document does not replace or refresh those rules.

The candidate starts from the original AVX2 32-bit-bank implementation.
It retains the evaluator, tap tables, seed construction, bank layout and
complete per-nonce fill, run, state serialization and SHA-256 digest.
Only RUN bank accesses are rescheduled: eight lanes per block, three queue
slots, exact PEXT addresses, T0 read-prefetch hints and a fixed two-block delay.
Enqueue precedes consumption of block i-2. The last two blocks drain before
the original ring wrap and buffer swaps. FILL remains immediate.
Queue payload is 192 bytes plus the retained 32-byte FILL scratch and other
compiler stack overhead. No logical bank RMW or cell evaluation is eliminated.
No three-byte packing or alternate Boolean evaluator is included.

The included complete-digest driver renames the kernel's inherited main.
Its public CLI accepts `vectors`, bounded `bench` and `sha-control`; it does
not enter the inherited diagnostic benchmark or mining function by default.

## Required existing tools

Linux x86-64 with AVX2 and BMI2, GCC with OpenMP, Python 3 standard library,
and normal shell/core utilities including `taskset` and `sha256sum`.
Dependencies are not vendored and there is no automatic installer.
The recorded candidate build used GCC 13.3.0 with the flags below.
`-march=native` builds for the compilation host, so do not assume binary
portability or reuse a binary built for a different machine.

## Frozen-definition check

Run from the package root only when execution is authorised:

```sh
sha256sum -c <<'EOF'
5596327c5fc89b4d87eaf64df0b25e8430a9b25247ebae4c3e1037c19cd2f292  spec.py
20f78b63ff10f7b4fee681355190e91eaaeb527a733d2701d928eb0ac6534dab  generate.py
d406e2319f21e641dc77fcf79693c88062cc312cd1d75f0c286fa4ba85cf88f1  vectors.txt
EOF
```

## Build and full-column proof

These build flags and driver/checker arguments were exercised in the controlled
local check on the exact source bytes included here. Build products and logs
were written to a separate scratch directory, leaving all source files unchanged.
The checked source tree is retained separately; this revision updates only its
documentation. Reproduce the checks on the intended review host.

```sh
(
  cd cpu
  gcc -O3 -march=native -fopenmp '-DSOURCE_FILE="h4_kernel.c"' \
      driver.c sha256.c -o h4_driver
)
./cpu/h4_driver vectors vectors.txt > candidate-vectors.txt
python3 -B host/check_vectors.py candidate-vectors.txt vectors.txt
```

The driver checks each expected nonce, digest, fold and complete ring state
before printing it. The supplied reference has eight rows; the checker must
report `8/8` on every column. A digest-only or fold-only comparison is not
sufficient. This source-only tree does not bundle the locally built binary.
The local check completed successfully: `PASS: 8/8 vectors bit-exact on every
column (digest, fold, state)`.

## A fresh seed without changing the frozen tree

The seed enters the unchanged `spec.py` through `BRAM_EPOCH`. The original
generator rewrites CPU tables and all eight complete vectors and also emits
FPGA files, even for a CPU-only proof. Create its output directories in a
separate scratch copy. The full Python vector generation can be expensive;
do not truncate it, substitute candidate-generated vectors, or run it as an
unapproved background job. The following is a prospective command sequence,
not a record that the future organiser seed has been verified:

```sh
# Choose a new sibling path within the working area; it must not exist.
scratch=../h4-fresh-proof
test ! -e "$scratch" || exit 1
mkdir "$scratch"
cp -R cpu host spec.py generate.py vectors.txt LICENSE README.md "$scratch/"
mkdir "$scratch/fpga"
(
  cd "$scratch"
  BRAM_EPOCH='organiser-supplied-seed' PYTHONDONTWRITEBYTECODE=1 python3 -B generate.py
  (
    cd cpu
    gcc -O3 -march=native -fopenmp '-DSOURCE_FILE="h4_kernel.c"' \
        driver.c sha256.c -o h4_driver
  )
  ./cpu/h4_driver vectors vectors.txt > candidate-vectors.txt
  python3 -B host/check_vectors.py candidate-vectors.txt vectors.txt
)
```

Substitute the exact supplied seed string. Keep the original package's
published definition and vectors unchanged. Fresh-seed proof does not
establish speed; the stated speed comparison uses epoch0.

## Benchmark entry point and pinning

Static inspection finds `MAX_THREADS=8`, `MAX_COUNT=4096`, dynamic OpenMP
disabled, an actual-thread-count check and complete SHA-256 work per nonce.
The source accepts `bench 800 8 0000000000000000`. No eight-core test has
been executed for this assembled tree. Pinning is performed externally;
thread support alone does not certify physical P-core placement.

Example for the reference machine's documented eight P-core logical IDs:

```sh
OMP_NUM_THREADS=8 OMP_THREAD_LIMIT=8 OMP_DYNAMIC=FALSE \
OMP_PROC_BIND=close OMP_PLACES='{0},{2},{4},{6},{8},{10},{12},{14}' \
taskset -c 0,2,4,6,8,10,12,14 \
./cpu/h4_driver bench 800 8 0000000000000000
```

Inspect the target's topology first; the CPU list is not portable. The JSON
reports count, actual threads, first nonce, checksum and internal wall time.
Compute rate as count divided by that wall time. One-time epoch-table
preparation is outside the timer; per-nonce fill/run/serialization/SHA-256
and checksum consumption are inside it. No machine settings are changed.
The official comparison needs the actual current champion in the same
session, five alternating pairs and arithmetic means, or twenty-run means
under its near-bar rule. No champion source or baseline executable is
included, so this tree alone does not perform an official comparison.

## Existing evidence and limits

The exact candidate source previously passed all eight complete published
vectors and eight retained independently generated seed vectors, plus a
shared-helper two-step sentinel test and assembly review. That is evidence
about the source version. The eight published vectors were also reproduced
from the packaged source files in the controlled check described above.
None of these tests is the future organiser-issued seed challenge.

One local comparison used an i7-8565U under WSL, four distinct guest cores,
800 nonces per run and the original shipped baseline. Four main rates per
variant gave arithmetic means of 56.218774 H/s for baseline and 61.370204 H/s
for the candidate: +9.1631846%. The preregistered A/A, orientation, half-session
drift and sample-CV gates passed; no runs were excluded or retried.
The orientation gap was 4.5623 percentage points against a 5-point gate,
with only two pairs per orientation. These are descriptive local controls,
not a statistical confidence guarantee.

The local improvement is below 10%. The reference i7-12700KF, its actual
current champion, remaining awards and the future seed check remain
unverified. Do not extrapolate the local rate or percentage to that host.
No award, income, global novelty or half-work result is established.

## Licence status

This source distribution uses the MIT licence in `LICENSE`, including the
queue helper, complete-digest entrypoint and documentation. The original
upstream MIT notice and copyright are retained unchanged. This distribution
does not assert a prize, independent discovery or an official performance
result.
