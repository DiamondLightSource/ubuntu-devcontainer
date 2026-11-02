#!/usr/bin/env python3
"""Turn results/<run>/ artifacts from run-experiment.sh into results/results.md."""
import gzip
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RES = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
ORDER = ["R0", "R0b", "R0c", "R0d", "R0e", "R1", "R2a", "R2b", "R2c", "R2d", "R2e", "R2f", "R5a", "R5b", "R4", "R4b", "R4c",
         "R6", "R7rel", "R7a", "R7b", "R2shim", "R0shim", "R2dbg", "R7dbg", "R8a", "R8b", "R8c"]
DESC = {
    "R0": "no sccache, cold (baseline)",
    "R0b": "no sccache, cold (repeat)",
    "R0c": "no sccache, cold (repeat, after host restart)",
    "R0d": "no sccache, cold (repeat, after host restart)",
    "R0e": "no sccache, cold (repeat, after host restart)",
    "R1": "sccache, empty cache = release build",
    "R2a": "sccache warm (seeded from R1), direct mode on (default)",
    "R2b": "repeat of R2a",
    "R2c": "repeat of R2a",
    "R2d": "repeat of R2a (after host restart, interleaved with R0c-e)",
    "R2e": "repeat of R2a (after host restart, interleaved with R0c-e)",
    "R2f": "repeat of R2a (after host restart, interleaved with R0c-e)",
    "R5a": "warm, direct (preprocessor-cache) mode OFF",
    "R5b": "repeat of R5a",
    "R4": "warm + comment line inserted near top of asynDriver.h",
    "R4b": "warm + comment line appended at end of asynDriver.h",
    "R4c": "warm + real declaration added to asynDriver.h",
    "R6": "TUNING: warm + no .d dependency generation (HDEPENDS_FILES=)",
    "R2shim": "warm + timing shims (instrumented, not a headline number)",
    "R8a": "devcontainer plan: FROM released image (exp/release), re-run all ansible steps",
    "R8b": "repeat of R8a",
    "R8c": "repeat of R8a",
    "R0shim": "cold no sccache + timing shims (instrumented)",
    "R2dbg": "warm + SCCACHE_LOG=debug + shims (miss analysis only)",
    "R7rel": "PATCHED sccache (direct mode fixed), empty cache = release build",
    "R7a": "PATCHED sccache, warm (seeded from R7rel), direct mode on",
    "R7b": "repeat of R7a",
    "R7dbg": "PATCHED sccache warm + SCCACHE_LOG=debug (direct-mode hit check)",
}


def fnum(x, d=1):
    return "–" if x is None else f"{x:.{d}f}"


def load_jsonl(p):
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def parse_build_log(p):
    """Return list of (desc, seconds) for each executed docker build step."""
    desc, dur = {}, {}
    for line in p.read_text(errors="replace").splitlines():
        m = re.match(r"#(\d+) \[(\S+)\s+(\d+)/(\d+)\] (.*)", line)
        if m:
            desc[int(m.group(1))] = (m.group(2), m.group(5))
            continue
        m = re.match(r"#(\d+) DONE ([\d.]+)s", line)
        if m:
            dur[int(m.group(1))] = float(m.group(2))
    steps = []
    for k in sorted(desc):
        if k in dur:
            steps.append((desc[k][0], desc[k][1], dur[k]))
    return steps


def parse_time_v(p):
    d = {}
    for line in p.read_text().splitlines():
        k, _, v = line.strip().rpartition(": ")
        d[k] = v
    el = d.get("Elapsed (wall clock) time (h:mm:ss or m:ss)", "0:0")
    parts = [float(x) for x in el.split(":")]
    secs = 0.0
    for x in parts:
        secs = secs * 60 + x
    return {
        "wall": secs,
        "user": float(d.get("User time (seconds)", 0)),
        "sys": float(d.get("System time (seconds)", 0)),
        "cpu_pct": d.get("Percent of CPU this job got", "?"),
        "maxrss_mb": int(d.get("Maximum resident set size (kbytes)", 0)) / 1024,
    }


