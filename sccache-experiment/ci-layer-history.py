"""For each commit on ioc-adsimdetector main, find the first developer-stage
Docker step it invalidates, and cost layered vs flat rebuilds with R0 cold
per-step times measured in the sccache experiment."""
import subprocess, re, sys, collections
# usage: ci-layer-history.py IOC_CLONE IBEK_SUPPORT_CLONE [--all]
#   IOC_CLONE needs full main history; IBEK_SUPPORT_CLONE needs full history.
#   --all: every non-merge commit (approximates PR pushes) instead of first-parent merges.
IOC = sys.argv[1]
IBS = sys.argv[2]
ALL = "--all" in sys.argv
T = dict(iocStats=27, sequencer=12, sscan=13, calc=13, asyn=19, busy=11, autosave=11,
         pvlogging=9, ADCore=118, ffmpegServer=41, ADSimDetector=15, ioc=8)
UNKNOWN = 15
def git(*a, repo=IOC):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout
def steps(rev):
    """ordered developer-stage steps: list of (key, instruction-group text)"""
    df = git("show", f"{rev}:Dockerfile")
    out = []; cur = []
    for line in df.splitlines():
        if re.match(r"\s*FROM\b.*\bAS\s+runtime", line, re.I): break
        if not line.strip() or line.lstrip().startswith("#"): continue
        cur.append(line.strip())
        m = re.search(r"(?:ansible\.sh|install\.sh)\s+(\S+)|ibek-support/(\w+)/install\.sh|RUN.*\bioc\b", line)
        if line.lstrip().upper().startswith("RUN"):
            mod = None
            mm = re.search(r"ansible\.sh\s+(\S+)", line) or re.search(r"ibek-support/([\w-]+)/install\.sh", line) \
                 or re.search(r"(\w+)/install\.sh", line)
            grp = "\n".join(cur)
            if re.search(r"^COPY ioc\b", grp, re.M) or re.search(r"ansible\.sh\s+ioc\b", line): mod = "ioc"
            elif mm: mod = mm.group(1)
            out.append((mod or "pre", "\n".join(cur))); cur = []
    if cur: out.append(("post", "\n".join(cur)))
    return out
def cost(sts, i):  # cost of re-running steps i..end
    return sum(T.get(k, UNKNOWN if k not in ("pre", "post") else 0) for k, _ in sts[i:])
def sub_rev(rev):
    l = git("ls-tree", rev, "ibek-support").split()
    return l[2] if len(l) > 2 else None
revs = git("log", "--no-merges" if ALL else "--first-parent", "--format=%h %ad", "--date=short", "origin/main").split("\n")
rows = []
for r in revs:
    if not r.strip(): continue
    h, d = r.split(); p = git("rev-parse", "--short", f"{h}^").strip()
    if not p: continue
    try: s_new = steps(h); s_old = steps(p)
    except Exception: continue
    if not s_new: continue
    files = git("diff", "--name-only", p, h).split()
    first = None
    # Dockerfile instruction change
    for i, (a, b) in enumerate(zip(s_new, s_old)):
        if a[1] != b[1]: first = i; break
    else:
        if len(s_new) != len(s_old): first = min(len(s_new), len(s_old))
    def idx_of(pred):
        for i, (k, txt) in enumerate(s_new):
            if pred(k, txt): return i
    cand = []
    if first is not None: cand.append(first)
    if "requirements.txt" in files: cand.append(0)
    if any(f.startswith("ioc/") for f in files):
        j = idx_of(lambda k, t: k == "ioc"); cand.append(j if j is not None else len(s_new) - 1)
    if "ibek-support" in files:
        a, b = sub_rev(p), sub_rev(h)
        if a and b:
            ch = git("diff", "--name-only", a, b, repo=IBS).split()
            if not ch and git("cat-file", "-t", b, repo=IBS).strip() != "commit": ch = ["_ansible/?"]
            tops = {c.split("/")[0] for c in ch}
            for i, (k, txt) in enumerate(s_new):
                if any(re.search(rf"ibek-support/{re.escape(t)}\b", txt) or (t == k) for t in tops):
                    cand.append(i); break
            else:
                if tops: cand.append(None)  # changed only modules not in the image
    cand = [c for c in cand if c is not None]
    full = cost(s_new, 0); ioc_i = idx_of(lambda k, t: k == "ioc")
    if not cand:
        kind, lay, flat = "no dev-stage change", 0, 0
    else:
        i = min(cand); lay = cost(s_new, i)
        if ioc_i is not None and i >= ioc_i: kind, flat = "ioc only", lay
        else:
            flat = full
            kind = "support (from %s)" % s_new[i][0]
    rows.append((d, h, kind, lay, flat))
import statistics
def summ(rs, label):
    n = len(rs); c = collections.Counter(r[2].split(" (")[0] for r in rs)
    L = sum(r[3] for r in rs); F = sum(r[4] for r in rs)
    print(f"\n{label}: {n} commits; " + ", ".join(f"{k}: {v}" for k, v in c.items()))
    print(f"  layered total {L/60:.0f} min, flat total {F/60:.0f} min, extra {(F-L)/60:.0f} min ({(F-L)/max(n,1):.0f} s/commit avg)")
    sup = [r for r in rs if r[2].startswith("support")]
    if sup:
        print(f"  support-changing commits: layered mean {statistics.mean(r[3] for r in sup):.0f} s, flat {statistics.mean(r[4] for r in sup):.0f} s")
        print("  first invalidated:", collections.Counter(r[2] for r in sup).most_common())
for r in rows: print(*r, sep="\t")
summ(rows, "all history")
summ([r for r in rows if r[0] >= "2025-11-01"], "last 12 months")
