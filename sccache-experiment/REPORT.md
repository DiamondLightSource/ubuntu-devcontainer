# How cheap is "re-run every ansible step with a warm sccache"?

Target: `ioc-adsimdetector` developer stage on `epics-base-developer:7.0.10ec2`:
iocStats, sequencer, sscan, calc, asyn, busy, autosave, pvlogging, ADCore,
ffmpegServer, ADSimDetector and the IOC, all built by the stock ibek-support ansible roles.

The script is [`run-experiment.sh`](run-experiment.sh), the analysis is
[`analyse.py`](analyse.py), and the full tables are in [`results/results.md`](results/results.md).
The raw per-run logs are under `results/<run>/`.

## Machine

| | |
|---|---|
| CPU | 4 vCPU Intel Xeon (cloud VM), `make -j4` |
| RAM | 15 GiB |
| Disk | virtio block device, ext4, `/var/lib/docker` on `/dev/vda` |
| Docker | 29.9.2, BuildKit, `docker build --no-cache --network host` |
| Compiler | gcc 13.3.0 (Ubuntu 24.04, from the base image) |
| sccache | 0.19.0 (official musl release, sha256-checked), local disk cache |
| Sources | ioc-adsimdetector @ 2d6a48e, ibek-support @ 6d4567a |

The host was restarted mid-experiment (kernel build v185 → v230, same specs).
The R0c–e and R2d–f runs were made after the restart and interleaved with each other,
so they compare cleanly with one another.

## Headline

| scenario | runs | wall (mean) | vs cold | `make` (build) total |
|---|---:|---:|---:|---:|
| **R0** cold, no sccache, FROM base | 5 | **334 s** (σ 14) | 100% | 38.6 s |
| R1 release build, empty cache | 1 | 332 s | 99% | 41 s |
| **R2** FROM base, cache seeded from the release image | 6 | **327 s** (σ 11) | **98%** | **12.7 s (33%)** |
| R7 as R2, with patched sccache (direct mode working) | 2 | 322 s (σ 21) | 96% | 10 s (26%) |
| **R8 FROM the released image, re-run every ansible step** (your plan) | 3 | **179 s** (σ 4) | **54%** | 11 s |

* sccache does its part. 205 of 208 compiles hit (98.6%), and `make` falls from 39 s to 13 s.
* But compilation was only about 12% of the cold build in the first place. The wall-clock
  saving of the cache alone (R2 vs R0, about 7 s) is smaller than the run-to-run noise (σ 11–14 s).
* Building FROM the released image (R8) is what roughly halves the time. It reuses the
  installed apt packages, the existing clones, and the cache already sitting in `/sccache`.
  What remains is almost all ansible overhead.

## (a) Warm full rebuild as a % of cold

* Same layering as cold (FROM base, cache seeded): **98% of cold wall**, 94% of the
  ansible-step time, 33% of the `make` time.
* As planned (FROM the released image + warm cache): **54% of cold wall (179 s vs 334 s)**.

## (b) What dominates the warm time

R8 (your plan), mean of 3 runs, 179 s:

| bucket | s | notes |
|---|---:|---|
| apt `package` tasks | ~46 | One `ansible.builtin.package` call **per package** (`loop:` in `support/tasks/system.yml`). Every package is already installed ("ok"), yet ADCore alone takes 25 s and ffmpegServer 6 s. "Install local system dependencies" is another ~10 s even though every item is skipped. |
| ~700 other small ansible tasks | ~70 | RELEASE/dbd/lib list edits, file links, copies. Mean ~0.1–0.2 s each; this is pure ansible per-task overhead. |
| gather_facts | 11 | Gathered once per `ansible.sh` call, ×12. |
| `make` (build) | 11–14 | Of which ~3 s compile (hits), ~4.7 s perl (`installEpics.pl` ×419, dbd tools), ~2 s `-MM` dependency files, ~1.3 s link, ~3 s make traversal. |
| `make clean` (×2 per module) | 9 | "Clean module for rebuild" plus the final clean. |
| ansible start/exit | 5 | |
| docker (layer export etc.) | 12–18 | 12 RUN layers. |
| clone | 1 | Skipped: the sources are already in the image. |

R2 (FROM base) is the same plus ~85 s more apt (real installs: ADCore ~85 s, ffmpegServer
~24 s), ~37 s of clones, and ~7 s to pull the 3 GB seed image just to get its 11 MB cache.

**Inside a warm `make`** (13.2 s in R2shim; shim timing, union of intervals):