def task_category(t):
    n, a = t["name"].split(" : ", 1)[-1], t.get("action", "")
    if n == "Gathering Facts" or a in ("gather_facts", "setup", "ansible.builtin.setup"):
        return "facts"
    if a.endswith(("apt", "package", "get_url")) or "apt" in n.lower() or "download" in n.lower():
        return "apt"
    if a.endswith("git") or n.startswith("Clone ") or n.startswith("Get specific commit") \
            or n.startswith("Patch file"):
        return "clone"
    if n.startswith("Build module"):
        return "make"
    if n.startswith("Clean module"):
        return "make_clean"
    return "ansible_other"


def sccache_stats(p):
    if not p.exists():
        return None
    s = json.loads(p.read_text())["stats"]
    hits = sum(s["cache_hits"]["counts"].values())
    misses = sum(s["cache_misses"]["counts"].values())
    return {
        "requests": s["compile_requests"],
        "hits": hits,
        "misses": misses,
        "not_compile": s["requests_not_compile"],
        "not_cacheable": s["requests_not_cacheable"],
        "non_cacheable_compilations": s["non_cacheable_compilations"],
        "not_cached": dict(s.get("not_cached", {})),
        "unsupported": s["requests_unsupported_compiler"],
        "errors": sum(s["cache_errors"]["counts"].values()) + s["cache_read_errors"]
        + s["cache_write_errors"],
        "compile_fails": s["compile_fails"],
    }


def union_len(intervals):
    tot, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(intervals):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        tot += cur_e - cur_s
    return tot


def load_run(d):
    r = {"name": d.name}
    w = d / "wall.txt"
    if not w.exists() or not (d / "steps.jsonl").exists():
        return None
    t0, t1 = map(float, w.read_text().split())
    r["wall"] = t1 - t0
    r["steps"] = load_jsonl(d / "steps.jsonl")
    r["modules"] = [s["module"] for s in r["steps"]]
    r["docker_steps"] = parse_build_log(d / "build.log")
    # per module details
    per = {}
    for s in r["steps"]:
        m = s["module"]
        tasks = [t for t in load_jsonl(d / f"{m}.tasks.jsonl") if t["ev"] == "task"]
        pbs = [t for t in load_jsonl(d / f"{m}.tasks.jsonl") if t["ev"] == "pb_start"]
        cats = defaultdict(float)
        for t in tasks:
            cats[task_category(t)] += t["end"] - t["start"]
        first_task = min((t["start"] for t in tasks), default=s["ansible1"])
        last_end = max((t["end"] for t in tasks), default=s["ansible1"])
        cats["ansible_startup"] = first_task - s["ansible0"]
        cats["ansible_exit"] = s["ansible1"] - last_end
        cats["sccache_srv"] = (s["ready"] - s["start"]) + (s["end"] - s["ansible1"])
        cats["cascade_preclone"] = s["preclone1"] - s["preclone0"]
        makes = []
        for tf in sorted(d.glob(f"{m}.make.*.time")):
            args = (tf.with_suffix(".args")).read_text().splitlines()
            tv = parse_time_v(tf)
            tv["args"] = args[1] if len(args) > 1 else ""
            tv["cwd"] = args[0] if args else ""
            makes.append(tv)
        build = [x for x in makes if "clean" not in x["args"]]
        per[m] = {
            "total": s["end"] - s["start"],
            "cats": dict(cats),
            "make": sum(x["wall"] for x in build),
            "make_cpu": sum(x["user"] + x["sys"] for x in build),
            "makes": makes,
            "sc": sccache_stats(d / f"{m}.sccache.json"),
            "cache_bytes": s.get("cache_bytes", 0),
        }
    r["per"] = per
    # aggregate sccache
    agg = defaultdict(int)
    nc = defaultdict(int)
    have = False
    for m, p in per.items():
        if p["sc"]:
            have = True
            for k in ("requests", "hits", "misses", "not_compile", "not_cacheable",
                      "non_cacheable_compilations", "unsupported", "errors", "compile_fails"):
                agg[k] += p["sc"][k]
            for k, v in p["sc"]["not_cached"].items():
                nc[k] += v
    r["sc"] = dict(agg) if have else None
    r["not_cached"] = dict(nc)
    for f in ("image_bytes", "final_cache_bytes", "seed_cache_bytes"):
        p = d / f
        r[f] = int(p.read_text().strip() or 0) if p.exists() and p.read_text().strip() else None
    r["shim"] = (d / "shim.log")
    return r


