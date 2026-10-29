#!/usr/bin/env python3
"""One manually approved, finite offline three-arm pilot; no mining or networked kernel work.
Embedded C sources derive from the project MIT distribution.
Copyright (c) 2026 Peter Rizun; the repository LICENSE remains applicable.

This file is inert on import. The only network activity is a fixed, hash-checked
source acquisition before compilation. It never installs tools or retries work.
"""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import signal
import statistics
import subprocess
import time
import urllib.request

REPO = "Parcifalix00/bram-ring-prefetch-queue"
SOURCE_COMMIT = "4099956f2abc9398a0049ec658e3598a312b6761"
UPSTREAM_COMMIT = "abe3f552fef39b1d7fc52327b2ca5e97134b57b3"
UPSTREAM_URL = ("https://git.nodelabs.ca/nexapow/bram-ring/-/raw/"
                + UPSTREAM_COMMIT + "/cpu/verify_avx2.c")
BASELINE_SHA = "cef9169590a4b81201879ce92959b155b3e7c3fbf6ec20372e45e9f98ceed05b"
# Required frozen package files only; never execute a downloaded Python file.
SOURCE_HASHES = {
    "LICENSE": "1891665e46abb61980d3a456df8a17f341f3bc913f55c34dec62b03abddc98ba",
    "spec.py": "5596327c5fc89b4d87eaf64df0b25e8430a9b25247ebae4c3e1037c19cd2f292",
    "vectors.txt": "d406e2319f21e641dc77fcf79693c88062cc312cd1d75f0c286fa4ba85cf88f1",
    "cpu/driver.c": "9f447e2ddfab4f55eb75b65a8666cfded7dc01eca4d6c4454f53b3abd1e49883",
    "cpu/h4_kernel.c": "6ecad18183ef5e5c3554351b7e4236830b2a8fe9acd05732684498ca262e7f5a",
    "cpu/h4_queue.h": "23e9448fab0ac3b59a488da71004571456e7e8dc0f4fec417bc3c394baad3bb2",
    "cpu/sha256.c": "838a3dfa0ba2bb0c544e57ce403b7b11c525f896befa2ec9d048b7e03944b998",
    "cpu/sha256.h": "8483f784e6adce94c864a58d7a454ac5af38bf6e0294e08d41c2af8963fc1db0",
    "cpu/tables.h": "c25ec853118e1e5eede4be5ef204768921fde242fd926f8a214e69dc004085c6",
}
SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
WORK = "init+fill+run+serialize+SHA256+consume"
COUNT = 800
MAIN_TRIPLETS = ("ABC", "BCA", "CAB", "CBA", "BAC", "ACB")
SCHEDULE = [("warmup", v) for v in "ABC"] + [("aa", "A")] * 2 + [
    ("main", v) for triplet in MAIN_TRIPLETS for v in triplet]