| | cold (R0shim) | warm (R2shim) |
|---|---:|---:|
| compile | 29.6 s | 3.2 s |
| perl (installEpics, dbdExpand, dbdTo*H, ...) | 4.6 s | 4.7 s |
| dependency generation (`-MM`) | 1.8 s | 2.2 s |
| link | 1.2 s | 1.3 s |
| make traversal / idle | 3.4 s | 3.3 s |
| msi | 0 | 0 |
| **total make** | **39.0 s** | **13.2 s** |

**Method.** Each ansible step runs under a wrapper (`/exp/step.sh`). Inside it:

* An ansible callback plugin timestamps every task.
* Top-level `make` runs under `/usr/bin/time -v`.
* In the `*shim` runs, CONFIG_SITE overrides `CC`, `CCC`, `PERL` and `MSI` with shims that log
  start and end times. Calls are classed by flags: `-c` = compile, `-MM` = dependency file,
  otherwise link.
* "Traversal" is make wall time minus the union of all tool intervals.
* sccache stats are zeroed before each module step and dumped after it.

## (c) Is "skip unchanged modules" still worth it?

**Not to save compilation.** With a warm cache, the whole `make` for all 12 modules is
11–13 s, and a widely-included header change (R4c, asyn) costs only +20 s.

**Yes, if the goal is the remaining ~2½ minutes.** Almost none of that is make. A skip would
have to avoid running the ansible role at all for a module, which removes its apt, facts and
~60 tasks. Cheaper targets first, all in ibek-support and none needing skip logic:

1. **apt loop → one call.** Pass the whole list (`name: "{{ apt_developer | reject('match','^/') }}"`)
   instead of `loop:`. That is one dpkg query per module instead of one per package, so an estimated
   ~35 s → ~3 s. Also skip `Update apt cache` when every package is already installed.
2. **One ansible run instead of 12.** The squash-to-one-layer plan makes this natural: a single
   playbook over all modules removes 11× fact gathering (~10 s), process start-up (~4 s), and
   repeated per-module boilerplate tasks. Or set `gather_facts: false` / `gather_subset: min`.
3. **Drop `make clean` before build in a fresh container** (~4 s; nothing to clean in CI).
   In a devcontainer re-run it is what makes the rebuild "full", so keep it there or make it optional.
4. **Don't generate `.d` files in one-shot image builds** (`HDEPENDS_FILES =`, measured as R6): 196 fewer
   compiler calls, make 13 → 10 s. Do *not* use this for interactive developer builds, where the `.d`
   files are what drive incremental rebuilds.
5. **The IOC role builds with `make_options: ""` (-j1).** Here it costs only ~1.4 s, so it is not worth touching.

## (d) What defeats caching, and fixes

| what | effect | fix |
|---|---|---|
| **sccache 0.19.0 direct (preprocessor-cache) mode never engages for EPICS.** EPICS compiles from `O.<arch>` with `../foo.c`. In `process_preprocessor_line` (`src/compiler/c.rs`), sccache normalises the relative linemarker path *before* joining it to cwd, so `../foo.c` → `foo.c` and the stat fails. The log shows `Disabling preprocessor cache mode` for 205/205 compiles (R2dbg). Still present on sccache main. | Every hit costs a full `gcc -E`. Hits still happen, through the preprocessed-output hash. | [`sccache-relative-path-direct-mode.patch`](sccache-relative-path-direct-mode.patch) (join cwd before normalising; leave `<built-in>` alone). With it, 193/205 hits are direct-mode (R7dbg) and make drops from 12.7 to 10 s. Worth reporting upstream; I have not filed it. |
| **Generated timestamped headers:** `seq_release.h` (`seq_release.pl`) and `autosave_release.h` (`autosave_release.pl`) contain `"... compiled $now"` (localtime) | Sequencer `main.o` and `seq_main.o` and autosave `asVerify.o` miss on every build: the 3 misses in every warm run | Make the scripts honour `SOURCE_DATE_EPOCH`, or drop the timestamp. Costs ~1 s, so low priority. |
| **`SCCACHE_DIRECT` must match between release and developer builds.** With direct mode off, sccache runs `gcc -E -P` (no linemarkers), so the preprocessed hash differs. | R5: 0/208 hits against a cache built with direct mode on, and the cache doubles (9 → 18 MiB) | Set it once in the epics-base image and never override it. The same applies to the sccache version. |
| **Comment edits near the top of a header still miss.** The preprocessed output contains line markers, so inserting a line shifts everything after it. | R4: a comment at the top of `asynDriver.h` gives 110 misses, the same as a real code change (R4c); a comment at the end (R4b) gives 0 extra misses | None needed (this is correct behaviour). It means the "comment-only change" case is not free. |
| `-MM` dependency calls and links | 196 + 19 calls per build go through sccache uncached (`not_cached: -MM`) | Harmless (~2 s). See (c).4 to remove them in CI. |