def shim_breakdown(path):
    """category -> (count, summed seconds, union wall seconds)"""
    if not path.exists():
        return None
    by = defaultdict(list)
    per_mod = defaultdict(lambda: defaultdict(list))
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split(" ")
        if len(parts) < 5:
            continue
        k, s, e, mod = parts[0], float(parts[1]), float(parts[2]), parts[3]
        by[k].append((s, e))
        per_mod[mod][k].append((s, e))
    out = {}
    for k, iv in by.items():
        out[k] = (len(iv), sum(e - s for s, e in iv), union_len(iv))
    return out, per_mod


def misses_from_debug(d):
    """List compile misses from SCCACHE_LOG=debug logs, attach cwd/source via shim log."""
    shim_src = defaultdict(list)  # (module, objbase) -> [(cwd, src)]
    sp = d / "shim.log"
    if sp.exists():
        for line in sp.read_text(errors="replace").splitlines():
            p = line.split(" ")
            if len(p) >= 6 and p[0] == "compile":
                src = p[5]
                base = Path(src).stem
                shim_src[(p[3], base)].append((p[4], src))
    misses = []
    stats = defaultdict(lambda: defaultdict(int))
    for lf in sorted(d.glob("*.sccache.log.gz")):
        mod = lf.name.split(".sccache.log")[0]
        with gzip.open(lf, "rt", errors="replace") as fh:
            for line in fh:
                if "compile result: cache miss" in line:
                    m = re.search(r"\[([^\]]+)\]: compile result", line)
                    obj = m.group(1) if m else "?"
                    misses.append((mod, obj, shim_src.get((mod, Path(obj).stem), [])))
                    stats[mod]["miss"] += 1
                elif "compile result: cache hit" in line:
                    stats[mod]["hit"] += 1
                elif "Preprocessor cache hit" in line:
                    stats[mod]["pp_hit"] += 1
                elif "too new" in line:
                    stats[mod]["too_new"] += 1
                elif "Preprocessor cache miss" in line or "preprocessor cache miss" in line:
                    stats[mod]["pp_miss"] += 1
                elif "Disabling preprocessor cache" in line:
                    stats[mod]["pp_disabled"] += 1
    return misses, stats