COMPARISONS = (("B", "A"), ("C", "A"), ("C", "B"))
CPU_CAP = 900.0
WALL_CAP = 400.0
CPU_RESERVE = 4.0
OUTPUT_CAP = 131072
ASM_OUTPUT_CAP = 524288
SOURCE_CAP = 524288
COMMAND_CAP = 40
PLANNED_COMMANDS = 37
EXPECTED_HASHED_FILES = 21
H6_KERNEL_SHA = 'be21311882cc2f8faf7055f61fbced08f56859f9062829cbc60c917d27dd0ab4'
SENTINEL_EXPECTED = "H6_QUEUE_UNIT_PASS steps=2 banks=768 depth=512 consumed_blocks=192 old_reads=1536 all_rows_and_canaries=equal lane767=covered"
H6_HELPER_SHA = 'a6b0b8bd9c9cdf52ffc5348bd235712d63899a10d227833a60cebff4bbfe434d'
H6_HELPER_B64 = 'I2lmbmRlZiBORVhBX0g2X1FVRVVFX0gKI2RlZmluZSBORVhBX0g2X1FVRVVFX0gKI2luY2x1ZGUgPHN0ZGludC5oPgojaW5jbHVkZSA8aW1taW50cmluLmg+CgovKiBQcml2YXRlIEg2OiBjb25zdW1lIGJsb2NrIGktMiBiZWZvcmUgZW5xdWV1ZSBpOyBEPTIsIHR3byBzbG90cy4gKi8KdHlwZWRlZiBzdHJ1Y3QgewogICAgdWludDMyX3QgcXZbMl1bOF07CiAgICB1aW50MzJfdCBxYVsyXVs4XTsKfSBoNF9xdWV1ZTsKX1N0YXRpY19hc3NlcnQoc2l6ZW9mKGg0X3F1ZXVlKSA9PSAxMjgsICJINiBxdWV1ZSBwYXlsb2FkIG11c3QgYmUgMTI4IGJ5dGVzIik7Cl9TdGF0aWNfYXNzZXJ0KEIgPT0gNzY4ICYmIERFUFRIID09IDUxMiwgIkg2IGdlb21ldHJ5IG11c3QgbWF0Y2ggSDQiKTsKCnN0YXRpYyBpbmxpbmUgdm9pZCBoNF9lbnF1ZXVlX2Jsb2NrKGg0X3F1ZXVlICpxLCBpbnQgYmxvY2ssIF9fbTI1NmkgdjgsCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVpbnQzMl90IGJhbmtbQl1bREVQVEhdLAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCB1aW50MzJfdCBhbWFza1tCXSkKewogICAgaW50IHNsb3QgPSBibG9jayAmIDE7CiAgICBfbW0yNTZfc3RvcmV1X3NpMjU2KChfX20yNTZpICopcS0+cXZbc2xvdF0sIHY4KTsKICAgIGZvciAoaW50IGsgPSAwOyBrIDwgODsgaysrKSB7CiAgICAgICAgaW50IGIgPSBibG9jayAqIDggKyBrOwogICAgICAgIHVuc2lnbmVkIGEgPSBfcGV4dF91MzIocS0+cXZbc2xvdF1ba10sIGFtYXNrW2JdKTsKICAgICAgICBxLT5xYVtzbG90XVtrXSA9IGE7CiAgICAgICAgX21tX3ByZWZldGNoKChjb25zdCBjaGFyICopJmJhbmtbYl1bYV0sIF9NTV9ISU5UX1QwKTsKICAgIH0KfQoKLyogTm9ubmVnYXRpdmUgYmxvY2tzOyBjYWxsZXIgbXVzdCBjb25zdW1lIGJlZm9yZSByZXVzaW5nIGVpdGhlciBzbG90LiAqLwpzdGF0aWMgaW5saW5lIHZvaWQgaDRfY29uc3VtZV9ibG9jayhoNF9xdWV1ZSAqcSwgaW50IGJsb2NrLAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB1aW50MzJfdCBiYW5rW0JdW0RFUFRIXSwgdWludDMyX3QgbnJkW0JdKQp7CiAgICBpbnQgc2xvdCA9IGJsb2NrICYgMTsKICAgIGZvciAoaW50IGsgPSAwOyBrIDwgODsgaysrKSB7CiAgICAgICAgaW50IGIgPSBibG9jayAqIDggKyBrOwogICAgICAgIHVuc2lnbmVkIGEgPSBxLT5xYVtzbG90XVtrXTsKICAgICAgICB1aW50MzJfdCBvbGQgPSBiYW5rW2JdW2FdOwogICAgICAgIG5yZFtiXSA9IG9sZDsKICAgICAgICBiYW5rW2JdW2FdID0gcS0+cXZbc2xvdF1ba107CiAgICB9Cn0KI2VuZGlmCg=='
SENTINEL_ORIGINAL_SHA = '72e13ee769bec73d81798ead7c0e26033e5a9bcd74cea8bf9c52c33d0c043b92'
SENTINEL_SHA = '9d756004587f501197999c3853a486157e77c1b9aee7cb9e40316fd5d6136e75'
SENTINEL_B64 = 'LyogQ29ycmVjdG5lc3Mgb25seTogbm8gaGFzaCwgdGltaW5nLCBub25jZSBzZWFyY2ggb3IgYmVuY2htYXJrLiAqLwojaW5jbHVkZSA8c3RkaW50Lmg+CiNpbmNsdWRlIDxzdGRpby5oPgojaW5jbHVkZSA8c3RyaW5nLmg+CiNpbmNsdWRlICJ0YWJsZXMuaCIKI2luY2x1ZGUgImg2X3F1ZXVlLmgiCiNkZWZpbmUgVkFMVUVfTUFTSyAoKDF1IDw8IFcpIC0gMSkKdHlwZWRlZiBzdHJ1Y3QgewogICAgdWludDMyX3QgYmVmb3JlWzE2XTsKICAgIHVpbnQzMl90IHdvcmRzW0JdW0RFUFRIXTsKICAgIHVpbnQzMl90IGFmdGVyWzE2XTsKfSBndWFyZGVkX2JhbmtzOwpzdGF0aWMgZ3VhcmRlZF9iYW5rcyBjYW5kaWRhdGUsIHJlZmVyZW5jZTsKc3RhdGljIHVpbnQzMl90IGFtYXNrW0JdLCB2YWx1ZXNbMl1bQl07CgpzdGF0aWMgdW5zaWduZWQgcmVmZXJlbmNlX3BleHQodWludDMyX3QgdmFsdWUsIHVpbnQzMl90IGJpdHMpCnsKICAgIHVuc2lnbmVkIG91dCA9IDAsIG4gPSAwOwogICAgZm9yICh1bnNpZ25lZCBpID0gMDsgaSA8IDMyOyBpKyspCiAgICAgICAgaWYgKGJpdHMgJiAoMXUgPDwgaSkpIG91dCB8PSAoKHZhbHVlID4+IGkpICYgMXUpIDw8IG4rKzsKICAgIHJldHVybiBvdXQ7Cn0KCmludCBtYWluKHZvaWQpCnsKICAgIGlmIChXICE9IDIwIHx8IEIgIT0gNzY4IHx8IERFUFRIICE9IDUxMikgcmV0dXJuIDI7CiAgICBmb3IgKHVuc2lnbmVkIGkgPSAwOyBpIDwgMTY7IGkrKykgewogICAgICAgIGNhbmRpZGF0ZS5iZWZvcmVbaV0gPSAweENBMTAwMDAwdSArIGk7CiAgICAgICAgY2FuZGlkYXRlLmFmdGVyW2ldID0gMHhDQTIwMDAwMHUgKyBpOwogICAgfQogICAgZm9yIChpbnQgYiA9IDA7IGIgPCBCOyBiKyspIHsKICAgICAgICBhbWFza1tiXSA9IDB4MWZmdSA8PCAoYiAlIDEyKTsKICAgICAgICB2YWx1ZXNbMF1bYl0gPSAoMHg3MTM1YnUgXiAoKHVpbnQzMl90KWIgKiAweDllMzc3OWI5dSkpICYgVkFMVUVfTUFTSzsKICAgICAgICB2YWx1ZXNbMV1bYl0gPSAoYiAmIDEpCiAgICAgICAgICAgID8gKCgweGEyMzQ1dSBeICgodWludDMyX3QpYiAqIDB4ODVlYmNhNmJ1KSkgJiBWQUxVRV9NQVNLKQogICAgICAgICAgICA6ICh2YWx1ZXNbMF1bYl0gXiAoKH5hbWFza1tiXSkgJiBWQUxVRV9NQVNLKSk7CiAgICAgICAgZm9yIChpbnQgYSA9IDA7IGEgPCBERVBUSDsgYSsrKQogICAgICAgICAgICBjYW5kaWRhdGUud29yZHNbYl1bYV0gPSAweEE1MDAwMDAwdSBeICgodWludDMyX3QpYiAqIDB4OWUzN3UpCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgXiAoKHVpbnQzMl90KWEgKiAweDQ1ZDl1KTsKICAgIH0KICAgIC8qIEV4cGxpY2l0IGxlZ2FsIGZpcnN0L2xhc3QgYmFuay9yb3cgZWRnZXMsIHJlcGVhdGVkIGFjcm9zcyBib3RoIHN0ZXBzLiAqLwogICAgZm9yIChpbnQgc3RlcCA9IDA7IHN0ZXAgPCAyOyBzdGVwKyspIHsKICAgICAgICB2YWx1ZXNbc3RlcF1bMF0gJj0gfmFtYXNrWzBdOwogICAgICAgIHZhbHVlc1tzdGVwXVtCIC0gMV0gfD0gYW1hc2tbQiAtIDFdOwogICAgfQogICAgbWVtY3B5KCZyZWZlcmVuY2UsICZjYW5kaWRhdGUsIHNpemVvZiBjYW5kaWRhdGUpOwogICAgdW5zaWduZWQgY29uc3VtZWRfdG90YWwgPSAwOwogICAgaDRfcXVldWUgcTsgLyogVW5pbml0aWFsaXplZDsgYm90aCBzbG90cyBwZXJzaXN0IGFjcm9zcyB0aGUgdHdvIHN0ZXBzLiAqLwogICAgZm9yIChpbnQgc3RlcCA9IDA7IHN0ZXAgPCAyOyBzdGVwKyspIHsKICAgICAgICB1aW50MzJfdCBnb3Rfb2xkW0JdLCBleHBlY3RlZF9vbGRbQl0sIG5oW0IgKyAxXTsKICAgICAgICB1bnNpZ25lZCBjb25zdW1lZFtCIC8gOF0gPSB7MH07CiAgICAgICAgbWVtc2V0KGdvdF9vbGQsIDB4Q0QsIHNpemVvZiBnb3Rfb2xkKTsKICAgICAgICBtZW1zZXQobmgsIDB4RUYsIHNpemVvZiBuaCk7CiAgICAgICAgZm9yIChpbnQgYiA9IDA7IGIgPCBCOyBiKyspIHsKICAgICAgICAgICAgdW5zaWduZWQgYSA9IHJlZmVyZW5jZV9wZXh0KHZhbHVlc1tzdGVwXVtiXSwgYW1hc2tbYl0pOwogICAgICAgICAgICBpZiAoYSA+PSBERVBUSCkgcmV0dXJuIDM7CiAgICAgICAgICAgIGV4cGVjdGVkX29sZFtiXSA9IHJlZmVyZW5jZS53b3Jkc1tiXVthXTsKICAgICAgICAgICAgcmVmZXJlbmNlLndvcmRzW2JdW2FdID0gdmFsdWVzW3N0ZXBdW2JdOwogICAgICAgIH0KICAgICAgICBmb3IgKGludCBibG9jayA9IDA7IGJsb2NrIDwgQiAvIDg7IGJsb2NrKyspIHsKICAgICAgICAgICAgX19tMjU2aSB2OCA9IF9tbTI1Nl9sb2FkdV9zaTI1NigoY29uc3QgX19tMjU2aSAqKSZ2YWx1ZXNbc3RlcF1bOCAqIGJsb2NrXSk7CiAgICAgICAgICAgIF9tbTI1Nl9zdG9yZXVfc2kyNTYoKF9fbTI1NmkgKikmbmhbOCAqIGJsb2NrICsgMV0sIHY4KTsKICAgICAgICAgICAgaWYgKGJsb2NrID49IDIpIHsKICAgICAgICAgICAgICAgIGludCBqID0gYmxvY2sgLSAyOwogICAgICAgICAgICAgICAgaDRfY29uc3VtZV9ibG9jaygmcSwgaiwgY2FuZGlkYXRlLndvcmRzLCBnb3Rfb2xkKTsKICAgICAgICAgICAgICAgIGNvbnN1bWVkW2pdKys7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgaDRfZW5xdWV1ZV9ibG9jaygmcSwgYmxvY2ssIHY4LCBjYW5kaWRhdGUud29yZHMsIGFtYXNrKTsKICAgICAgICB9CiAgICAgICAgZm9yIChpbnQgYmxvY2sgPSBCIC8gOCAtIDI7IGJsb2NrIDwgQiAvIDg7IGJsb2NrKyspIHsKICAgICAgICAgICAgaDRfY29uc3VtZV9ibG9jaygmcSwgYmxvY2ssIGNhbmRpZGF0ZS53b3JkcywgZ290X29sZCk7CiAgICAgICAgICAgIGNvbnN1bWVkW2Jsb2NrXSsrOwogICAgICAgIH0KICAgICAgICAvKiBTYW1lIG9yaWdpbmFsIGJvdW5kYXJ5LCBhZnRlciBhbGwgcGVuZGluZyBiYW5rIG9wZXJhdGlvbnMuICovCiAgICAgICAgbmhbMF0gPSBuaFtCXTsKICAgICAgICBmb3IgKGludCBibG9jayA9IDA7IGJsb2NrIDwgQiAvIDg7IGJsb2NrKyspIHsKICAgICAgICAgICAgaWYgKGNvbnN1bWVkW2Jsb2NrXSAhPSAxKSByZXR1cm4gNDsKICAgICAgICAgICAgY29uc3VtZWRfdG90YWwrKzsKICAgICAgICB9CiAgICAgICAgZm9yIChpbnQgYiA9IDA7IGIgPCBCOyBiKyspIHsKICAgICAgICAgICAgaWYgKGdvdF9vbGRbYl0gIT0gZXhwZWN0ZWRfb2xkW2JdKSByZXR1cm4gNTsKICAgICAgICAgICAgaWYgKG5oWyhiICsgMSkgJSBCXSAhPSB2YWx1ZXNbc3RlcF1bYl0pIHJldHVybiA2OwogICAgICAgIH0KICAgICAgICAvKiBJbmNsdWRlcyBhbGwgdW50b3VjaGVkIHJvd3MgYW5kIGJvdGggZ3VhcmQgcmVnaW9ucywgZXZlcnkgc3RlcC4gKi8KICAgICAgICBpZiAobWVtY21wKCZjYW5kaWRhdGUsICZyZWZlcmVuY2UsIHNpemVvZiBjYW5kaWRhdGUpKSByZXR1cm4gNzsKICAgIH0KICAgIGlmIChjb25zdW1lZF90b3RhbCAhPSAxOTIpIHJldHVybiA4OwogICAgcHV0cygiSDZfUVVFVUVfVU5JVF9QQVNTIHN0ZXBzPTIgYmFua3M9NzY4IGRlcHRoPTUxMiBjb25zdW1lZF9ibG9ja3M9MTkyIG9sZF9yZWFkcz0xNTM2IGFsbF9yb3dzX2FuZF9jYW5hcmllcz1lcXVhbCBsYW5lNzY3PWNvdmVyZWQiKTsKICAgIHJldHVybiAwOwp9Cg=='

