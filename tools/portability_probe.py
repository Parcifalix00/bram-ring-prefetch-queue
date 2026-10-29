#!/usr/bin/env python3
"""One manually approved, finite offline pilot; no mining or networked kernel work.

This file is inert on import. The only network activity is a fixed, hash-checked
source acquisition before compilation. It never installs tools or retries work.
"""
import argparse
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
SCHEDULE = [("warmup", v) for v in "AB"] + [("aa", "A")] * 2 + [
    ("main", v) for v in "ABBABAAB"]
CPU_CAP = 900.0
WALL_CAP = 400.0
CPU_RESERVE = 4.0
OUTPUT_CAP = 131072
SOURCE_CAP = 524288


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


def aa_preflight(rows):
    rates = [r["rate_hps"] for r in rows if r["phase"] == "aa"]
    if len(rates) != 2:
        return {"complete": False, "passed": False}
    difference = abs(rates[1] - rates[0]) / statistics.mean(rates)
    return {"complete": True, "rates_hps": rates,
            "symmetric_relative_difference": difference, "limit": 0.05,
            "passed": difference <= 0.05}


def analysis(rows):
    main = [r for r in rows if r["phase"] == "main"]
    rates = {v: [r["rate_hps"] for r in main if r["variant"] == v] for v in "AB"}
    complete = ([(r["phase"], r["variant"]) for r in rows] == SCHEDULE
                and all(math.isfinite(r["rate_hps"]) and r["rate_hps"] > 0 for r in rows))
    result = {"complete": complete, "completed_main_runs": len(main),
              "all_main_rates_hps": rates, "aa_preflight": aa_preflight(rows)}
    if not complete:
        return result
    means = {v: statistics.mean(rates[v]) for v in "AB"}
    cvs = {v: statistics.stdev(rates[v]) / means[v] for v in "AB"}
    pairs = []
    for i in range(0, 8, 2):
        pair = main[i:i + 2]
        a = next(r["rate_hps"] for r in pair if r["variant"] == "A")
        b = next(r["rate_hps"] for r in pair if r["variant"] == "B")
        pairs.append({"pair": i // 2 + 1, "orientation": "".join(r["variant"] for r in pair),
                      "b_over_a": b / a, "gain_pp": 100 * (b / a - 1)})
    orientations = {s: statistics.mean(p["gain_pp"] for p in pairs if p["orientation"] == s)
                    for s in ("AB", "BA")}
    halves = []
    for part in (main[:4], main[4:]):
        a = statistics.mean(r["rate_hps"] for r in part if r["variant"] == "A")
        b = statistics.mean(r["rate_hps"] for r in part if r["variant"] == "B")
        halves.append(100 * (b / a - 1))
    gates = {
        "aa_relative_difference_at_most_5pct": result["aa_preflight"]["passed"],
        "orientation_difference_at_most_5pp": abs(orientations["AB"] - orientations["BA"]) <= 5,
        "half_session_gain_drift_at_most_5pp": abs(halves[1] - halves[0]) <= 5,
        "sample_cv_each_at_most_10pct": max(cvs.values()) <= 0.10,
    }
    result.update({"arithmetic_mean_hps_all_four_runs_each": means,
                   "primary_gain_percent": 100 * (means["B"] / means["A"] - 1),
                   "sample_cv": cvs, "paired_ratios": pairs,
                   "orientation_mean_gain_pp": orientations, "half_session_gain_pp": halves,
                   "quality_gates": gates, "quality_pass": all(gates.values())})
    return result


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

    def run(self, label, argv, cwd, per_child_wall=60):
        remaining = CPU_CAP - self.total_cpu - CPU_RESERVE
        wall_remaining = WALL_CAP - (time.monotonic() - self.started)
        require(remaining >= 1 and wall_remaining > 0, "TOTAL_BUDGET_STOP")
        require(len(self.commands) < 24, "COMMAND_COUNT_CAP")
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
                    if max(stdout_path.stat().st_size, stderr_path.stat().st_size) > OUTPUT_CAP:
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
        bounded = len(raw) <= OUTPUT_CAP and len(error) <= OUTPUT_CAP
        rec = {"label": label, "argv": argv, "returncode": proc.returncode,
               "stop_reason": reason, "outer_wall_seconds": time.monotonic() - begin,
               "child_user_cpu_seconds": usage.ru_utime, "child_system_cpu_seconds": usage.ru_stime,
               "child_cpu_seconds": cpu, "cumulative_child_cpu_seconds": self.total_cpu,
               "voluntary_context_switches": usage.ru_nvcsw,
               "involuntary_context_switches": usage.ru_nivcsw,
               "stdout": raw[:OUTPUT_CAP].decode("utf-8", errors="replace"),
               "stderr": error[:OUTPUT_CAP].decode("utf-8", errors="replace"),
               "output_complete": bounded, "affinity": self.affinity,
               "omp_environment": {k: v for k, v in self.env.items() if k.startswith("OMP_")}}
        self.commands.append(rec)
        emit("command", rec)
        require(bounded and proc.returncode == 0 and reason is None, "CHILD_FAILED: " + label)
        require(not error, "CHILD_STDERR: " + label)
        require(self.total_cpu < CPU_CAP and time.monotonic() - self.started < WALL_CAP,
                "POST_CHILD_TOTAL_CAP")
        return rec["stdout"]


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
    folder = workspace / "work" / ("portability-run-" + run_id)
    folder.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows, correctness, failure, budget, expected_paths = [], False, None, None, {}
    stats, metadata = {}, {}
    expected_paths[Path(__file__).resolve()] = sha(Path(__file__))
    expected_paths[workspace / ".github/workflows/portability.yml"] = sha(
        workspace / ".github/workflows/portability.yml")
    save(folder / "started.json", {"workflow_commit": workflow_sha, "run_id": run_id,
                                   "probe_sha256": sha(Path(__file__)), "automatic_retry": False})
    try:
        host = topology()
        metadata = {"workflow_commit": workflow_sha, "probe_sha256": sha(Path(__file__)),
                    "workflow_sha256": sha(workspace / ".github/workflows/portability.yml"),
                    "run_id": run_id, "run_attempt": 1, "topology": host,
                    "os_release": Path("/etc/os-release").read_text(),
                    "source_commit": SOURCE_COMMIT, "upstream_commit": UPSTREAM_COMMIT,
                    "caps": {"child_cpu_seconds": CPU_CAP, "controller_wall_seconds": WALL_CAP,
                             "per_child_wall_seconds": 60, "cpu_reserve_seconds": CPU_RESERVE},
                    "comparison": "B fixed H4 versus A original upstream baseline, not current champion",
                    "official_reference_or_prize_result": False}
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
        # All source acquisition ends here; no network functions are used below.
        golden = parse_vectors((source / "vectors.txt").read_text())
        budget = Budget(folder, host["selected_one_per_guest_core"], started)
        compiler = "/usr/bin/gcc-13"
        require(Path(compiler).is_file(), "GCC13_NOT_INSTALLED_STOP_NO_INSTALL")
        version = budget.run("compiler-version", [compiler, "--version"], source)
        require(re.search(r"\b13\.\d", version) is not None, "GCC13_VERSION_GUARD")
        binaries = {}
        for variant, kernel in (("A", "baseline_kernel.c"), ("B", "h4_kernel.c")):
            exe = folder / ("driver-" + variant)
            argv = [compiler, "-O3", "-march=native", "-fopenmp",
                    '-DSOURCE_FILE="' + kernel + '"', "driver.c", "sha256.c", "-o", str(exe)]
            budget.run("build-" + variant, argv, source / "cpu")
            binaries[variant] = exe
            expected_paths[exe] = sha(exe)
        emit("binary_binding", {v: {"path": str(p.relative_to(workspace)), "sha256": sha(p)}
                                for v, p in binaries.items()})
        for variant in "AB":
            exe = binaries[variant]
            control = budget.run("sha-control-" + variant, [str(exe), "sha-control"], folder)
            require(control.strip() == SHA_ABC, "SHA_CONTROL_MISMATCH")
            proof = budget.run("eight-full-vectors-" + variant,
                               [str(exe), "vectors", str(source / "vectors.txt")], folder)
            require(parse_vectors(proof) == golden, "FULL_VECTOR_MISMATCH")
            emit("correctness", {"variant": variant, "full_vectors_passed": 8,
                                 "columns": ["nonce", "SHA256", "fold", "full_state"],
                                 "sha_abc_control": True})
        correctness = True
        checksum = None
        for index, (phase, variant) in enumerate(SCHEDULE, 1):
            raw = budget.run("%02d-%s-%s" % (index, phase, variant),
                             [str(binaries[variant]), "bench", str(COUNT), str(host["threads"]),
                              "0000000000000000"], folder)
            driver = json.loads(raw)
            require(driver.get("mode") == "bounded_complete_digest" and driver.get("count") == COUNT
                    and driver.get("threads") == host["threads"]
                    and driver.get("first_nonce_hex") == "0000000000000000"
                    and driver.get("work") == WORK and driver.get("rate_claim") is False,
                    "DRIVER_METADATA_MISMATCH")
            seconds = driver.get("wall_seconds")
            require(isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
                    and math.isfinite(seconds) and seconds > 0, "INVALID_INTERNAL_WALL")
            require(re.fullmatch(r"[0-9a-f]{16}", driver.get("checksum_hex", "")) is not None,
                    "INVALID_CHECKSUM_FORMAT")
            if checksum is None:
                checksum = driver["checksum_hex"]
            require(driver["checksum_hex"] == checksum, "CROSS_RUN_OR_VARIANT_CHECKSUM_MISMATCH")
            row = {"index": index, "phase": phase, "variant": variant, "count": COUNT,
                   "first_nonce_hex": "0000000000000000", "epoch": "epoch0",
                   "driver": driver, "rate_hps": COUNT / seconds}
            rows.append(row)
            emit("measurement", row)
            if phase == "aa" and aa_preflight(rows)["complete"]:
                require(aa_preflight(rows)["passed"], "AA_NOISE_STOP_BEFORE_MAIN_NO_RETRY")
    except Exception as error:
        failure = type(error).__name__ + ": " + str(error)
    changed = [str(p.relative_to(workspace)) for p, digest in expected_paths.items()
               if not p.is_file() or sha(p) != digest]
    if changed:
        failure = "POST_RUN_HASH_FAILURE: " + repr(changed)
    stats = analysis(rows)
    hashes_ok = not changed and len(expected_paths) == len(SOURCE_HASHES) + 5
    valid = effective_valid(failure, stats, correctness, hashes_ok)
    if failure is None and not valid:
        failure = "DESCRIPTIVE_QUALITY_GATE_FAILURE_NO_RETRY"
    result = {"status": "COMPLETED_PORTABILITY_ONLY" if valid else "STOP_NO_RETRY",
              "failure": failure, "metadata": metadata, "correctness_passed": correctness,
              "source_and_binary_hashes_verified_after": hashes_ok, "changed_inputs": changed,
              "source_and_binary_sha256": {str(p.relative_to(workspace)): h for p, h in expected_paths.items()},
              "commands": budget.commands if budget else [], "runs": rows, "analysis": stats,
              "child_cpu_seconds": budget.total_cpu if budget else 0.0,
              "controller_wall_seconds": time.monotonic() - started,
              "effective_comparison_valid": valid, "automatic_retry": False,
              "interpretation": "All samples retained. Descriptive engineering gates, not confidence intervals. "
                  "Only this guest host and original baseline; no physical P-core, current-champion, "
                  "i7-12700KF, official threshold, award or income inference. "
                  "Partial, failed or noisy runs are not valid gains."}
    save(folder / "result.json", result)
    emit("result", result)
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])
    require(summary_path.resolve().is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()),
            "SUMMARY_PATH_OUTSIDE_RUNNER_TEMP")
    summary = "## Finite offline portability pilot\n\nStatus: **" + result["status"] + "**\n\n"
    summary += "Complete main samples: " + str(stats.get("completed_main_runs", 0)) + "/8.\n\n"
    if valid:
        summary += "Descriptive gain against the original baseline: %.6f%%.\n\n" % stats["primary_gain_percent"]
    summary += result["interpretation"] + "\n\nRaw commands, outputs, hashes and all estimators are in the job log.\n"
    summary_path.write_text(summary, encoding="utf-8")
    return 0 if valid else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-approved-manual-pilot", action="store_true", required=True)
    parser.parse_args()
    raise SystemExit(execute())
