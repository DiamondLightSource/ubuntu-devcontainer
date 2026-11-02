#!/usr/bin/env bash
# =============================================================================
# sccache experiment for epics-containers IOC developer images
#
# Question: if epics-base-developer ships sccache (empty cache, hooked into the
# EPICS compiler variables), and an ioc-* release build populates that cache,
# how cheap is it for a devcontainer to re-run *every* ansible step of the IOC
# Dockerfile from scratch, seeded with the release image's cache?
#
# What it does (all from scratch, reproducible):
#   1. clones ioc-adsimdetector at a pinned commit (+ its ibek-support submodule)
#   2. builds exp/net          = epics-base-developer + sandbox proxy CA (only if
#                                a proxy CA is configured; plumbing, all runs)
#   3. builds exp/sccache-base = exp/net + sccache + CONFIG_SITE hook, and
#                                verifies sccache really sees EPICS compiles
#   4. rewrites the IOC Dockerfile: every `RUN ansible.sh X` becomes an
#      instrumented `RUN /exp/step.sh X` (ansible task timer callback, sccache
#      stats per module, /usr/bin/time -v around each top-level make)
#   5. runs the build variants listed in RUNS (see run_variant below) with
#      `docker build --no-cache --target developer`
#   6. writes results/<run>/... and results/results.md (via analyse.py)
#
# Usage:  ./run-experiment.sh                # all runs
#         RUNS="R0 R1 R2a" ./run-experiment.sh
#         ./run-experiment.sh analyse        # only regenerate results.md
#
# Requirements: docker (with BuildKit), git, curl, python3, ~30 GB free disk.
# =============================================================================
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${WORK:-/var/tmp/sccache-exp}
RESULTS=${RESULTS:-$HERE/results}

