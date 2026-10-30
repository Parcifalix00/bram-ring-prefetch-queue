# BRAM-ring: H6 consume-first CPU candidate

H6 retains the complete per-nonce fill, run, state serialization and SHA-256
work. It uses two queue slots (128 payload bytes) and consumes block `i-2`
before enqueueing block `i`, retaining a nominal two-block delay. Bank widths,
tap tables, evaluator, specification and logical bank operations are unchanged.
The historical H4 documentation is retained verbatim below.

## Build H6 and check all published vectors

Run these commands from the package root on the intended Linux x86-64 host
with AVX2/BMI2 and existing GCC 13/OpenMP tools. The shared driver is unchanged.
It includes `SOURCE_FILE` and has no default kernel selector. The shell single
quotes below preserve the double quotes required by the C include operand.

```sh
(
  cd cpu
  gcc-13 -O3 -march=native -fopenmp '-DSOURCE_FILE="h6_kernel.c"' \
      driver.c sha256.c -o h6_driver
)
./cpu/h6_driver sha-control
./cpu/h6_driver vectors vectors.txt > h6-vectors.txt
python3 -B host/check_vectors.py h6-vectors.txt vectors.txt
```

The SHA control must print
`ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`.
The checker must report all eight nonces, digests, folds and full states
bit-exact. Its first file argument is our output; the second is the golden
reference. Build natively on each host; do not reuse `-march=native` binaries
on another CPU. These package instructions were checked statically during
assembly of this source tree, without another build or benchmark.

## Two completed AMD guest batches

Both fixed jobs compared the frozen original baseline, unchanged H4 and exact
H6 in one session. Each selected two distinct reported guest cores from four
vCPUs, used 800 complete hashes per timing run and six balanced main samples
per arm, and retained every sample. Rates were not pooled across hosts.

| Reported guest CPU | Job | H6/original, ratio of means | H6/H4, ratio of means |
| --- | --- | --- | --- |
| AMD EPYC 9V74 | [first batch](https://github.com/Parcifalix00/bram-ring-prefetch-queue/actions/runs/40971265977) | +12.231010% | +3.496671% |
| AMD EPYC 7763 | [replication](https://github.com/Parcifalix00/bram-ring-prefetch-queue/actions/runs/40972608143) | +12.400295% | +5.289601% |

Each job passed all three eight-vector proofs and SHA controls, the two-step
H6 shared-helper sentinel, source/binary/capture bindings, native assembly
review and its descriptive stability gates. All six H6/H4 triplet ratios
exceeded one in each job. In the first job, one H6/original triplet gain was
8.160695%, below 10%; five of six exceeded 10%. All six exceeded 10% in the
second job. A ratio of arithmetic means does not promise every run exceeds
that threshold. Native binary bindings come from the job logs; the binary
bytes were not independently downloaded.

These are two-thread guest measurements against the frozen original,
not a verified current-champion comparison or proof of physical placement.
They are not an official i7-12700KF eight-P-core result. The fixed samples and
descriptive gates provide no statistical-confidence or award guarantee.

## Additional correctness and Intel timing limit

An offline Intel i7-8565U guest check with two reported cores passed H6's
eight complete published vectors, eight complete independently generated
fresh-seed vectors, both SHA controls and the shared-helper sentinel.
Source and result integrity checks passed. The independent fixture was
generated from the unchanged definition, not from H6 and not supplied by
the organiser.

That Intel timing session's descriptive ratio of means was +14.922101%
against the frozen original. It failed the preset stability requirement:
half-session gain drift was 5.322717 percentage points, above the 5-point
limit. The timing is retained as a failed-quality observation and does not
establish a reliable Intel gain. It must not be pooled with the AMD batches.
No future organiser-issued fresh-seed challenge has been completed.

## Complete-work benchmark entry point

The unchanged driver accepts `bench 800 8 0000000000000000`, verifies the
actual thread count, disables dynamic OpenMP and consumes each full SHA-256
result. Per-nonce initialization, fill, run, serialization, SHA-256 and
checksum consumption are inside its timer; one-time table preparation is
outside it. This assembled tree has not been tested on eight physical cores.

Only after verifying that the target topology and allowed affinity really
match the sponsor's documented eight P-core logical IDs, the illustrative
command is:

```sh
OMP_NUM_THREADS=8 OMP_THREAD_LIMIT=8 OMP_DYNAMIC=FALSE \
OMP_PROC_BIND=close OMP_PLACES='{0},{2},{4},{6},{8},{10},{12},{14}' \
taskset -c 0,2,4,6,8,10,12,14 \
./cpu/h6_driver bench 800 8 0000000000000000
```

Do not apply that CPU list to an unverified host. Thread support does not
prove physical P-core placement. The JSON reports count, actual threads,
nonce, checksum and wall time; rate is count divided by wall time. The
official comparison requires the actual current champion and the applicable
organiser protocol. This package does not perform that official comparison.

## Future organiser seed

For a future supplied seed, preserve this frozen tree and use a separate
authorised scratch copy. The unchanged generator emits all eight full vectors
and CPU/FPGA tables and can be expensive; do not truncate it or substitute a
candidate-generated oracle. This is a prospective recipe, not a completed
organiser challenge:

```sh
scratch=../h6-fresh-proof
test ! -e "$scratch" || exit 1
mkdir "$scratch"
cp -R cpu host spec.py generate.py vectors.txt LICENSE README.md "$scratch/"
mkdir "$scratch/fpga"
(
  cd "$scratch"
  BRAM_EPOCH='ORGANISER_SUPPLIED_SEED' PYTHONDONTWRITEBYTECODE=1 python3 -B generate.py
  (
    cd cpu
    gcc-13 -O3 -march=native -fopenmp '-DSOURCE_FILE="h6_kernel.c"' \
        driver.c sha256.c -o h6_driver
  )
  ./cpu/h6_driver sha-control
  ./cpu/h6_driver vectors vectors.txt > h6-vectors.txt
  python3 -B host/check_vectors.py h6-vectors.txt vectors.txt
)
```

Replace the placeholder with the exact supplied seed. A fresh-seed correctness
proof is separate from speed, which the recorded jobs measured on epoch0.

## Source identity and licence

| File | SHA-256 |
| --- | --- |
| `cpu/h6_kernel.c` | `be21311882cc2f8faf7055f61fbced08f56859f9062829cbc60c917d27dd0ab4` |
| `cpu/h6_queue.h` | `a6b0b8bd9c9cdf52ffc5348bd235712d63899a10d227833a60cebff4bbfe434d` |

The retained workflow and probe are unchanged. They pin H4 source commit
`4099956f2abc9398a0049ec658e3598a312b6761`, derive H6 using the reviewed
include and consume/enqueue changes, and verify these H6 hashes. Adding the
standalone H6 sources does not change that fixed experiment.

The exact MIT `LICENSE` and original copyright notice are retained.
No award, income, hardware-efficiency qualification or current-champion
result is asserted.

---

## Historical H4 documentation (retained verbatim)

The following commands, source descriptions and results refer to H4.

# BRAM-ring: two-block prefetch queue candidate

This is an unreleased CPU implementation candidate. On 29 October 2026, the
exact implementation and reference files included here were compiled in a
controlled local check. All eight published vectors passed on every column,
and the SHA-256 abc control passed. The resulting binary SHA-256 was
`d365c1fd8ab72f298953b15f6d07b2b99c82d68e8b9128ed1d1a068f43c4b2fb`,
identical to the candidate used for the earlier local speed comparison.
The implementation files match the locally tested candidate. No
reference-machine performance result or prize qualification is asserted.

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