Not found: no `__DATE__`/`__TIME__` in any compiled source, and no absolute-path problems. The paths are
identical (`/epics/support/...`) in the release and developer builds, so no `SCCACHE_BASEDIRS` is needed.

## Cache sizing and the developer-cache question

* The release build's cache is **11 MB** (`du -sh`; 14–18 MB with direct-mode manifests).
  It is built empty on top of epics-base, so each release image carries exactly its own objects and no history.
* **Developer containers:** if the devcontainer is the released image plus re-run ansible (R8), its
  `/sccache` starts as exactly the release's 11 MB. It only grows with the developer's own
  changes, in the container's writable layer, and is discarded at the next devcontainer rebuild or release.
  That is naturally bounded, so **I recommend no persistent or host cache for developers.** Set a small
  `SCCACHE_CACHE_SIZE` (e.g. `1G`) as a belt-and-braces bound, and make sure `/sccache` is writable
  by the remote user (the experiment used `chmod 1777`).
* A host bind-mount or volume at `/sccache` would *hide* the seeded cache, and sccache cannot layer
  a read-only local disk under a writable one (multi-level only chains to remote backends). If
  persistence is ever wanted, use a volume at a *different* path, and copy the image's `/sccache`
  into it on first start.
* **Seeding a FROM-base build** by `COPY --from` the 3 GB release image is wasteful: ~7 s to resolve
  and pull it for 11 MB. Publish the cache as its own tiny image or OCI artifact if you go that way.
  In your plan (R8) this cost disappears, because the cache is already in the base layer.
* Image size: R8 is 3077 MiB against 2971 MiB for the release image (+106 MiB of re-run layers). Squashing, as planned, removes most of that.

## Deviations from the original brief (agreed or forced)

* There is no ADSupport build and no upstream ADCore R3-14; this is the real ioc-adsimdetector stack. ADCore is at the SHA pinned in ibek-support.
  epics-base and pvxs are not rebuilt: they come from the base image, which is how the plan layers them.
* sccache is hooked through `CC`/`CCC` in `configure/os/CONFIG_SITE.Common.linux-x86_64` of epics-base. That file
  is included after gnuCommon's definitions. Links also pass through sccache (as non-compile calls), which is harmless.
* **R3 (local mirrors) was not run.** Clone time was measured instead (~37 s FROM base; ~1 s in R8, where clones are skipped).
  A mirror can save at most that.
* R5 is "direct mode off" vs the default "on". Because of the bug above, the default was effectively off
  too, so the patched-sccache series R7 was added to measure real direct mode.
* **Tuning, labelled as such:** R6 (`HDEPENDS_FILES =`) and R7 (patched sccache) are extra variants, not
  changes to the baseline. Nothing was tuned mid-series.
* Harness fixes mid-run: the R4 cascade sed used the wrong include-guard name, and the R7 seed tag
  was uppercase. Both failed outright (no partial data was used) and were rerun. R7rel was rerun in full.
* Sandbox-only: an extra layer adds the egress proxy's CA bundle so that uv, git and apt work. It is identical for all runs.
* Shim runs (`R0shim`, `R2shim`, `R2dbg`) add a few ms per call and are used only for breakdowns, not headline numbers.

## Run list

| run | what |
|---|---|
| R0, R0b–e | cold, no sccache, FROM base |
| R1 | sccache with an empty cache; this is the "release" build whose `/sccache` seeds the warm runs |
| R2a–f | warm (cache copied from R1), direct mode default |
| R2shim / R0shim / R2dbg | timing shims, and debug log for miss analysis |
| R4 / R4b / R4c | warm, plus a comment at the top / a comment at the end / a declaration in `asynDriver.h` |
| R5a–b | warm, `SCCACHE_DIRECT=false` |
| R6 | warm, no `.d` generation (tuning) |
| R7rel, R7a–b, R7dbg | patched sccache: release build, then warm runs |
| R8a–c | FROM the released image, every ansible step re-run (the devcontainer plan) |

Reproduce: `./run-experiment.sh` (all runs, ~2.5 h on this machine), or `RUNS="R0 R1 R2a R8a" ./run-experiment.sh`.
`./run-experiment.sh analyse` regenerates `results/results.md`.