BASE_IMAGE=${BASE_IMAGE:-ghcr.io/epics-containers/epics-base-developer:7.0.10ec2}
IOC_REPO=${IOC_REPO:-https://github.com/epics-containers/ioc-adsimdetector}
IOC_COMMIT=${IOC_COMMIT:-2d6a48e716b43c7099735f7044bdba6f6c891fb1}
SCCACHE_VERSION=${SCCACHE_VERSION:-0.19.0}
SCCACHE_SHA256=${SCCACHE_SHA256:-aa73c7270c997894038c0d8f0d297865f57569e1687883322bc431713d4bb9dd}
# R7*: sccache with a one-line fix so preprocessor (direct) mode works with
# EPICS's "../file.c" relative source paths (see sccache-relative-path-direct-mode.patch)
SCCACHE_PATCH=${SCCACHE_PATCH:-$HERE/sccache-relative-path-direct-mode.patch}
# proxy CA bundle for sandboxed environments (Claude Code cloud); optional
PROXY_CA_BUNDLE=${PROXY_CA_BUNDLE:-/root/.ccr/ca-bundle.crt}

# Order matters: R1 produces the "release" image whose /sccache seeds the rest.
DEFAULT_RUNS="R0 R1 R2a R2b R2c R5a R5b R4 R2dbg R2shim R0shim R6 R7rel R7a R7b R7dbg R4b R4c R0b"
RUNS=${RUNS:-$DEFAULT_RUNS}

log() { printf '\n[%(%F %T)T] %s\n' -1 "$*" >&2; }

# ---------------------------------------------------------------------------
machine_info() {
    mkdir -p "$RESULTS"
    {
        echo "date: $(date -u +%FT%TZ)"
        echo "host_os: $(. /etc/os-release; echo "$PRETTY_NAME")"
        echo "kernel: $(uname -r)"
        echo "nproc: $(nproc)"
        echo "cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | xargs)"
        echo "ram: $(free -g | awk '/Mem:/{print $2" GiB"}')"
        echo "disk_rotational_flag: $(lsblk -dno NAME,ROTA | tr '\n' ' ')"
        echo "docker_root_fs: $(df -hT /var/lib/docker | tail -1)"
        echo "docker: $(docker version --format '{{.Server.Version}}')"
        echo "base_image: $BASE_IMAGE"
        echo "base_image_digest: $(docker image inspect --format '{{index .RepoDigests 0}}' "$BASE_IMAGE" 2>/dev/null || echo n/a)"
        echo "gcc_in_base: $(docker run --rm "$BASE_IMAGE" gcc --version | head -1)"
        echo "nproc_in_container: $(docker run --rm "$BASE_IMAGE" nproc)"
        echo "ioc_repo: $IOC_REPO @ $IOC_COMMIT"
        echo "ibek_support: $(git -C "$WORK/ioc/ibek-support" rev-parse HEAD 2>/dev/null || echo n/a)"
        echo "sccache: $SCCACHE_VERSION (sha256 $SCCACHE_SHA256)"
    } > "$RESULTS/machine.txt"
    cat "$RESULTS/machine.txt"
}

# ---------------------------------------------------------------------------
prepare_sources() {
    mkdir -p "$WORK"
    if [[ ! -d $WORK/ioc/.git ]]; then
        git clone -q "$IOC_REPO" "$WORK/ioc"
    fi
    git -C "$WORK/ioc" fetch -q origin
    git -C "$WORK/ioc" checkout -q --force "$IOC_COMMIT"
    git -C "$WORK/ioc" submodule update -q --init --force
    git -C "$WORK/ioc" clean -qfdx
}

# ---------------------------------------------------------------------------
# helper files that end up in /exp inside the build (named build context "exp")
write_helpers() {
    local X=$WORK/exp-ctx
    rm -rf "$X"; mkdir -p "$X/callbacks" "$X/bin" "$X/shim"

    # --- per-module step wrapper -------------------------------------------
    cat > "$X/step.sh" <<'EOF'
#!/bin/bash
# Instrumented replacement for `RUN ansible.sh <module>`
set -euo pipefail
mod=$1; shift
R=/exp-results; mkdir -p "$R"
export EXP_MODULE=$mod
t_start=$EPOCHREALTIME
have_sccache=0; command -v sccache >/dev/null && have_sccache=1

if (( have_sccache )); then
    [[ -n ${EXP_DIRECT:-} ]] && export SCCACHE_DIRECT=$EXP_DIRECT
    if [[ ${EXP_DEBUG:-0} == 1 ]]; then
        export SCCACHE_LOG=debug SCCACHE_ERROR_LOG=$R/$mod.sccache.log
    fi
    sccache --stop-server >/dev/null 2>&1 || true
    sccache --start-server >/dev/null
    sccache --zero-stats >/dev/null
fi
t_ready=$EPOCHREALTIME

# R4*: simulate a low-level change in a widely included asyn header.  The clone
# is done here (ansible skips its clone when the folder exists) so it is timed
# separately as 'cascade_preclone'.
t_pre0=$EPOCHREALTIME
if [[ $mod == asyn && -n ${EXP_CASCADE:-} ]]; then
    ver=$(awk '/^version:/{print $2}' /epics/generic-source/ibek-support/asyn/asyn.install.yml)
    git clone -q --depth 1 -b "$ver" https://github.com/epics-modules/asyn /epics/support/asyn
    h=/epics/support/asyn/asyn/asynDriver/asynDriver.h
    grep -q '^#define asynDriverH' "$h"
    case $EXP_CASCADE in
      comment-top) sed -i '/^#define asynDriverH/a /* sccache experiment: cascade test comment */' "$h" ;;
      comment-end) echo '/* sccache experiment: cascade test comment */' >> "$h" ;;
      code)        sed -i '/^#define asynDriverH/a typedef int asynSccacheExperimentType;' "$h" ;;
    esac
    diff <(git -C /epics/support/asyn show HEAD:asyn/asynDriver/asynDriver.h) "$h" > "$R/cascade.diff" || true
fi
t_pre1=$EPOCHREALTIME

export ANSIBLE_CALLBACK_PLUGINS=/exp/callbacks ANSIBLE_CALLBACKS_ENABLED=exptimer
export EXP_TASKLOG=$R/$mod.tasks.jsonl
export PATH=/exp/bin:$PATH        # /exp/bin/make wraps top-level make in time -v
t_ans0=$EPOCHREALTIME
rc=0
ansible.sh "$mod" "$@" > "$R/$mod.ansible.log" 2>&1 || rc=$?
t_ans1=$EPOCHREALTIME
tail -n 40 "$R/$mod.ansible.log"
(( rc == 0 )) || { echo "ansible.sh $mod failed rc=$rc"; tail -n 200 "$R/$mod.ansible.log"; exit $rc; }

cache_bytes=0
if (( have_sccache )); then
    sccache --show-stats --stats-format=json > "$R/$mod.sccache.json"
    sccache --show-stats > "$R/$mod.sccache.txt"
    sccache --stop-server >/dev/null 2>&1 || true
    cache_bytes=$(du -sb "${SCCACHE_DIR:-/sccache}" | cut -f1)
