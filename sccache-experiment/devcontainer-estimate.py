"""Estimate devcontainer build time at every commit of an IOC repo under four
strategies, diffing each commit against the most recent release tag (the image a
'FROM last' devcontainer would start from).  Per-step times are measured ones:
R0 (cold, FROM base, no sccache) and R8 (FROM released image, warm sccache).

usage: devcontainer-estimate.py IOC_CLONE IBEK_SUPPORT_CLONE   (both with full history + tags)
"""
import subprocess, re, sys, collections, statistics, importlib.util, os
spec = importlib.util.spec_from_file_location("h", os.path.join(os.path.dirname(__file__), "ci-layer-history.py"))
IOC, IBS = sys.argv[1], sys.argv[2]
def git(*a, repo=IOC):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout

# measured per-step seconds
R0 = dict(iocStats=27, sequencer=12, sscan=13, calc=13, asyn=19, busy=11, autosave=11,
          pvlogging=9, ADCore=118, ffmpegServer=41, ADSimDetector=15, ioc=8)
R8 = dict(iocStats=16, sequencer=8, sscan=8, calc=8, asyn=12, busy=8, autosave=8,
          pvlogging=7, ADCore=57, ffmpegServer=15, ADSimDetector=8, ioc=7)
UNK0, UNK8 = 15, 9            # modules no longer in the image (pvxs, ...)
COLD_FULL = 334               # R0 mean wall
SEEDED_FROM_BASE = 327        # R2 mean wall (base changed: FROM last impossible)
RERUN_ALL = 179               # R8 mean wall
DOCKER_R0 = 30                # wall minus steps in R0 runs
SKIP_OVERHEAD = 15            # assumed: uv pip, COPYs, layer export, ~0.5 s hash check per module

def steps(rev):
    df = git("show", f"{rev}:Dockerfile"); out = []; cur = []
    for line in df.splitlines():
        if re.match(r"\s*FROM\b.*\bAS\s+runtime", line, re.I): break
        if not line.strip() or line.lstrip().startswith("#"): continue
        cur.append(line.strip())
        if line.lstrip().upper().startswith("RUN"):
            grp = "\n".join(cur)
            mm = re.search(r"ansible\.sh\s+(\S+)", line) or re.search(r"([\w-]+)/install\.sh", line)
            if re.search(r"^COPY ioc\b", grp, re.M) or re.search(r"ansible\.sh\s+ioc\b", line): mod = "ioc"
            elif mm: mod = mm.group(1)
            else: mod = "pre"
            out.append((mod, grp)); cur = []
    return out
def base_lines(rev):
    df = git("show", f"{rev}:Dockerfile")
    return [l.strip() for l in df.splitlines()
            if re.match(r"\s*(FROM|ARG\s+(BASE|DEVELOPER|RUNTIME|REGISTRY|IMAGE_EXT|TARGET))", l)]
def sub_rev(rev):
    l = git("ls-tree", rev, "ibek-support").split()
    return l[2] if len(l) > 2 else None

def classify(tag, x):
    """-> (kind, first_changed_step_index or None, steps)"""
    s_new, s_old = steps(x), steps(tag)
    if base_lines(x) != base_lines(tag): return "base", 0, s_new, True
    files = git("diff", "--name-only", tag, x).split()
    cand = []
    old = dict((k, t) for k, t in s_old)
    for i, (k, t) in enumerate(s_new):
        if k == "pre": continue
        if old.get(k) != t: cand.append(i); break
    if "ibek-support" in files:
        a, b = sub_rev(tag), sub_rev(x)
        if a and b:
            tops = {c.split("/")[0] for c in git("diff", "--name-only", a, b, repo=IBS).split()}
            for i, (k, t) in enumerate(s_new):
                if k != "pre" and (k in tops or any(f"ibek-support/{d}" in t for d in tops)):
                    cand.append(i); break
    if any(f.startswith("ioc/") for f in files):
        cand += [i for i, (k, _) in enumerate(s_new) if k == "ioc"]
    req = "requirements.txt" in files
    pre_changed = [t for k, t in s_new if k == "pre"] != [t for k, t in s_old if k == "pre"]
    i = min(cand) if cand else None
    if i is None: kind = "requirements/pre only" if (req or pre_changed) else "no build change"
    else: kind = "ioc only" if s_new[i][0] == "ioc" else f"modules from {s_new[i][0]}"
    return kind, i, s_new, (req or pre_changed)

def costs(kind, i, s, req):
    tail = s[i:] if i is not None else []
    r0 = lambda ss: sum(R0.get(k, UNK0) for k, _ in ss if k != "pre")
    r8 = lambda ss: sum(R8.get(k, UNK8) for k, _ in ss if k != "pre")
    if kind == "base":
        return dict(cold=COLD_FULL, layered=COLD_FULL, rerun=SEEDED_FROM_BASE,
                    skip=SEEDED_FROM_BASE, skip_req=SEEDED_FROM_BASE)
    layered = DOCKER_R0 + (r0(s) if req else r0(tail))    # requirements COPY sits above every module layer
    skip = SKIP_OVERHEAD + r8(tail)
    skip_req = SKIP_OVERHEAD + (r8(s) if req else r8(tail))  # if ibek/pvi version is part of every module hash
    return dict(cold=COLD_FULL, layered=layered, rerun=RERUN_ALL, skip=skip, skip_req=skip_req)

commits = git("log", "--no-merges", "--format=%h %ad", "--date=short", "origin/main").split("\n")
rows = []
for c in commits:
    if not c.strip(): continue
    x, d = c.split()
    tag = git("describe", "--tags", "--abbrev=0", x).strip()
    if not tag or git("rev-parse", f"{tag}^{{commit}}").strip().startswith(git("rev-parse", x).strip()):
        continue                              # untagged prehistory, or the commit *is* a release
    try: kind, i, s, req = classify(tag, x)
    except Exception: continue
    if not s: continue
    rows.append((d, x, tag, kind, costs(kind, i, s, req)))
cols = ["cold", "layered", "rerun", "skip", "skip_req"]
names = {"cold": "cold FROM base (no cache)", "layered": "today: layered, layer cache = last release",
         "rerun": "FROM last, re-run all ansible", "skip": "FROM last + per-module hash skip",
         "skip_req": "  same, ibek/pvi version in every hash"}
for r in rows: print(r[0], r[1], r[2], r[3], *[r[4][c] for c in cols], sep="\t")
def summ(rs, label):
    print(f"\n## {label}: {len(rs)} commits")
    print("  kinds:", dict(collections.Counter(r[3].split(" from")[0] if r[3].startswith("modules") else r[3] for r in rs)))
    for c in cols:
        v = [r[4][c] for r in rs]
        print(f"  {names[c]:45} mean {statistics.mean(v):5.0f} s   median {statistics.median(v):5.0f} s   total {sum(v)/60:5.0f} min")
summ(rows, "all history")
summ([r for r in rows if r[0] >= "2025-11-03"], "last 12 months")