def main():
    runs = {}
    for d in sorted(RES.iterdir()) if RES.exists() else []:
        if d.is_dir():
            r = load_run(d)
            if r:
                runs[d.name] = r
    names = [n for n in ORDER if n in runs] + sorted(set(runs) - set(ORDER))
    out = []
    P = out.append
    mi = RES / "machine.txt"
    P("# sccache experiment results\n")
    if mi.exists():
        P("## Machine\n\n```\n" + mi.read_text().strip() + "\n```\n")
    if not runs:
        print("no runs"); return
    base = runs.get("R0")
    allmods = []
    for n in names:
        for m in runs[n]["modules"]:
            if m not in allmods:
                allmods.append(m)

    # ---------------------------------------------------------------- summary
    P("## Run summary\n")
    P("Wall = whole `docker build --no-cache --target developer` (includes uv pip, COPYs, "
      "manifest, seed COPY). Steps = sum of the instrumented `ansible.sh` steps. "
      "Hit rate = hits / (hits + misses) over cacheable compiles.\n")
    P("| run | description | wall s | % of R0 | ansible steps s | make (build) s | compiles | hits | misses | hit rate | -MM calls (not cacheable) | link/other (not compile) | cache after |")
    P("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for n in names:
        r = runs[n]
        steps = sum(p["total"] for p in r["per"].values())
        mk = sum(p["make"] for p in r["per"].values())
        sc = r["sc"]
        pct = f"{100*r['wall']/base['wall']:.0f}%" if base else "–"
        if sc:
            hr = sc["hits"] / max(1, sc["hits"] + sc["misses"])
            cols = [sc["requests"], sc["hits"], sc["misses"], f"{100*hr:.1f}%",
                    r["not_cached"].get("-MM", 0), sc["not_compile"]]
        else:
            cols = ["–"] * 6
        cache = f"{r['final_cache_bytes']/2**20:.0f} MiB" if r.get("final_cache_bytes") else "–"
        P(f"| {n} | {DESC.get(n, '')} | {r['wall']:.0f} | {pct} | {steps:.0f} | {mk:.0f} | "
          + " | ".join(str(c) for c in cols) + f" | {cache} |")
    P("")

    # variance
    def group(prefix):
        return [runs[n]["wall"] for n in names if re.fullmatch(prefix, n)]
    P("### Variance\n")
    P("| group | n | mean wall s | stdev s | min | max |")
    P("|---|---:|---:|---:|---:|---:|")
    for label, rx in (("R0 cold, all", r"R0[b-e]?"), ("R2 warm (direct on), all", r"R2[a-f]"),
                      ("R0 cold, before restart", r"R0b?"), ("R2 warm, before restart", r"R2[abc]"),
                      ("R0 cold, after restart (interleaved)", r"R0[cde]"),
                      ("R2 warm, after restart (interleaved)", r"R2[def]"),
                      ("R5 warm (direct off)", r"R5[ab]"), ("R7 warm (patched, direct on)", r"R7[ab]"),
                      ("R8 FROM released image", r"R8[a-c]")):
        v = group(rx)
        if v:
            sd = statistics.stdev(v) if len(v) > 1 else 0
            P(f"| {label} | {len(v)} | {statistics.mean(v):.0f} | {sd:.1f} | {min(v):.0f} | {max(v):.0f} |")
    P("")

    # -------------------------------------------------------- per module wall
    P("## Per-module step wall time (s)\n")
    P("Whole `RUN /exp/step.sh <module>` = ansible.sh incl. apt, clone, configure, make, make clean.\n")
    P("| run | " + " | ".join(allmods) + " |")
    P("|---|" + "---:|" * len(allmods))
    for n in names:
        per = runs[n]["per"]
        P(f"| {n} | " + " | ".join(fnum(per[m]["total"], 0) if m in per else "–" for m in allmods) + " |")
    P("")
    P("## Per-module `make` (build only) wall time (s), from `/usr/bin/time -v`\n")
    P("| run | " + " | ".join(allmods) + " |")
    P("|---|" + "---:|" * len(allmods))
    for n in names:
        per = runs[n]["per"]
        P(f"| {n} | " + " | ".join(fnum(per[m]["make"], 1) if m in per else "–" for m in allmods) + " |")
    P("")
    P("## Per-module sccache hit rate (hits/(hits+misses)) and misses\n")
    P("| run | " + " | ".join(allmods) + " |")
    P("|---|" + "---:|" * len(allmods))
    for n in names:
        per = runs[n]["per"]
        cells = []
        for m in allmods:
            sc = per.get(m, {}).get("sc") if m in per else None
            if not sc or sc["hits"] + sc["misses"] == 0:
                cells.append("–" if not sc else "n/a (0)")
            else:
                cells.append(f"{100*sc['hits']/(sc['hits']+sc['misses']):.0f}% ({sc['misses']}m)")
        P(f"| {n} | " + " | ".join(cells) + " |")
    P("")

    # --------------------------------------------------- category breakdowns
    cats = ["apt", "clone", "facts", "ansible_startup", "ansible_other", "make", "make_clean",
            "ansible_exit", "sccache_srv", "cascade_preclone"]
    P("## Where the time goes, by ansible task category (s, summed over modules)\n")
    P("Categories come from the ansible callback timer: `apt` = system/apt/get_url tasks, "
      "`clone` = git tasks, `facts` = fact gathering, `ansible_startup` = process start to first "
      "task, `ansible_other` = all other tasks (RELEASE fixups, patching, ibek, runtime lists), "
      "`make` / `make_clean` = the build and clean tasks, `sccache_srv` = start/zero/stats/stop of "
      "the sccache server in the wrapper (experiment overhead). `docker other` = wall minus "
      "ansible steps (uv pip install, COPY layers incl. seed cache COPY, manifest, export).\n")
    P("| run | " + " | ".join(cats) + " | docker other | wall |")
    P("|---|" + "---:|" * (len(cats) + 2))
    for n in names:
        r = runs[n]
        tot = defaultdict(float)
        for p in r["per"].values():
            for k, v in p["cats"].items():
                tot[k] += v
        steps = sum(p["total"] for p in r["per"].values())
        P(f"| {n} | " + " | ".join(fnum(tot.get(c, 0), 0) for c in cats)
          + f" | {r['wall']-steps:.0f} | {r['wall']:.0f} |")
    P("")
    # docker steps for one warm run
    for n in ("R0", "R1", "R2a"):
        if n in runs:
            P(f"### Docker build steps for {n} (s)\n")
            P("| step | s |")
            P("|---|---:|")
            for stage, d, s in runs[n]["docker_steps"]:
                if s >= 0.5:
                    P(f"| [{stage}] `{d[:90]}` | {s:.1f} |")
            P("")

    # --------------------------------------------------------- shim breakdown
    for n in ("R0shim", "R2shim", "R2dbg"):
        if n not in runs:
            continue
        sb = shim_breakdown(runs[n]["shim"])
        if not sb:
            continue
        b, per_mod = sb
        mk = sum(p["make"] for p in runs[n]["per"].values())
        P(f"## Inside make: tool breakdown for {n}\n")
        P("Each compiler-driver call (CC/CCC), perl call ($(PERL)) and msi call is wrapped by a "
          "bash shim that logs start/end ($EPOCHREALTIME). `sum` = summed durations (CPU-ish, "
          "overlapping under -j), `wall covered` = union of intervals, i.e. time during which at "
          f"least one such process was running. Total make (build) wall for this run: {mk:.0f} s. "
          "Shim overhead is a few ms per call, so these runs are not headline numbers.\n")
        P("| category | calls | sum s | wall covered s |")
        P("|---|---:|---:|---:|")
        groups = defaultdict(lambda: [0, 0.0, []])
        for k, (c, s, u) in sorted(b.items(), key=lambda kv: -kv[1][1]):
            P(f"| {k} | {c} | {s:.1f} | {u:.1f} |")
        # per module wall-covered for compile/dep/link/perl-any
        P("")
        P(f"### {n}: per-module wall covered (s) by category\n")
        kinds = ["compile", "dep", "link", "perl(any)", "msi", "make wall"]
        P("| module | " + " | ".join(kinds) + " |")
        P("|---|" + "---:|" * len(kinds))
        for m in allmods:
            if m not in per_mod:
                continue
            pm = per_mod[m]
            perl = [iv for k, ivs in pm.items() if k.startswith("perl") for iv in ivs]
            vals = [union_len(pm.get("compile", [])), union_len(pm.get("dep", [])),
                    union_len(pm.get("link", [])), union_len(perl), union_len(pm.get("msi", [])),
                    runs[n]["per"].get(m, {}).get("make", 0)]
            P(f"| {m} | " + " | ".join(f"{v:.1f}" for v in vals) + " |")
        P("")

    # ---------------------------------------------------------------- misses
    for dbg in ("R2dbg", "R7dbg"):
        if dbg not in runs:
            continue
        d = RES / dbg
        misses, st = misses_from_debug(d)
        P(f"## Warm-cache misses ({dbg}, SCCACHE_LOG=debug)\n")
        P("| module | hits | misses | preprocessor(direct)-cache hits | 'too new' headers | direct mode disabled |")
        P("|---|---:|---:|---:|---:|---:|")
        for m in allmods:
            if m in st:
                s = st[m]
                P(f"| {m} | {s['hit']} | {s['miss']} | {s['pp_hit']} | {s['too_new']} | {s['pp_disabled']} |")
        P("")
        if misses:
            P("| module | object | source (cwd) |")
            P("|---|---|---|")
            for mod, obj, srcs in misses[:300]:
                s = "; ".join(f"{src} ({cwd})" for cwd, src in srcs[:2]) or "?"
                P(f"| {mod} | {obj} | {s} |")
            P("")
        else:
            P("No compile misses recorded.\n")

    # ---------------------------------------------------- not cacheable reasons
    P("## Non-cacheable calls by reason (sccache `not_cached`)\n")
    P("| run | " + " | ".join(sorted({k for r in runs.values() for k in r['not_cached']})) + " |")
    keys = sorted({k for r in runs.values() for k in r['not_cached']})
    P("|---|" + "---:|" * len(keys))
    for n in names:
        P(f"| {n} | " + " | ".join(str(runs[n]["not_cached"].get(k, 0)) for k in keys) + " |")
    P("")

    # ---------------------------------------------------------------- sizes
    P("## Image and cache sizes\n")
    P("| run | image bytes (docker inspect) | seed cache | cache after |")
    P("|---|---:|---:|---:|")
    for n in names:
        r = runs[n]
        f = lambda b: f"{b/2**20:.0f} MiB" if b else "–"
        P(f"| {n} | {f(r.get('image_bytes'))} | {f(r.get('seed_cache_bytes'))} | {f(r.get('final_cache_bytes'))} |")
    P("")
    (RES / "results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