fi
t_end=$EPOCHREALTIME
printf '{"module":"%s","start":%s,"ready":%s,"preclone0":%s,"preclone1":%s,"ansible0":%s,"ansible1":%s,"end":%s,"cache_bytes":%s}\n' \
    "$mod" "$t_start" "$t_ready" "$t_pre0" "$t_pre1" "$t_ans0" "$t_ans1" "$t_end" "$cache_bytes" >> "$R/steps.jsonl"
EOF

    # --- stage setup: variant-specific CONFIG_SITE additions ---------------
    cat > "$X/setup.sh" <<'EOF'
#!/bin/bash
set -euo pipefail
R=/exp-results; mkdir -p "$R"
echo "$EPOCHREALTIME" > "$R/stage_start"
env | grep -E '^EXP_' | sort > "$R/variant.env" || true
CS=/epics/epics-base/configure/os/CONFIG_SITE.Common.linux-x86_64
if command -v sccache >/dev/null; then L="/usr/local/bin/sccache "; else L=""; fi
if [[ ${EXP_SHIMS:-0} == 1 ]]; then
cat >> "$CS" <<EOS
# --- sccache experiment: timing shims (instrumented runs only) ---
CC  = /exp/shim/cc ${L}\$(GNU_BIN)/\$(CMPLR_PREFIX)gcc\$(CMPLR_SUFFIX)
CCC = /exp/shim/cc ${L}\$(GNU_BIN)/\$(CMPLR_PREFIX)g++\$(CMPLR_SUFFIX)
PERL = /exp/shim/tool perl perl -CSD
MSI3_15 = /exp/shim/tool msi "\$(EPICS_BASE_HOST_BIN)/msi\$(HOSTEXE)"
MSI = \$(MSI3_15)
EOS
fi
if [[ ${EXP_NODEPS:-0} == 1 ]]; then
cat >> "$CS" <<'EOS'
# --- sccache experiment: no header dependency (.d) generation ---
HDEPENDS_FILES =
EOS
fi
cp "$CS" "$R/CONFIG_SITE.Common.linux-x86_64"
if command -v sccache >/dev/null; then
    sccache --version > "$R/sccache.version"
    du -sb "${SCCACHE_DIR:-/sccache}" | cut -f1 > "$R/seed_cache_bytes"
fi
EOF

    # --- make wrapper: /usr/bin/time -v around each top-level make ----------
    cat > "$X/bin/make" <<'EOF'
#!/bin/bash
if [[ -n ${MAKELEVEL:-} || -z ${EXP_MODULE:-} ]]; then exec /usr/bin/make "$@"; fi
out=/exp-results/$EXP_MODULE.make.$(date +%s%N)
printf '%s\n%s\n' "$PWD" "$*" > "$out.args"
exec /exp/bin/gtime -v -o "$out.time" /usr/bin/make "$@"
EOF

    # --- compiler shim: classify + time every compiler-driver call ---------
    cat > "$X/shim/cc" <<'EOF'
#!/bin/bash
s=$EPOCHREALTIME
"$@"; rc=$?
e=$EPOCHREALTIME
k=link
for a in "$@"; do
    case $a in -MM|-M) k=dep; break ;; -c) k=compile ;; -E) [[ $k == link ]] && k=cpp ;; esac
done
printf '%s %s %s %s %s %s\n' "$k" "$s" "$e" "${EXP_MODULE:-?}" "$PWD" "${!#}" >> /exp-results/shim.log
exit $rc
EOF
    cat > "$X/shim/tool" <<'EOF'
#!/bin/bash
cat=$1; shift
s=$EPOCHREALTIME
"$@"; rc=$?
e=$EPOCHREALTIME
if [[ $cat == perl ]]; then
    for a in "$@"; do case $a in *.pl|*.pm) cat="perl:${a##*/}"; break ;; esac; done