KERNEL_ORDER_BEFORE = b'                int block = b0 / 8;\n                h4_enqueue_block(&queue, block, v8, bank, AMASK);\n                if (block >= 2)\n                    h4_consume_block(&queue, block - 2, bank, nrd);'
KERNEL_ORDER_AFTER = b'                int block = b0 / 8;\n                if (block >= 2)\n                    h4_consume_block(&queue, block - 2, bank, nrd);\n                h4_enqueue_block(&queue, block, v8, bank, AMASK);'


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(event, data):
    # JSON keeps child newlines inside a single log record.
    print(json.dumps({"event": event, "data": data}, sort_keys=True), flush=True)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_vectors(raw):
    result = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        require(len(fields) == 4, "VECTOR_COLUMN_COUNT")
        require(all(re.fullmatch(r"[0-9a-fA-F]+", s) for s in fields), "VECTOR_NONHEX")
        nonce = int(fields[0], 16)
        require(nonce not in result, "DUPLICATE_VECTOR_NONCE")
        result[nonce] = tuple(int(s, 16) for s in fields[1:])
    require(len(result) == 8, "EXPECTED_EXACTLY_EIGHT_FULL_VECTORS")
    return result


def valid_rate(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def aa_preflight(rows):
    rates = [r.get("rate_hps") for r in rows if r.get("phase") == "aa"]
    if len(rates) != 2 or not all(valid_rate(r) for r in rates):
        return {"complete": len(rates) == 2, "passed": False, "invalid_or_incomplete": True}
    difference = abs(rates[1] - rates[0]) / statistics.mean(rates)
    return {"complete": True, "rates_hps": rates,
            "symmetric_relative_difference": difference, "limit": 0.05,
            "passed": difference <= 0.05}


def analysis(rows):
    main = [r for r in rows if r.get("phase") == "main"]
    rates = {v: [r.get("rate_hps") for r in main if r.get("variant") == v] for v in "ABC"}
    complete = ([(r.get("phase"), r.get("variant")) for r in rows] == SCHEDULE
                and all(valid_rate(r.get("rate_hps")) for r in rows))
    result = {"complete": complete, "completed_main_runs": len(main),
              "all_main_rates_hps": rates, "aa_preflight": aa_preflight(rows)}
    if not complete:
        return result
    means = {v: statistics.mean(rates[v]) for v in "ABC"}
    cvs = {v: statistics.stdev(rates[v]) / means[v] for v in "ABC"}
    triplets = [main[i:i + 3] for i in range(0, 18, 3)]
    comparisons = {}
    gates = {"aa_relative_difference_at_most_5pct": result["aa_preflight"]["passed"],
             "sample_cv_each_at_most_10pct": max(cvs.values()) <= 0.10}
    for numerator, denominator in COMPARISONS:
        key = numerator + "_over_" + denominator
        forward = denominator + "_before_" + numerator
        reverse = numerator + "_before_" + denominator
        pairs = []
        for index, triplet in enumerate(triplets, 1):
            order = "".join(r["variant"] for r in triplet)
            values = {r["variant"]: r["rate_hps"] for r in triplet}
            ratio = values[numerator] / values[denominator]
            orientation = forward if order.index(denominator) < order.index(numerator) else reverse
            pairs.append({"triplet": index, "order": order, "orientation": orientation,
                          "ratio": ratio, "gain_pp": 100 * (ratio - 1)})
        orientations = {orientation: statistics.mean(p["gain_pp"] for p in pairs
                                                    if p["orientation"] == orientation)
                        for orientation in (forward, reverse)}
        halves = []
        for part in (main[:9], main[9:]):
            n = statistics.mean(r["rate_hps"] for r in part if r["variant"] == numerator)
            d = statistics.mean(r["rate_hps"] for r in part if r["variant"] == denominator)
            halves.append(100 * (n / d - 1))
        gap = abs(orientations[forward] - orientations[reverse])
        drift = abs(halves[1] - halves[0])
        comparisons[key] = {"ratio_of_all_six_arithmetic_means": means[numerator] / means[denominator],
                            "gain_percent": 100 * (means[numerator] / means[denominator] - 1),
                            "all_six_triplet_ratios": pairs,
                            "orientation_mean_gain_pp": orientations,
                            "orientation_gap_pp": gap, "half_session_gain_pp": halves,
                            "half_session_gain_drift_pp": drift}
        gates[key + "_orientation_gap_at_most_5pp"] = gap <= 5
        gates[key + "_half_session_drift_at_most_5pp"] = drift <= 5
    result.update({"arithmetic_mean_hps_all_six_runs_each": means,
                   "sample_cv": cvs, "comparisons": comparisons,
                   "quality_gates": gates, "quality_pass": all(gates.values()),
                   "interpretation": "Descriptive numerics only; actual B/C assembly and all logs require root review."})
    return result


def parse_driver(raw, threads):
    driver = json.loads(raw)
    require(isinstance(driver, dict), "DRIVER_NOT_OBJECT")
    require(driver.get("mode") == "bounded_complete_digest"
            and type(driver.get("count")) is int and driver["count"] == COUNT
            and type(driver.get("threads")) is int and driver["threads"] == threads
            and driver.get("first_nonce_hex") == "0000000000000000"
            and driver.get("work") == WORK and driver.get("rate_claim") is False,
            "DRIVER_METADATA_MISMATCH")
    require(valid_rate(driver.get("wall_seconds")), "INVALID_INTERNAL_WALL")
    require(isinstance(driver.get("checksum_hex"), str)
            and re.fullmatch(r"[0-9a-f]{16}", driver["checksum_hex"]) is not None,
            "INVALID_CHECKSUM_FORMAT")
    return driver


def validate_assembly(raw):
    require(re.search(r"^[0-9a-fA-F]+ <hash_state>:$", raw, re.M) is not None,
            "HASH_STATE_SYMBOL_UNAVAILABLE_STOP")
    require(re.search(r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{2}\s+)+", raw, re.M) is not None,
            "HASH_STATE_INSTRUCTIONS_UNAVAILABLE_STOP")
    # Presence is a capture gate only, never a modulo or memory-order proof.
    return {"symbol": "hash_state", "capture_nonempty": True,
            "semantic_review": "PENDING_ROOT_REVIEW_NO_AUTOMATIC_MODULO_OR_ORDER_CLAIM"}


def effective_valid(failure, stats, correctness_passed, hashes_ok):
    return (failure is None and correctness_passed and hashes_ok
            and stats.get("complete") is True and stats.get("quality_pass") is True)


def passive_guest_field(fields, key):
    value = fields.get(key)
    return {"status": "reported" if value else "missing", "value": value or None}


def passive_file_status(path):
    try:
        value = path.read_text().strip()
    except FileNotFoundError:
        return {"status": "missing", "value": None}
    except OSError as error:
        return {"status": "unreadable", "value": None,
                "error": type(error).__name__, "errno": error.errno}
    return {"status": "readable" if value else "empty", "value": value or None}


def topology():
    allowed = sorted(os.sched_getaffinity(0))
    require(bool(allowed), "NO_ALLOWED_CPU")
    cpuinfo_record = passive_file_status(Path("/proc/cpuinfo"))
    cpuinfo_status = {k: v for k, v in cpuinfo_record.items() if k != "value"}
    require(cpuinfo_record["status"] == "readable",
            "CPUINFO_CONTEXT_UNAVAILABLE: " + json.dumps(cpuinfo_status))
    cpuinfo = cpuinfo_record["value"]
    per_cpu = {}
    for block in cpuinfo.strip().split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        fields = {k.strip(): v.strip() for k, v in fields.items()}
        if "processor" in fields:
            per_cpu[int(fields["processor"])] = fields
    chosen, rows, seen = [], [], set()
    for cpu in allowed:
        fields = per_cpu.get(cpu, {})
        flags = set(fields.get("flags", "").split())
        require({"avx2", "bmi2"} <= flags, "REQUIRED_ISA_UNAVAILABLE")
        folder = Path("/sys/devices/system/cpu") / ("cpu" + str(cpu)) / "topology"
        package = int((folder / "physical_package_id").read_text())
        core = int((folder / "core_id").read_text())
        require(package >= 0 and core >= 0, "GUEST_TOPOLOGY_UNAVAILABLE")
        rows.append({"logical_cpu": cpu, "guest_package": package, "guest_core": core,
                     "guest_reported_model": fields.get("model name"),
                     "guest_reported_vendor": fields.get("vendor_id"),
                     "cpu_family": passive_guest_field(fields, "cpu family"),
                     "cpu_model_number": passive_guest_field(fields, "model"),
                     "stepping": passive_guest_field(fields, "stepping"),
                     "microcode": passive_guest_field(fields, "microcode")})
        if (package, core) not in seen:
            seen.add((package, core))
            chosen.append(cpu)
    chosen = chosen[:4]
    return {"platform": platform.platform(), "cpuinfo_status": cpuinfo_status,
            "allowed_logical_cpus": allowed,
            "guest_topology": rows, "selected_one_per_guest_core": chosen,
            "threads": len(chosen), "physical_pcore_placement_proven": False,
            "gather_data_sampling": passive_file_status(Path(
                "/sys/devices/system/cpu/vulnerabilities/gather_data_sampling")),
            "guest_context_limit": "Passive guest reports only. Missing, empty or unknown CPU/GDS "
                "context remains a confounder, not a host diagnosis. No mitigation is changed."}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("HTTP_REDIRECT_STOP_NO_WORKAROUND")


def fetch_exact(url, path, expected, started):
    require(time.monotonic() - started < WALL_CAP - 20, "ACQUISITION_WALL_BUDGET")
    # Respect default system networking, proxy and TLS controls; no alternate route.
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "finite-public-source-pilot"})
    def acquisition_timeout(signum, frame):
        raise TimeoutError("ACQUISITION_TOTAL_WALL_STOP_NO_RETRY")

    previous_handler = signal.signal(signal.SIGALRM, acquisition_timeout)
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP - (time.monotonic() - started) - 5)
    try:
        with opener.open(request, timeout=15) as response:
            require(response.status == 200, "HTTP_NON200_STOP")
            body = response.read(SOURCE_CAP + 1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    require(len(body) <= SOURCE_CAP, "SOURCE_SIZE_CAP")
    digest = hashlib.sha256(body).hexdigest()
    emit("source", {"url": url, "bytes": len(body), "expected_sha256": expected,
                    "actual_sha256": digest})
    require(digest == expected, "SOURCE_HASH_MISMATCH")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def group_live_cpu(pgid):
    # Sum live process CPU plus already waited descendants within the private
    # process group. Compiler subprocesses are included, not just gcc's parent.
    ticks = 0
    for item in Path("/proc").iterdir():
        if not item.name.isdecimal():
            continue
        try:
            fields = (item / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pgid:
                ticks += sum(int(fields[i]) for i in (11, 12, 13, 14))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return ticks / os.sysconf("SC_CLK_TCK")


class Budget:
    def __init__(self, folder, affinity, started):
        self.folder, self.affinity, self.started = folder, affinity, started
        self.total_cpu, self.commands = 0.0, []
        tmp = folder / "tmp"
        tmp.mkdir()
        self.env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                    "TMPDIR": str(tmp), "TMP": str(tmp), "TEMP": str(tmp),
                    "OMP_NUM_THREADS": str(len(affinity)), "OMP_THREAD_LIMIT": str(len(affinity)),
                    "OMP_DYNAMIC": "FALSE", "OMP_PROC_BIND": "close",
                    "OMP_PLACES": ",".join("{" + str(c) + "}" for c in affinity)}

    def run(self, label, argv, cwd, per_child_wall=60, stdout_cap=OUTPUT_CAP):
        remaining = CPU_CAP - self.total_cpu - CPU_RESERVE
        wall_remaining = WALL_CAP - (time.monotonic() - self.started)
        require(remaining >= 1 and wall_remaining > 0, "TOTAL_BUDGET_STOP")
        require(len(self.commands) < COMMAND_CAP, "COMMAND_COUNT_CAP")
        require(stdout_cap in (OUTPUT_CAP, ASM_OUTPUT_CAP), "UNAPPROVED_STDOUT_CAP")
        stdout_path, stderr_path = self.folder / (label + ".stdout"), self.folder / (label + ".stderr")

        def setup():
            os.setsid()
            os.sched_setaffinity(0, set(self.affinity))
            limit = max(1, math.floor(remaining))
            resource.setrlimit(resource.RLIMIT_CPU, (limit, limit))
            resource.setrlimit(resource.RLIMIT_FSIZE, (16777216, 16777216))
            resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        begin, reason, usage, proc = time.monotonic(), None, None, None
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            proc = subprocess.Popen(argv, cwd=cwd, env=self.env, stdout=stdout, stderr=stderr,
                                    preexec_fn=setup)
            try:
                while True:
                    got, status, usage = os.wait4(proc.pid, os.WNOHANG)
                    if got:
                        break
                    if time.monotonic() - begin >= min(per_child_wall, wall_remaining):
                        reason = "WALL_CAP"
                    if self.total_cpu + group_live_cpu(proc.pid) >= CPU_CAP - CPU_RESERVE:
                        reason = "TOTAL_CPU_CAP_RESERVE"
                    if stdout_path.stat().st_size > stdout_cap or stderr_path.stat().st_size > OUTPUT_CAP:
                        reason = "OUTPUT_CAP"
                    if reason:
                        os.killpg(proc.pid, signal.SIGKILL)
                        _, status, usage = os.wait4(proc.pid, 0)
                        break
                    time.sleep(0.05)
                proc.returncode = os.waitstatus_to_exitcode(status)
            except Exception as error:
                reason = "MONITOR_ERROR: " + type(error).__name__ + ": " + str(error)
            finally:
                if proc.returncode is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    _, status, usage = os.wait4(proc.pid, 0)
                    proc.returncode = os.waitstatus_to_exitcode(status)
                else:
                    # No descendants are allowed to remain after the direct child.
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        cpu = usage.ru_utime + usage.ru_stime
        self.total_cpu += cpu
        raw = stdout_path.read_bytes()
        error = stderr_path.read_bytes()
        bounded = len(raw) <= stdout_cap and len(error) <= OUTPUT_CAP
        rec = {"label": label, "argv": argv, "returncode": proc.returncode,
               "stop_reason": reason, "outer_wall_seconds": time.monotonic() - begin,
               "child_user_cpu_seconds": usage.ru_utime, "child_system_cpu_seconds": usage.ru_stime,
               "child_cpu_seconds": cpu, "cumulative_child_cpu_seconds": self.total_cpu,
               "voluntary_context_switches": usage.ru_nvcsw,
               "involuntary_context_switches": usage.ru_nivcsw,
               "stdout": raw[:stdout_cap].decode("utf-8", errors="replace"),
               "stderr": error[:OUTPUT_CAP].decode("utf-8", errors="replace"),
               "output_complete": bounded, "stdout_cap_bytes": stdout_cap,
               "stdout_sha256": hashlib.sha256(raw).hexdigest(), "affinity": self.affinity,
               "omp_environment": {k: v for k, v in self.env.items() if k.startswith("OMP_")}}
        self.commands.append(rec)
        emit("command", rec)
        require(bounded and proc.returncode == 0 and reason is None, "CHILD_FAILED: " + label)
        require(not error, "CHILD_STDERR: " + label)
        require(self.total_cpu < CPU_CAP and time.monotonic() - self.started < WALL_CAP,
                "POST_CHILD_TOTAL_CAP")
        return rec["stdout"]


def derive_h6_kernel(h4_body):
    require(h4_body.count(b'#include "h4_queue.h"') == 1, "H4_INCLUDE_COUNT")
    require(h4_body.count(KERNEL_ORDER_BEFORE) == 1, "H4_RUN_ORDER_COUNT")
    body = h4_body.replace(b'#include "h4_queue.h"', b'#include "h6_queue.h"', 1)
    body = body.replace(KERNEL_ORDER_BEFORE, KERNEL_ORDER_AFTER, 1)
    require(hashlib.sha256(body).hexdigest() == H6_KERNEL_SHA, "H6_EXACT_KERNEL_HASH")
    return body


def execute():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "MANUAL_GITHUB_ACTIONS_ONLY")
    require(os.environ.get("GITHUB_REPOSITORY") == REPO, "REPOSITORY_GUARD")
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "EVENT_GUARD")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "NO_RERUN")
    require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "GITHUB_HOSTED_ONLY")
    require(os.environ.get("RUNNER_OS") == "Linux" and os.environ.get("RUNNER_ARCH") == "X64",
            "STANDARD_LINUX_X64_ONLY")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    require(event.get("repository", {}).get("private") is False, "PUBLIC_REPOSITORY_ONLY")
    require(platform.machine() == "x86_64", "ARCHITECTURE_GUARD")
    workflow_sha = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    require(re.fullmatch(r"[0-9a-f]{40}", workflow_sha) is not None, "WORKFLOW_SHA_GUARD")
    require(run_id.isdecimal(), "RUN_ID_GUARD")
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    require(Path(__file__).resolve() == workspace / "tools" / "portability_probe.py", "SCRIPT_PATH_GUARD")
    folder = workspace / "work" / ("h6-three-arm-run-" + run_id)
    folder.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows, failure, budget, expected_paths = [], None, None, {}
    proofs_passed, sentinel_passed, assembly_captured = False, False, False
    stats, metadata, assembly_records = {}, {}, {}
    expected_paths[Path(__file__).resolve()] = sha(Path(__file__))
    workflow_path = workspace / ".github/workflows/portability.yml"
    expected_paths[workflow_path] = sha(workflow_path)
    save(folder / "started.json", {"workflow_commit": workflow_sha, "run_id": run_id,
                                   "probe_sha256": sha(Path(__file__)), "automatic_retry": False})
    try:
        host = topology()
        metadata = {"workflow_commit": workflow_sha, "probe_sha256": sha(Path(__file__)),
                    "workflow_sha256": sha(workflow_path), "run_id": run_id, "run_attempt": 1,
                    "topology": host, "os_release": Path("/etc/os-release").read_text(),
                    "source_commit": SOURCE_COMMIT, "upstream_commit": UPSTREAM_COMMIT,
                    "caps": {"child_cpu_seconds": CPU_CAP, "controller_wall_seconds": WALL_CAP,
                             "per_child_wall_seconds": 60, "cpu_reserve_seconds": CPU_RESERVE,
                             "command_cap": COMMAND_CAP, "planned_commands": PLANNED_COMMANDS,
                             "assembly_stdout_bytes_each": ASM_OUTPUT_CAP},
                    "comparison": "A original baseline, B exact H4, C H6 D2 two-slot consume-first helper",
                    "official_reference_or_prize_result": False,
                    "licence": "MIT; Copyright (c) 2026 Peter Rizun; repository LICENSE retained"}
        require('ID=ubuntu' in metadata["os_release"] and 'VERSION_ID="24.04"' in metadata["os_release"],
                "UBUNTU_24_04_ONLY")
        emit("environment", metadata)
        source = folder / "source"
        for name, digest in SOURCE_HASHES.items():
            path = source / name
            url = "https://raw.githubusercontent.com/" + REPO + "/" + SOURCE_COMMIT + "/" + name
            fetch_exact(url, path, digest, started)
            expected_paths[path] = digest
        baseline = source / "cpu/baseline_kernel.c"
        fetch_exact(UPSTREAM_URL, baseline, BASELINE_SHA, started)
        expected_paths[baseline] = BASELINE_SHA
        # All network acquisition ends here; fixed embedded/derived bytes follow.
        for name, blob, digest in (("h6_queue.h", H6_HELPER_B64, H6_HELPER_SHA),
                                    ("queue_unit.c", SENTINEL_B64, SENTINEL_SHA)):
            body = base64.b64decode(blob, validate=True)
            require(hashlib.sha256(body).hexdigest() == digest, "EMBEDDED_SOURCE_HASH_MISMATCH")
            path = source / "cpu" / name
            path.write_bytes(body)
            expected_paths[path] = digest
            emit("embedded_source", {"path": str(path.relative_to(workspace)), "sha256": digest,
                                     "bytes": len(body), "licence": "MIT"})
        h4_body = (source / "cpu/h4_kernel.c").read_bytes()
        h6_body = derive_h6_kernel(h4_body)
        h6_kernel = source / "cpu/h6_kernel.c"
        h6_kernel.write_bytes(h6_body)
        expected_paths[h6_kernel] = H6_KERNEL_SHA
        emit("derived_source", {"path": str(h6_kernel.relative_to(workspace)),
                                "sha256": H6_KERNEL_SHA, "only_changes": ["H6 helper include", "consume i-2 before enqueue i"]})
        golden = parse_vectors((source / "vectors.txt").read_text())
        budget = Budget(folder, host["selected_one_per_guest_core"], started)
        compiler, objdump = "/usr/bin/gcc-13", "/usr/bin/objdump"
        require(Path(compiler).is_file(), "GCC13_NOT_INSTALLED_STOP_NO_INSTALL")
        require(Path(objdump).is_file(), "OBJDUMP_NOT_INSTALLED_STOP_NO_INSTALL")
        version = budget.run("compiler-version", [compiler, "--version"], source)
        require(re.search(r"\b13\.\d", version) is not None, "GCC13_VERSION_GUARD")
        binaries = {}
        for variant, kernel in (("A", "baseline_kernel.c"), ("B", "h4_kernel.c"), ("C", "h6_kernel.c")):
            exe = folder / ("driver-" + variant)
            argv = [compiler, "-O3", "-march=native", "-fopenmp",
                    '-DSOURCE_FILE="' + kernel + '"', "driver.c", "sha256.c", "-o", str(exe)]
            budget.run("build-" + variant, argv, source / "cpu")
            binaries[variant] = exe
            expected_paths[exe] = sha(exe)
        emit("binary_binding", {v: {"path": str(p.relative_to(workspace)), "sha256": sha(p)}
                                for v, p in binaries.items()})
        for variant in "ABC":
            exe = binaries[variant]
            control = budget.run("sha-control-" + variant, [str(exe), "sha-control"], folder)
            require(control.strip() == SHA_ABC, "SHA_CONTROL_MISMATCH")
            proof = budget.run("eight-full-vectors-" + variant,
                               [str(exe), "vectors", str(source / "vectors.txt")], folder)
            require(parse_vectors(proof) == golden, "FULL_VECTOR_MISMATCH")
            emit("correctness", {"variant": variant, "full_vectors_passed": 8,
                                 "columns": ["nonce", "SHA256", "fold", "full_state"],
                                 "sha_abc_control": True})
        proofs_passed = True
        unit_exe = folder / "h6-queue-unit"
        budget.run("build-H6-sentinel", [compiler, "-O3", "-march=native", "-fopenmp",
                                        "queue_unit.c", "-o", str(unit_exe)], source / "cpu")
        expected_paths[unit_exe] = sha(unit_exe)
        unit_output = budget.run("run-H6-sentinel", [str(unit_exe)], folder)
        require(unit_output.strip() == SENTINEL_EXPECTED, "H6_SENTINEL_OUTPUT_MISMATCH")
        sentinel_passed = True
        emit("sentinel", {"passed": True, "source_sha256": SENTINEL_SHA,
                          "binary_sha256": sha(unit_exe), "full_output": unit_output})
        for variant in "BC":
            label = "native-hash-state-" + variant
            raw = budget.run(label, [objdump, "-d", "-M", "intel", "--disassemble=hash_state",
                                     str(binaries[variant])], folder, stdout_cap=ASM_OUTPUT_CAP)
            record = validate_assembly(raw)
            assembly_file = folder / (label + ".stdout")
            expected_paths[assembly_file] = sha(assembly_file)
            record.update({"variant": variant, "binary_sha256": sha(binaries[variant]),
                           "stdout_sha256": sha(assembly_file), "stdout_bytes": assembly_file.stat().st_size,
                           "stdout_path": str(assembly_file.relative_to(workspace))})
            assembly_records[variant] = record
            emit("assembly_capture", record)
        assembly_captured = set(assembly_records) == {"B", "C"}
        checksum = None
        for index, (phase, variant) in enumerate(SCHEDULE, 1):
            raw = budget.run("%02d-%s-%s" % (index, phase, variant),
                             [str(binaries[variant]), "bench", str(COUNT), str(host["threads"]),
                              "0000000000000000"], folder)
            driver = parse_driver(raw, host["threads"])
            if checksum is None:
                checksum = driver["checksum_hex"]
            require(driver["checksum_hex"] == checksum, "CROSS_RUN_OR_VARIANT_CHECKSUM_MISMATCH")
            row = {"index": index, "phase": phase, "variant": variant, "count": COUNT,
                   "first_nonce_hex": "0000000000000000", "epoch": "epoch0",
                   "driver": driver, "rate_hps": COUNT / driver["wall_seconds"]}
            rows.append(row)
            emit("measurement", row)
            if phase == "aa" and aa_preflight(rows)["complete"]:
                require(aa_preflight(rows)["passed"], "AA_NOISE_STOP_BEFORE_MAIN_NO_RETRY")
        require(len(budget.commands) == PLANNED_COMMANDS, "PLANNED_COMMAND_COUNT_MISMATCH")
    except Exception as error:
        failure = type(error).__name__ + ": " + str(error)
    changed = [str(p.relative_to(workspace)) for p, digest in expected_paths.items()
               if not p.is_file() or sha(p) != digest]
    if changed:
        failure = "POST_RUN_HASH_FAILURE: " + repr(changed)
    stats = analysis(rows)
    hashes_ok = not changed and len(expected_paths) == EXPECTED_HASHED_FILES
    preflight_passed = proofs_passed and sentinel_passed and assembly_captured
    valid = effective_valid(failure, stats, preflight_passed, hashes_ok)
    if failure is None and not valid:
        failure = "DESCRIPTIVE_QUALITY_OR_PREFLIGHT_FAILURE_NO_RETRY"
    result = {"status": "COMPLETED_MEASUREMENTS_PENDING_ROOT_ASSEMBLY_REVIEW" if valid else "STOP_NO_RETRY",
              "failure": failure, "metadata": metadata,
              "three_full_proofs_and_SHA_passed": proofs_passed, "H6_sentinel_passed": sentinel_passed,
              "assembly_captured": assembly_captured, "assembly": assembly_records,
              "assembly_semantic_review_status": "PENDING_ROOT_REVIEW" if assembly_captured else "NOT_AVAILABLE",
              "speedup_or_causal_conclusion": "NOT_ADJUDICATED_BY_AUTOMATION",
              "source_binary_and_capture_hashes_verified_after": hashes_ok, "changed_inputs": changed,
              "source_binary_and_capture_sha256": {str(p.relative_to(workspace)): h for p, h in expected_paths.items()},
              "commands": budget.commands if budget else [], "runs": rows, "analysis": stats,
              "child_commands": len(budget.commands) if budget else 0,
              "child_cpu_seconds": budget.total_cpu if budget else 0.0,
              "controller_wall_seconds": time.monotonic() - started,
              "effective_measurement_valid": valid, "automatic_retry": False,
              "interpretation": "All samples retained. Descriptive engineering numerics, not confidence intervals. "
                  "Root must inspect actual B/C assembly and all logs before interpreting speed, consume/enqueue order, v8 spills, prefetch placement or stack changes. "
                  "Only this guest and original baseline; no physical P-core, current-champion, i7-12700KF, "
                  "official threshold, award or income inference. Partial, failed or noisy batches are invalid."}
    save(folder / "result.json", result)
    emit("result", result)
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])
    require(summary_path.resolve().is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()),
            "SUMMARY_PATH_OUTSIDE_RUNNER_TEMP")
    summary = "## Finite offline three-arm pilot\n\nStatus: **" + result["status"] + "**\n\n"
    summary += "Complete main samples: " + str(stats.get("completed_main_runs", 0)) + "/18.\n\n"
    if valid:
        summary += "Provisional descriptive ratios of arithmetic means, root review pending:\n\n"
        for key, comparison in stats["comparisons"].items():
            summary += "- " + key + ": %.6f%% relative difference.\n" % comparison["gain_percent"]
        summary += "\n"
    summary += result["interpretation"] + "\n\nRaw commands, assembly, outputs, hashes and all estimators are in the job log.\n"
    summary_path.write_text(summary, encoding="utf-8")
    return 0 if valid else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-approved-manual-pilot", action="store_true", required=True)
    parser.parse_args()
    raise SystemExit(execute())