fi
printf '%s %s %s %s %s -\n' "$cat" "$s" "$e" "${EXP_MODULE:-?}" "$PWD" >> /exp-results/shim.log
exit $rc
EOF
    chmod +x "$X"/*.sh "$X"/bin/* "$X"/shim/*

    # --- ansible callback: per-task wall times ------------------------------
    cat > "$X/callbacks/exptimer.py" <<'EOF'
# Records start/end of every ansible task as JSON lines in $EXP_TASKLOG.
import json, os, time
from ansible.plugins.callback import CallbackBase

class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'exptimer'
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super().__init__()
        self._f = open(os.environ.get('EXP_TASKLOG', '/dev/null'), 'a')
        self._cur = None

    def _emit(self, **kw):
        self._f.write(json.dumps(kw) + '\n'); self._f.flush()

    def _close(self):
        if self._cur:
            name, action, start = self._cur
            self._emit(ev='task', name=name, action=action, start=start, end=time.time())
            self._cur = None

    def v2_playbook_on_start(self, playbook):
        self._emit(ev='pb_start', t=time.time())

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._close()
        self._cur = (task.get_name(), task.action, time.time())

    v2_playbook_on_handler_task_start = lambda self, task: self.v2_playbook_on_task_start(task, False)

    def v2_playbook_on_stats(self, stats):
        self._close()
        self._emit(ev='pb_end', t=time.time())
EOF
}

# ---------------------------------------------------------------------------
proxy_args() {
    local a=()
    for v in HTTPS_PROXY https_proxy NO_PROXY no_proxy; do
        [[ -n ${!v:-} ]] && a+=(--build-arg "$v=${!v}")
    done
    printf '%s\n' "${a[@]}"
}

build_support_images() {
    local D=$WORK/images; rm -rf "$D"; mkdir -p "$D/net" "$D/sccache" "$D/tools"
    docker pull -q "$BASE_IMAGE" >/dev/null
    mapfile -t PA < <(proxy_args)

    # exp/net: sandbox plumbing only (proxy CA).  Identical for every run.
    if [[ -f $PROXY_CA_BUNDLE ]]; then
        cp "$PROXY_CA_BUNDLE" "$D/net/ca-bundle.crt"
        cat > "$D/net/Dockerfile" <<EOF
FROM $BASE_IMAGE
COPY ca-bundle.crt /etc/ssl/exp-ca-bundle.crt
RUN cp /etc/ssl/exp-ca-bundle.crt /usr/local/share/ca-certificates/exp-proxy.crt && update-ca-certificates >/dev/null 2>&1
ENV SSL_CERT_FILE=/etc/ssl/exp-ca-bundle.crt UV_NATIVE_TLS=true
EOF
    else
        echo "FROM $BASE_IMAGE" > "$D/net/Dockerfile"
    fi
    docker build -q --network host "${PA[@]}" -t exp/net "$D/net" >/dev/null

    # exp/tools: GNU time binary (copied into /exp/bin/gtime)
    printf 'FROM exp/net\nRUN apt-get update -qq && apt-get install -y -qq time >/dev/null\n' > "$D/tools/Dockerfile"
    docker build -q --network host "${PA[@]}" -t exp/tools "$D/tools" >/dev/null

    # exp/sccache-base: what epics-base-developer would ship.  Empty cache,
    # hooked into CC/CCC so every module built on top inherits it.
    cat > "$D/sccache/Dockerfile" <<EOF
FROM exp/net
ARG SCCACHE_VERSION=$SCCACHE_VERSION
ARG SCCACHE_SHA256=$SCCACHE_SHA256
RUN curl -fsSL -o /tmp/sccache.tgz \\
      https://github.com/mozilla/sccache/releases/download/v\${SCCACHE_VERSION}/sccache-v\${SCCACHE_VERSION}-x86_64-unknown-linux-musl.tar.gz \\
 && echo "\${SCCACHE_SHA256}  /tmp/sccache.tgz" | sha256sum -c - \\
 && tar -xzf /tmp/sccache.tgz -C /usr/local/bin --strip-components=1 sccache-v\${SCCACHE_VERSION}-x86_64-unknown-linux-musl/sccache \\
 && rm /tmp/sccache.tgz && sccache --version
ENV SCCACHE_DIR=/sccache
RUN mkdir -p /sccache && chmod 1777 /sccache && cat >> /epics/epics-base/configure/os/CONFIG_SITE.Common.linux-x86_64 <<'EOS'

# --- sccache: compiler cache for all modules built against this base ---------
# Disable with USE_SCCACHE=NO (e.g. make USE_SCCACHE=NO)
SCCACHE ?= /usr/local/bin/sccache
ifneq (\$(wildcard \$(SCCACHE)),)
ifneq (\$(USE_SCCACHE),NO)
CC  = \$(SCCACHE) \$(GNU_BIN)/\$(CMPLR_PREFIX)gcc\$(CMPLR_SUFFIX)
CCC = \$(SCCACHE) \$(GNU_BIN)/\$(CMPLR_PREFIX)g++\$(CMPLR_SUFFIX)
endif
endif
EOS
# Verify: build a throw-away EPICS example app and require sccache compile
# requests > 0, then leave the cache empty again.
RUN set -e; cd /tmp && mkdir verify && cd verify \\
 && makeBaseApp.pl -u exp -t example verify >/dev/null && make -s -j\$(nproc) >/dev/null 2>&1 \\
 && sccache --show-stats --stats-format=json > /tmp/v.json && sccache --show-stats \\
 && python3 -c "import json,sys; s=json.load(open('/tmp/v.json'))['stats']; n=s['compile_requests']; print('compile_requests',n); sys.exit(0 if n>0 else 1)" \\
 && sccache --stop-server && cd / && rm -rf /tmp/verify /tmp/v.json /sccache/* && du -sh /sccache
EOF
    docker build --network host --no-cache --progress=plain "${PA[@]}" -t exp/sccache-base "$D/sccache" \
        > "$RESULTS/sccache-base.build.log" 2>&1 || { tail -50 "$RESULTS/sccache-base.build.log"; exit 1; }
    grep -E 'compile_requests|Compile requests|Cache hits|Cache misses' "$RESULTS/sccache-base.build.log" | head -8
    cp "$D/sccache/Dockerfile" "$RESULTS/Dockerfile.sccache-base"
}

# ---------------------------------------------------------------------------
# exp/sccache-patched-base: exp/sccache-base with a patched sccache binary
# (only used by the R7* runs).  Built with the host's cargo if available,
# otherwise inside the official rust image.
build_patched_sccache() {
    local D=$WORK/sccache-patched
    if ! docker image inspect exp/sccache-patched-base >/dev/null 2>&1; then
        if [[ ! -x $D/sccache ]]; then
            rm -rf "$D"; mkdir -p "$D"
            git clone -q --depth 1 -b "v$SCCACHE_VERSION" https://github.com/mozilla/sccache "$D/src"
            git -C "$D/src" apply "$SCCACHE_PATCH"
            if command -v cargo >/dev/null; then
                (cd "$D/src" && cargo build --release --locked -q)
            else
                docker run --rm --network host -v "$D/src:/src" -w /src rust:1 cargo build --release --locked -q
            fi
            cp "$D/src/target/release/sccache" "$D/sccache"
        fi
        printf 'FROM exp/sccache-base\nCOPY sccache /usr/local/bin/sccache\nRUN sccache --version\n' > "$D/Dockerfile"
        docker build -q -t exp/sccache-patched-base "$D" >/dev/null
    fi
}

# ---------------------------------------------------------------------------
# Transform the IOC Dockerfile into the instrumented experiment Dockerfile.
gen_dockerfile() {
    local in=$WORK/ioc/Dockerfile out=$WORK/Dockerfile.exp
    python3 - "$in" "$out" <<'EOF'
import os, re, sys
src = open(sys.argv[1]).read().splitlines()
out = ['ARG SEED=exp/sccache-base']
for line in src:
    if re.match(r'\s*FROM\s+\$\{DEVELOPER\}\s+AS\s+developer', line):
        out += ['FROM ${SEED} AS seed', 'FROM exp/tools AS tools', line,
                'COPY --from=exp / /exp',
                'COPY --from=tools /usr/bin/time /exp/bin/gtime',
                '# seed the compiler cache from the previous release image',
                'COPY --from=seed /sccache /sccache',
                'ARG EXP_DIRECT EXP_DEBUG EXP_SHIMS EXP_CASCADE EXP_NODEPS',
                'RUN /exp/setup.sh']
        continue
    m = re.match(r'(\s*RUN\s+)ansible\.sh\s+(.*)$', line)
    if m:
        # SMOKE=1: keep only the first ansible step (harness self-test)
        if os.environ.get('SMOKE') and any('/exp/step.sh' in l for l in out):
            continue
        out.append(f'{m.group(1)}/exp/step.sh {m.group(2)}')
        continue
    out.append(line)
open(sys.argv[2], 'w').write('\n'.join(out) + '\n')
EOF
    cp "$out" "$RESULTS/Dockerfile.exp"
}

# ---------------------------------------------------------------------------
# run_variant NAME DEVELOPER_IMAGE SEED_IMAGE [EXP_VAR=value ...]
run_variant() {
    local name=$1 dev=$2 seed=$3; shift 3
    local out=$RESULTS/$name
    rm -rf "$out"; mkdir -p "$out"
    local ba=(--build-arg "DEVELOPER=$dev" --build-arg "SEED=$seed")
    for kv in "$@"; do ba+=(--build-arg "$kv"); done
    mapfile -t PA < <(proxy_args)
    printf 'developer=%s\nseed=%s\nvars=%s\n' "$dev" "$seed" "$*" > "$out/variant.txt"
    sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true   # cold page cache each run
    log "RUN $name  (developer=$dev seed=$seed $*)"
    local t0 t1 rc=0
    t0=$(date +%s.%N)
    docker build --network host --no-cache --progress=plain --target developer \
        --build-context exp="$WORK/exp-ctx" -f "$WORK/Dockerfile.exp" \
        "${PA[@]}" "${ba[@]}" -t "exp/run:$name" "$WORK/ioc" > "$out/build.log" 2>&1 || rc=$?
    t1=$(date +%s.%N)
    echo "$t0 $t1" > "$out/wall.txt"
    if (( rc != 0 )); then
        log "RUN $name FAILED (rc=$rc), see $out/build.log"; tail -40 "$out/build.log"
        return 1
    fi
    docker run --rm "exp/run:$name" tar -C /exp-results -cf - . | tar -xf - -C "$out"
    docker image inspect --format '{{.Size}}' "exp/run:$name" > "$out/image_bytes"
    docker run --rm "exp/run:$name" bash -c 'du -sb /sccache 2>/dev/null | cut -f1' > "$out/final_cache_bytes"
    gzip -f "$out"/*.sccache.log 2>/dev/null || true
    log "RUN $name done in $(python3 -c "print(round($t1-$t0,1))") s"
    if [[ $name == R1 || $name == R7rel ]]; then
        local tag=exp/release; [[ $name == R7rel ]] && tag=exp/release-R7rel
        docker tag "exp/run:$name" $tag      # the "released developer image"
        docker run --rm $tag du -sh /sccache | tee "$out/cache_du.txt"
    fi
    docker image rm -f "exp/run:$name" >/dev/null
    docker builder prune -af >/dev/null 2>&1 || true
}

run_by_name() {
    local net=exp/net sb=exp/sccache-base rel=exp/release
    case $1 in
        R0|R0b) run_variant "$1" $net $sb ;;                        # no sccache, cold
        R0shim) run_variant "$1" $net $sb EXP_SHIMS=1 ;;            # cold breakdown
        R1)     run_variant "$1" $sb  $sb ;;                        # empty cache (release build)
        R2?)    run_variant "$1" $sb  $rel ;;                       # warm, direct mode default (on)
        R2dbg)  run_variant "$1" $sb  $rel EXP_DEBUG=1 EXP_SHIMS=1 ;;  # miss analysis (not timed)
        R2shim) run_variant "$1" $sb  $rel EXP_SHIMS=1 ;;           # warm breakdown
        R5?)    run_variant "$1" $sb  $rel EXP_DIRECT=false ;;      # warm, direct mode off
        R4)     run_variant "$1" $sb  $rel EXP_CASCADE=comment-top ;;
        R4b)    run_variant "$1" $sb  $rel EXP_CASCADE=comment-end ;;
        R4c)    run_variant "$1" $sb  $rel EXP_CASCADE=code ;;
        R6)     run_variant "$1" $sb  $rel EXP_NODEPS=1 ;;          # TUNING: no .d generation
        R7rel)  build_patched_sccache; run_variant "$1" exp/sccache-patched-base exp/sccache-base ;;
        R7?)    run_variant "$1" exp/sccache-patched-base exp/release-R7rel ;;
        R7dbg)  run_variant "$1" exp/sccache-patched-base exp/release-R7rel EXP_DEBUG=1 ;;
        *) echo "unknown run $1"; return 1 ;;
    esac
}

# ---------------------------------------------------------------------------
main() {
    if [[ ${1:-} == analyse ]]; then
        python3 "$HERE/analyse.py" "$RESULTS"; exit 0
    fi
    command -v docker >/dev/null || { echo "docker required"; exit 1; }
    prepare_sources
    machine_info
    write_helpers
    build_support_images
    gen_dockerfile
    for r in $RUNS; do
        if [[ $r != R0* && $r != R1 && $r != R7* ]] && ! docker image inspect exp/release >/dev/null 2>&1; then
            echo "exp/release missing: run R1 first"; exit 1
        fi
        run_by_name "$r" || echo "$r FAILED" >> "$RESULTS/failures.txt"
        python3 "$HERE/analyse.py" "$RESULTS" >/dev/null 2>&1 || true
    done
    python3 "$HERE/analyse.py" "$RESULTS"
}

main "$@"
