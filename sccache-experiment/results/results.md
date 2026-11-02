# sccache experiment results

## Machine

```
date: 2026-11-02T21:00:54Z
host_os: Ubuntu 24.04.5 LTS
kernel: 6.18.44-fc-v230
nproc: 4
cpu: Intel(R) Xeon(R) Processor
ram: 15 GiB
disk_rotational_flag: zram0    0 vda      1 vdb      1 vdc      1 vdd      1 vde      1 vdf      1 
docker_root_fs: /dev/vda       ext4  252G   15G   24G  39% /var/lib/docker
docker: 29.9.2
base_image: ghcr.io/epics-containers/epics-base-developer:7.0.10ec2
base_image_digest: ghcr.io/epics-containers/epics-base-developer@sha256:3fbb6842341881622c45515ce6f61ac1347982c5e13f8b7fe8c32c2bbfb39580
gcc_in_base: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
nproc_in_container: 4
ioc_repo: https://github.com/epics-containers/ioc-adsimdetector @ 2d6a48e716b43c7099735f7044bdba6f6c891fb1
ibek_support: 6d4567ab4ea9921563aad1c20ff758a514389762
sccache: 0.19.0 (sha256 aa73c7270c997894038c0d8f0d297865f57569e1687883322bc431713d4bb9dd)
```

## Run summary

Wall = whole `docker build --no-cache --target developer` (includes uv pip, COPYs, manifest, seed COPY). Steps = sum of the instrumented `ansible.sh` steps. Hit rate = hits / (hits + misses) over cacheable compiles.

| run | description | wall s | % of R0 | ansible steps s | make (build) s | compiles | hits | misses | hit rate | -MM calls (not cacheable) | link/other (not compile) | cache after |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | no sccache, cold (baseline) | 322 | 100% | 298 | 39 | – | – | – | – | – | – | – |
| R0b | no sccache, cold (repeat) | 341 | 106% | 317 | 39 | – | – | – | – | – | – | – |
| R0c | no sccache, cold (repeat, after host restart) | 355 | 110% | 301 | 39 | – | – | – | – | – | – | – |
| R0d | no sccache, cold (repeat, after host restart) | 325 | 101% | 292 | 38 | – | – | – | – | – | – | – |
| R0e | no sccache, cold (repeat, after host restart) | 327 | 102% | 297 | 38 | – | – | – | – | – | – | – |
| R1 | sccache, empty cache = release build | 332 | 103% | 296 | 41 | 425 | 0 | 208 | 0.0% | 196 | 19 | 9 MiB |
| R2a | sccache warm (seeded from R1), direct mode on (default) | 326 | 101% | 283 | 13 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R2b | repeat of R2a | 334 | 104% | 292 | 12 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R2c | repeat of R2a | 331 | 103% | 290 | 13 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R2d | repeat of R2a (after host restart, interleaved with R0c-e) | 342 | 106% | 278 | 12 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R2e | repeat of R2a (after host restart, interleaved with R0c-e) | 311 | 97% | 272 | 12 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R2f | repeat of R2a (after host restart, interleaved with R0c-e) | 319 | 99% | 279 | 12 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R5a | warm, direct (preprocessor-cache) mode OFF | 347 | 108% | 305 | 41 | 425 | 0 | 208 | 0.0% | 196 | 19 | 18 MiB |
| R5b | repeat of R5a | 340 | 106% | 298 | 41 | 425 | 0 | 208 | 0.0% | 196 | 19 | 18 MiB |
| R4 | warm + comment line inserted near top of asynDriver.h | 338 | 105% | 307 | 33 | 425 | 98 | 110 | 47.1% | 196 | 19 | 16 MiB |
| R4b | warm + comment line appended at end of asynDriver.h | 326 | 101% | 284 | 12 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R4c | warm + real declaration added to asynDriver.h | 328 | 102% | 287 | 33 | 425 | 98 | 110 | 47.1% | 196 | 19 | 16 MiB |
| R6 | TUNING: warm + no .d dependency generation (HDEPENDS_FILES=) | 328 | 102% | 287 | 10 | 229 | 205 | 3 | 98.6% | 0 | 19 | 9 MiB |
| R7rel | PATCHED sccache (direct mode fixed), empty cache = release build | 327 | 102% | 297 | 40 | 425 | 0 | 208 | 0.0% | 196 | 19 | 14 MiB |
| R7a | PATCHED sccache, warm (seeded from R7rel), direct mode on | 337 | 105% | 297 | 10 | 425 | 205 | 3 | 98.6% | 196 | 19 | 14 MiB |
| R7b | repeat of R7a | 307 | 96% | 268 | 10 | 425 | 205 | 3 | 98.6% | 196 | 19 | 14 MiB |
| R2shim | warm + timing shims (instrumented, not a headline number) | 331 | 103% | 290 | 13 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R0shim | cold no sccache + timing shims (instrumented) | 336 | 104% | 306 | 39 | – | – | – | – | – | – | – |
| R2dbg | warm + SCCACHE_LOG=debug + shims (miss analysis only) | 314 | 98% | 290 | 13 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R7dbg | PATCHED sccache warm + SCCACHE_LOG=debug (direct-mode hit check) | 308 | 96% | 270 | 12 | 425 | 205 | 3 | 98.6% | 196 | 19 | 14 MiB |
| R8a | devcontainer plan: FROM released image (exp/release), re-run all ansible steps | 174 | 54% | 162 | 11 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R8b | repeat of R8a | 180 | 56% | 162 | 11 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |
| R8c | repeat of R8a | 182 | 57% | 165 | 11 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |

### Variance

| group | n | mean wall s | stdev s | min | max |
|---|---:|---:|---:|---:|---:|
| R0 cold, all | 5 | 334 | 13.9 | 322 | 355 |
| R2 warm (direct on), all | 6 | 327 | 11.1 | 311 | 342 |
| R0 cold, before restart | 2 | 331 | 13.7 | 322 | 341 |
| R2 warm, before restart | 3 | 330 | 4.1 | 326 | 334 |
| R0 cold, after restart (interleaved) | 3 | 335 | 16.9 | 325 | 355 |
| R2 warm, after restart (interleaved) | 3 | 324 | 16.0 | 311 | 342 |
| R5 warm (direct off) | 2 | 343 | 5.2 | 340 | 347 |
| R7 warm (patched, direct on) | 2 | 322 | 21.1 | 307 | 337 |
| R8 FROM released image | 3 | 179 | 4.4 | 174 | 182 |

## Per-module step wall time (s)

Whole `RUN /exp/step.sh <module>` = ansible.sh incl. apt, clone, configure, make, make clean.

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 27 | 12 | 13 | 13 | 19 | 11 | 11 | 9 | 118 | 41 | 15 | 8 |
| R0b | 30 | 15 | 13 | 13 | 20 | 10 | 11 | 9 | 131 | 44 | 13 | 8 |
| R0c | 27 | 11 | 11 | 12 | 21 | 10 | 11 | 9 | 125 | 43 | 13 | 8 |
| R0d | 27 | 11 | 13 | 12 | 19 | 9 | 10 | 9 | 119 | 38 | 16 | 8 |
| R0e | 26 | 12 | 12 | 12 | 18 | 10 | 10 | 9 | 124 | 44 | 12 | 8 |
| R1 | 28 | 12 | 12 | 13 | 20 | 10 | 14 | 9 | 111 | 46 | 13 | 8 |
| R2a | 29 | 11 | 12 | 11 | 16 | 11 | 10 | 9 | 116 | 38 | 11 | 8 |
| R2b | 29 | 11 | 11 | 11 | 16 | 10 | 11 | 9 | 122 | 41 | 13 | 8 |
| R2c | 28 | 12 | 13 | 13 | 15 | 10 | 10 | 10 | 110 | 50 | 10 | 8 |
| R2d | 27 | 10 | 10 | 10 | 14 | 10 | 9 | 9 | 113 | 46 | 11 | 8 |
| R2e | 26 | 10 | 10 | 11 | 14 | 10 | 9 | 10 | 108 | 44 | 10 | 9 |
| R2f | 25 | 10 | 10 | 12 | 16 | 10 | 10 | 9 | 106 | 53 | 11 | 8 |
| R5a | 28 | 15 | 13 | 13 | 20 | 10 | 11 | 10 | 125 | 38 | 13 | 8 |
| R5b | 29 | 12 | 15 | 14 | 20 | 13 | 11 | 9 | 115 | 39 | 13 | 8 |
| R4 | 27 | 10 | 12 | 11 | 18 | 10 | 9 | 11 | 128 | 49 | 13 | 8 |
| R4b | 27 | 10 | 11 | 12 | 13 | 10 | 11 | 10 | 113 | 49 | 10 | 8 |
| R4c | 26 | 10 | 10 | 11 | 18 | 10 | 10 | 9 | 122 | 39 | 13 | 8 |
| R6 | 27 | 10 | 11 | 12 | 17 | 10 | 12 | 9 | 116 | 45 | 10 | 8 |
| R7rel | 27 | 13 | 12 | 12 | 19 | 10 | 12 | 10 | 114 | 46 | 13 | 8 |
| R7a | 27 | 11 | 13 | 11 | 16 | 11 | 9 | 9 | 125 | 47 | 10 | 8 |
| R7b | 26 | 10 | 11 | 10 | 16 | 10 | 11 | 10 | 106 | 40 | 10 | 8 |
| R2shim | 27 | 11 | 12 | 11 | 16 | 11 | 10 | 11 | 113 | 48 | 10 | 9 |
| R0shim | 30 | 14 | 12 | 13 | 20 | 10 | 12 | 10 | 121 | 44 | 12 | 8 |
| R2dbg | 29 | 11 | 11 | 11 | 16 | 10 | 10 | 9 | 118 | 47 | 10 | 8 |
| R7dbg | 31 | 11 | 11 | 10 | 15 | 9 | 10 | 10 | 102 | 43 | 10 | 8 |
| R8a | 16 | 8 | 8 | 8 | 12 | 8 | 7 | 7 | 57 | 15 | 8 | 7 |
| R8b | 15 | 8 | 9 | 8 | 12 | 8 | 8 | 7 | 56 | 15 | 8 | 7 |
| R8c | 16 | 8 | 8 | 8 | 12 | 8 | 8 | 8 | 58 | 16 | 8 | 7 |

## Per-module `make` (build only) wall time (s), from `/usr/bin/time -v`

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 0.8 | 2.7 | 2.4 | 2.7 | 6.3 | 0.5 | 1.5 | 0.3 | 16.1 | 1.1 | 3.0 | 1.5 |
| R0b | 0.8 | 2.7 | 2.4 | 2.5 | 6.4 | 0.5 | 1.6 | 0.3 | 16.1 | 1.1 | 3.0 | 1.5 |
| R0c | 0.7 | 2.6 | 2.3 | 2.6 | 6.3 | 0.5 | 1.5 | 0.3 | 16.5 | 1.2 | 3.0 | 1.5 |
| R0d | 0.7 | 2.6 | 2.5 | 2.4 | 6.1 | 0.5 | 1.5 | 0.3 | 15.6 | 1.1 | 3.0 | 1.4 |
| R0e | 0.7 | 2.6 | 2.4 | 2.6 | 6.2 | 0.5 | 1.5 | 0.3 | 16.0 | 1.1 | 3.0 | 1.5 |
| R1 | 0.9 | 2.7 | 2.5 | 2.6 | 6.7 | 0.6 | 1.6 | 0.4 | 16.9 | 1.3 | 3.1 | 1.5 |
| R2a | 0.7 | 1.1 | 0.7 | 0.9 | 2.2 | 0.5 | 0.7 | 0.3 | 3.2 | 0.6 | 0.4 | 1.4 |
| R2b | 0.7 | 0.9 | 0.7 | 0.9 | 2.2 | 0.5 | 0.7 | 0.3 | 3.0 | 0.6 | 0.5 | 1.3 |
| R2c | 0.7 | 1.0 | 0.7 | 0.8 | 2.2 | 0.5 | 0.6 | 0.3 | 3.2 | 0.6 | 0.5 | 1.4 |
| R2d | 0.6 | 0.9 | 0.6 | 0.8 | 2.2 | 0.5 | 0.6 | 0.3 | 3.0 | 0.6 | 0.4 | 1.5 |
| R2e | 0.6 | 0.9 | 0.7 | 0.9 | 2.2 | 0.4 | 0.6 | 0.3 | 3.0 | 0.6 | 0.4 | 1.3 |
| R2f | 0.6 | 0.9 | 0.7 | 0.9 | 2.3 | 0.4 | 0.6 | 0.3 | 3.0 | 0.6 | 0.4 | 1.3 |
| R5a | 0.8 | 2.8 | 2.5 | 2.8 | 6.7 | 0.6 | 1.7 | 0.4 | 17.1 | 1.3 | 3.2 | 1.6 |
| R5b | 0.9 | 2.8 | 2.4 | 2.6 | 6.7 | 0.6 | 1.7 | 0.3 | 17.1 | 1.3 | 3.1 | 1.6 |
| R4 | 0.7 | 0.9 | 0.7 | 0.9 | 6.4 | 0.6 | 0.6 | 0.3 | 16.5 | 1.1 | 3.1 | 1.3 |
| R4b | 0.7 | 0.9 | 0.7 | 0.9 | 2.2 | 0.5 | 0.6 | 0.3 | 3.1 | 0.6 | 0.4 | 1.4 |
| R4c | 0.7 | 1.0 | 0.6 | 0.9 | 6.5 | 0.6 | 0.6 | 0.3 | 16.5 | 1.0 | 3.1 | 1.3 |
| R6 | 0.5 | 0.8 | 0.7 | 0.8 | 1.8 | 0.5 | 0.5 | 0.2 | 2.4 | 0.5 | 0.3 | 1.3 |
| R7rel | 0.9 | 2.9 | 2.4 | 2.6 | 6.8 | 0.6 | 1.6 | 0.3 | 16.0 | 1.2 | 3.2 | 1.5 |
| R7a | 0.6 | 0.9 | 0.7 | 0.8 | 1.8 | 0.4 | 0.6 | 0.3 | 2.2 | 0.5 | 0.4 | 1.3 |
| R7b | 0.6 | 0.9 | 0.6 | 0.8 | 1.8 | 0.5 | 0.6 | 0.3 | 2.3 | 0.4 | 0.4 | 1.3 |
| R2shim | 0.7 | 1.1 | 0.7 | 0.9 | 2.4 | 0.5 | 0.7 | 0.3 | 3.4 | 0.6 | 0.5 | 1.4 |
| R0shim | 0.8 | 2.8 | 2.4 | 2.5 | 6.5 | 0.6 | 1.7 | 0.3 | 16.0 | 1.1 | 3.0 | 1.5 |
| R2dbg | 0.8 | 1.0 | 0.7 | 1.0 | 2.4 | 0.5 | 0.7 | 0.3 | 3.5 | 0.7 | 0.5 | 1.4 |
| R7dbg | 0.6 | 1.0 | 0.7 | 0.8 | 2.1 | 0.4 | 0.6 | 0.3 | 3.3 | 0.5 | 0.4 | 1.4 |
| R8a | 0.7 | 0.9 | 0.6 | 0.8 | 2.0 | 0.5 | 0.6 | 0.3 | 2.9 | 0.6 | 0.4 | 1.3 |
| R8b | 0.6 | 0.9 | 0.6 | 0.8 | 2.0 | 0.5 | 0.6 | 0.3 | 2.7 | 0.6 | 0.4 | 1.4 |
| R8c | 0.7 | 0.9 | 0.6 | 0.7 | 2.0 | 0.5 | 0.6 | 0.3 | 2.8 | 0.6 | 0.4 | 1.3 |

## Per-module sccache hit rate (hits/(hits+misses)) and misses

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | – | – | – | – | – | – | – | – | – | – | – | – |
| R0b | – | – | – | – | – | – | – | – | – | – | – | – |
| R0c | – | – | – | – | – | – | – | – | – | – | – | – |
| R0d | – | – | – | – | – | – | – | – | – | – | – | – |
| R0e | – | – | – | – | – | – | – | – | – | – | – | – |
| R1 | 0% (17m) | 0% (23m) | 0% (7m) | 0% (18m) | 0% (67m) | 0% (4m) | 0% (9m) | 0% (2m) | 0% (50m) | 0% (8m) | 0% (1m) | 0% (2m) |
| R2a | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R2b | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R2c | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R2d | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R2e | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R2f | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R5a | 0% (17m) | 0% (23m) | 0% (7m) | 0% (18m) | 0% (67m) | 0% (4m) | 0% (9m) | 0% (2m) | 0% (50m) | 0% (8m) | 0% (1m) | 0% (2m) |
| R5b | 0% (17m) | 0% (23m) | 0% (7m) | 0% (18m) | 0% (67m) | 0% (4m) | 0% (9m) | 0% (2m) | 0% (50m) | 0% (8m) | 0% (1m) | 0% (2m) |
| R4 | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 10% (60m) | 75% (1m) | 89% (1m) | 100% (0m) | 16% (42m) | 62% (3m) | 0% (1m) | 100% (0m) |
| R4b | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R4c | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 10% (60m) | 75% (1m) | 89% (1m) | 100% (0m) | 16% (42m) | 62% (3m) | 0% (1m) | 100% (0m) |
| R6 | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R7rel | 0% (17m) | 0% (23m) | 0% (7m) | 0% (18m) | 0% (67m) | 0% (4m) | 0% (9m) | 0% (2m) | 0% (50m) | 0% (8m) | 0% (1m) | 0% (2m) |
| R7a | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R7b | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R2shim | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R0shim | – | – | – | – | – | – | – | – | – | – | – | – |
| R2dbg | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R7dbg | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R8a | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R8b | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |
| R8c | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |

## Where the time goes, by ansible task category (s, summed over modules)

Categories come from the ansible callback timer: `apt` = system/apt/get_url tasks, `clone` = git tasks, `facts` = fact gathering, `ansible_startup` = process start to first task, `ansible_other` = all other tasks (RELEASE fixups, patching, ibek, runtime lists), `make` / `make_clean` = the build and clean tasks, `sccache_srv` = start/zero/stats/stop of the sccache server in the wrapper (experiment overhead). `docker other` = wall minus ansible steps (uv pip install, COPY layers incl. seed cache COPY, manifest, export).

| run | apt | clone | facts | ansible_startup | ansible_other | make | make_clean | ansible_exit | sccache_srv | cascade_preclone | docker other | wall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 122 | 37 | 10 | 4 | 73 | 41 | 9 | 1 | 0 | 0 | 24 | 322 |
| R0b | 142 | 37 | 11 | 4 | 72 | 41 | 9 | 1 | 0 | 0 | 24 | 341 |
| R0c | 133 | 36 | 9 | 4 | 68 | 41 | 9 | 1 | 0 | 0 | 54 | 355 |
| R0d | 125 | 36 | 9 | 4 | 69 | 40 | 9 | 1 | 0 | 0 | 32 | 325 |
| R0e | 134 | 31 | 9 | 4 | 69 | 41 | 9 | 1 | 0 | 0 | 30 | 327 |
| R1 | 122 | 37 | 10 | 4 | 70 | 43 | 9 | 1 | 0 | 0 | 35 | 332 |
| R2a | 132 | 38 | 11 | 4 | 73 | 15 | 10 | 1 | 0 | 0 | 43 | 326 |
| R2b | 145 | 37 | 10 | 4 | 72 | 15 | 9 | 1 | 0 | 0 | 42 | 334 |
| R2c | 137 | 41 | 10 | 4 | 73 | 15 | 9 | 1 | 0 | 0 | 42 | 331 |
| R2d | 136 | 36 | 9 | 4 | 68 | 14 | 9 | 1 | 0 | 0 | 64 | 342 |
| R2e | 133 | 31 | 10 | 4 | 69 | 14 | 9 | 1 | 0 | 0 | 39 | 311 |
| R2f | 124 | 46 | 10 | 4 | 70 | 14 | 9 | 1 | 0 | 0 | 40 | 319 |
| R5a | 127 | 36 | 12 | 4 | 72 | 44 | 9 | 1 | 0 | 0 | 42 | 347 |
| R5b | 121 | 37 | 10 | 4 | 73 | 43 | 9 | 1 | 0 | 0 | 42 | 340 |
| R4 | 140 | 36 | 9 | 4 | 70 | 35 | 9 | 1 | 0 | 2 | 31 | 338 |
| R4b | 136 | 38 | 10 | 4 | 71 | 15 | 9 | 1 | 0 | 1 | 41 | 326 |
| R4c | 125 | 31 | 9 | 4 | 71 | 35 | 9 | 1 | 0 | 1 | 41 | 328 |
| R6 | 136 | 44 | 9 | 4 | 71 | 12 | 9 | 1 | 0 | 0 | 40 | 328 |
| R7rel | 124 | 36 | 10 | 4 | 70 | 42 | 9 | 1 | 0 | 0 | 31 | 327 |
| R7a | 133 | 58 | 9 | 4 | 70 | 13 | 9 | 1 | 0 | 0 | 40 | 337 |
| R7b | 122 | 43 | 9 | 4 | 68 | 13 | 9 | 1 | 0 | 0 | 39 | 307 |
| R2shim | 139 | 36 | 12 | 4 | 73 | 15 | 9 | 1 | 0 | 0 | 42 | 331 |
| R0shim | 134 | 35 | 10 | 4 | 72 | 41 | 9 | 1 | 0 | 0 | 30 | 336 |
| R2dbg | 145 | 32 | 10 | 4 | 73 | 16 | 9 | 1 | 0 | 0 | 24 | 314 |
| R7dbg | 126 | 35 | 9 | 6 | 69 | 14 | 9 | 1 | 1 | 0 | 38 | 308 |
| R8a | 54 | 1 | 9 | 4 | 69 | 14 | 9 | 1 | 0 | 0 | 12 | 174 |
| R8b | 53 | 1 | 11 | 4 | 69 | 14 | 9 | 1 | 0 | 0 | 18 | 180 |
| R8c | 55 | 1 | 11 | 4 | 71 | 14 | 9 | 1 | 0 | 0 | 18 | 182 |

### Docker build steps for R0 (s)

| step | s |
|---|---:|
| [developer] `RUN uv pip install --upgrade -r requirements.txt` | 0.9 |
| [developer] `RUN /exp/step.sh iocStats` | 27.2 |
| [developer] `RUN /exp/step.sh sequencer` | 12.4 |
| [developer] `RUN /exp/step.sh sscan` | 13.3 |
| [developer] `RUN /exp/step.sh calc` | 13.5 |
| [developer] `RUN /exp/step.sh asyn` | 19.6 |
| [developer] `RUN /exp/step.sh busy` | 10.8 |
| [developer] `RUN /exp/step.sh autosave` | 10.7 |
| [developer] `RUN /exp/step.sh pvlogging` | 9.4 |
| [developer] `RUN /exp/step.sh ADCore` | 118.3 |
| [developer] `RUN /exp/step.sh ffmpegServer` | 40.8 |
| [developer] `RUN /exp/step.sh ADSimDetector` | 14.9 |
| [developer] `RUN /exp/step.sh ioc` | 8.4 |

### Docker build steps for R1 (s)

| step | s |
|---|---:|
| [tools] `FROM docker.io/exp/tools:latest@sha256:84b9adf3759544a2d38f970cc1c799d9e11fa058db9788a6886` | 7.3 |
| [seed] `FROM docker.io/exp/sccache-base:latest@sha256:dd28d794e542991ae1d86de9630e014500bcf9ca00ed` | 0.5 |
| [developer] `COPY --from=exp / /exp` | 1.1 |
| [developer] `RUN uv pip install --upgrade -r requirements.txt` | 0.7 |
| [developer] `RUN /exp/step.sh iocStats` | 28.4 |
| [developer] `RUN /exp/step.sh sequencer` | 12.2 |
| [developer] `RUN /exp/step.sh sscan` | 12.6 |
| [developer] `RUN /exp/step.sh calc` | 12.7 |
| [developer] `RUN /exp/step.sh asyn` | 19.8 |
| [developer] `RUN /exp/step.sh busy` | 10.3 |
| [developer] `RUN /exp/step.sh autosave` | 13.6 |
| [developer] `RUN /exp/step.sh pvlogging` | 9.5 |
| [developer] `RUN /exp/step.sh ADCore` | 111.7 |
| [developer] `RUN /exp/step.sh ffmpegServer` | 46.2 |
| [developer] `RUN /exp/step.sh ADSimDetector` | 12.7 |
| [developer] `RUN /exp/step.sh ioc` | 8.2 |

### Docker build steps for R2a (s)

| step | s |
|---|---:|
| [developer] `FROM docker.io/exp/sccache-base:latest@sha256:dd28d794e542991ae1d86de9630e014500bcf9ca00ed` | 0.7 |
| [tools] `FROM docker.io/exp/tools:latest@sha256:84b9adf3759544a2d38f970cc1c799d9e11fa058db9788a6886` | 7.5 |
| [seed] `FROM docker.io/exp/release:latest@sha256:01c7097fb05a9ce7e8b085f169af19a45acf7ebf133b27dc7` | 7.4 |
| [developer] `COPY --from=exp / /exp` | 1.1 |
| [developer] `COPY --from=seed /sccache /sccache` | 1.0 |
| [developer] `RUN uv pip install --upgrade -r requirements.txt` | 0.8 |
| [developer] `RUN /exp/step.sh iocStats` | 29.2 |
| [developer] `RUN /exp/step.sh sequencer` | 10.9 |
| [developer] `RUN /exp/step.sh sscan` | 11.9 |
| [developer] `RUN /exp/step.sh calc` | 11.4 |
| [developer] `RUN /exp/step.sh asyn` | 16.4 |
| [developer] `RUN /exp/step.sh busy` | 11.1 |
| [developer] `RUN /exp/step.sh autosave` | 10.0 |
| [developer] `RUN /exp/step.sh pvlogging` | 9.6 |
| [developer] `RUN /exp/step.sh ADCore` | 116.1 |
| [developer] `RUN /exp/step.sh ffmpegServer` | 38.4 |
| [developer] `RUN /exp/step.sh ADSimDetector` | 11.4 |
| [developer] `RUN /exp/step.sh ioc` | 8.0 |

## Inside make: tool breakdown for R0shim

Each compiler-driver call (CC/CCC), perl call ($(PERL)) and msi call is wrapped by a bash shim that logs start/end ($EPOCHREALTIME). `sum` = summed durations (CPU-ish, overlapping under -j), `wall covered` = union of intervals, i.e. time during which at least one such process was running. Total make (build) wall for this run: 39 s. Shim overhead is a few ms per call, so these runs are not headline numbers.

| category | calls | sum s | wall covered s |
|---|---:|---:|---:|
| compile | 208 | 74.4 | 29.6 |
| perl:installEpics.pl | 419 | 5.8 | 3.2 |
| dep | 196 | 4.2 | 1.8 |
| link | 19 | 1.2 | 1.2 |
| perl:dbdExpand.pl | 6 | 0.9 | 0.9 |
| perl:dbdToRecordtypeH.pl | 18 | 0.5 | 0.3 |
| perl:convertRelease.pl | 11 | 0.2 | 0.2 |
| perl:registerRecordDeviceDriver.pl | 2 | 0.2 | 0.2 |
| perl:mkmf.pl | 14 | 0.2 | 0.1 |
| perl | 77 | 0.2 | 0.1 |
| perl:dbdToMenuH.pl | 2 | 0.0 | 0.0 |
| cpp | 2 | 0.0 | 0.0 |
| perl:makeIncludeDbd.pl | 1 | 0.0 | 0.0 |
| perl:bnf2txt.pl | 1 | 0.0 | 0.0 |
| perl:seq_release.pl | 1 | 0.0 | 0.0 |
| perl:autosave_release.pl | 1 | 0.0 | 0.0 |

### R0shim: per-module wall covered (s) by category

| module | compile | dep | link | perl(any) | msi | make wall |
|---|---:|---:|---:|---:|---:|---:|
| iocStats | 0.3 | 0.2 | 0.0 | 0.4 | 0.0 | 0.8 |
| sequencer | 2.1 | 0.1 | 0.1 | 0.3 | 0.0 | 2.8 |
| sscan | 1.8 | 0.0 | 0.1 | 0.5 | 0.0 | 2.4 |
| calc | 1.8 | 0.1 | 0.0 | 0.4 | 0.0 | 2.5 |
| asyn | 4.8 | 0.4 | 0.1 | 0.7 | 0.0 | 6.5 |
| busy | 0.1 | 0.0 | 0.0 | 0.1 | 0.0 | 0.6 |
| autosave | 1.1 | 0.1 | 0.1 | 0.1 | 0.0 | 1.7 |
| pvlogging | 0.1 | 0.0 | 0.0 | 0.1 | 0.0 | 0.3 |
| ADCore | 13.9 | 0.6 | 0.3 | 1.1 | 0.0 | 16.0 |
| ffmpegServer | 0.7 | 0.1 | 0.1 | 0.1 | 0.0 | 1.1 |
| ADSimDetector | 2.6 | 0.0 | 0.1 | 0.1 | 0.0 | 3.0 |
| ioc | 0.2 | 0.0 | 0.2 | 0.7 | 0.0 | 1.5 |

## Inside make: tool breakdown for R2shim

Each compiler-driver call (CC/CCC), perl call ($(PERL)) and msi call is wrapped by a bash shim that logs start/end ($EPOCHREALTIME). `sum` = summed durations (CPU-ish, overlapping under -j), `wall covered` = union of intervals, i.e. time during which at least one such process was running. Total make (build) wall for this run: 13 s. Shim overhead is a few ms per call, so these runs are not headline numbers.

| category | calls | sum s | wall covered s |
|---|---:|---:|---:|
| compile | 208 | 8.9 | 3.2 |
| perl:installEpics.pl | 419 | 5.9 | 3.2 |
| dep | 196 | 5.5 | 2.2 |
| link | 19 | 1.4 | 1.3 |
| perl:dbdExpand.pl | 6 | 0.9 | 0.9 |
| perl:dbdToRecordtypeH.pl | 18 | 0.5 | 0.4 |
| perl:convertRelease.pl | 11 | 0.2 | 0.2 |
| perl:registerRecordDeviceDriver.pl | 2 | 0.2 | 0.2 |
| perl:mkmf.pl | 14 | 0.2 | 0.1 |
| perl | 77 | 0.2 | 0.2 |
| cpp | 2 | 0.1 | 0.1 |
| perl:dbdToMenuH.pl | 2 | 0.0 | 0.0 |
| perl:makeIncludeDbd.pl | 1 | 0.0 | 0.0 |
| perl:bnf2txt.pl | 1 | 0.0 | 0.0 |
| perl:seq_release.pl | 1 | 0.0 | 0.0 |
| perl:autosave_release.pl | 1 | 0.0 | 0.0 |

### R2shim: per-module wall covered (s) by category

| module | compile | dep | link | perl(any) | msi | make wall |
|---|---:|---:|---:|---:|---:|---:|
| iocStats | 0.2 | 0.2 | 0.0 | 0.3 | 0.0 | 0.7 |
| sequencer | 0.3 | 0.2 | 0.1 | 0.3 | 0.0 | 1.1 |
| sscan | 0.1 | 0.1 | 0.1 | 0.4 | 0.0 | 0.7 |
| calc | 0.2 | 0.1 | 0.1 | 0.4 | 0.0 | 0.9 |
| asyn | 0.6 | 0.5 | 0.1 | 0.8 | 0.0 | 2.4 |
| busy | 0.1 | 0.0 | 0.1 | 0.1 | 0.0 | 0.5 |
| autosave | 0.2 | 0.1 | 0.1 | 0.1 | 0.0 | 0.7 |
| pvlogging | 0.0 | 0.1 | 0.0 | 0.1 | 0.0 | 0.3 |
| ADCore | 1.2 | 0.7 | 0.4 | 1.2 | 0.0 | 3.4 |
| ffmpegServer | 0.2 | 0.2 | 0.1 | 0.1 | 0.0 | 0.6 |
| ADSimDetector | 0.1 | 0.1 | 0.1 | 0.1 | 0.0 | 0.5 |
| ioc | 0.1 | 0.0 | 0.2 | 0.8 | 0.0 | 1.4 |

## Inside make: tool breakdown for R2dbg

Each compiler-driver call (CC/CCC), perl call ($(PERL)) and msi call is wrapped by a bash shim that logs start/end ($EPOCHREALTIME). `sum` = summed durations (CPU-ish, overlapping under -j), `wall covered` = union of intervals, i.e. time during which at least one such process was running. Total make (build) wall for this run: 13 s. Shim overhead is a few ms per call, so these runs are not headline numbers.

| category | calls | sum s | wall covered s |
|---|---:|---:|---:|
| compile | 208 | 9.0 | 3.2 |
| perl:installEpics.pl | 419 | 6.1 | 3.3 |
| dep | 196 | 5.6 | 2.3 |
| link | 19 | 1.4 | 1.3 |
| perl:dbdExpand.pl | 6 | 0.9 | 0.9 |
| perl:dbdToRecordtypeH.pl | 18 | 0.5 | 0.3 |
| perl:convertRelease.pl | 11 | 0.2 | 0.2 |
| perl:registerRecordDeviceDriver.pl | 2 | 0.2 | 0.2 |
| perl:mkmf.pl | 14 | 0.2 | 0.1 |
| perl | 77 | 0.2 | 0.2 |
| cpp | 2 | 0.1 | 0.1 |
| perl:dbdToMenuH.pl | 2 | 0.1 | 0.1 |
| perl:makeIncludeDbd.pl | 1 | 0.0 | 0.0 |
| perl:bnf2txt.pl | 1 | 0.0 | 0.0 |
| perl:autosave_release.pl | 1 | 0.0 | 0.0 |
| perl:seq_release.pl | 1 | 0.0 | 0.0 |

### R2dbg: per-module wall covered (s) by category

| module | compile | dep | link | perl(any) | msi | make wall |
|---|---:|---:|---:|---:|---:|---:|
| iocStats | 0.2 | 0.3 | 0.1 | 0.3 | 0.0 | 0.8 |
| sequencer | 0.3 | 0.1 | 0.1 | 0.3 | 0.0 | 1.0 |
| sscan | 0.1 | 0.1 | 0.1 | 0.5 | 0.0 | 0.7 |
| calc | 0.2 | 0.2 | 0.1 | 0.5 | 0.0 | 1.0 |
| asyn | 0.6 | 0.5 | 0.1 | 0.8 | 0.0 | 2.4 |
| busy | 0.0 | 0.0 | 0.0 | 0.1 | 0.0 | 0.5 |
| autosave | 0.2 | 0.1 | 0.1 | 0.1 | 0.0 | 0.7 |
| pvlogging | 0.0 | 0.1 | 0.0 | 0.1 | 0.0 | 0.3 |
| ADCore | 1.2 | 0.7 | 0.4 | 1.2 | 0.0 | 3.5 |
| ffmpegServer | 0.2 | 0.1 | 0.1 | 0.1 | 0.0 | 0.7 |
| ADSimDetector | 0.1 | 0.1 | 0.1 | 0.1 | 0.0 | 0.5 |
| ioc | 0.0 | 0.0 | 0.2 | 0.8 | 0.0 | 1.4 |

## Warm-cache misses (R2dbg, SCCACHE_LOG=debug)

| module | hits | misses | preprocessor(direct)-cache hits | 'too new' headers | direct mode disabled |
|---|---:|---:|---:|---:|---:|
| iocStats | 17 | 0 | 0 | 0 | 17 |
| sequencer | 21 | 2 | 0 | 0 | 23 |
| sscan | 7 | 0 | 0 | 0 | 7 |
| calc | 18 | 0 | 0 | 0 | 18 |
| asyn | 67 | 0 | 0 | 0 | 67 |
| busy | 4 | 0 | 0 | 0 | 4 |
| autosave | 8 | 1 | 0 | 0 | 9 |
| pvlogging | 2 | 0 | 1 | 0 | 1 |
| ADCore | 50 | 0 | 0 | 0 | 50 |
| ffmpegServer | 8 | 0 | 0 | 0 | 8 |
| ADSimDetector | 1 | 0 | 0 | 0 | 1 |
| ioc | 2 | 0 | 1 | 0 | 1 |

| module | object | source (cwd) |
|---|---|---|
| autosave | asVerify.o | ../asVerify.c (/epics/support/autosave/asApp/src/O.linux-x86_64) |
| sequencer | main.o | ../main.c (/epics/support/sequencer/src/snc/O.linux-x86_64) |
| sequencer | seq_main.o | ../seq_main.c (/epics/support/sequencer/src/seq/O.linux-x86_64) |

## Warm-cache misses (R7dbg, SCCACHE_LOG=debug)

| module | hits | misses | preprocessor(direct)-cache hits | 'too new' headers | direct mode disabled |
|---|---:|---:|---:|---:|---:|
| iocStats | 17 | 0 | 17 | 0 | 0 |
| sequencer | 21 | 2 | 11 | 0 | 0 |
| sscan | 7 | 0 | 6 | 0 | 0 |
| calc | 18 | 0 | 17 | 0 | 0 |
| asyn | 67 | 0 | 67 | 0 | 0 |
| busy | 4 | 0 | 4 | 0 | 0 |
| autosave | 8 | 1 | 8 | 0 | 0 |
| pvlogging | 2 | 0 | 2 | 0 | 0 |
| ADCore | 50 | 0 | 50 | 0 | 0 |
| ffmpegServer | 8 | 0 | 8 | 0 | 0 |
| ADSimDetector | 1 | 0 | 1 | 0 | 0 |
| ioc | 2 | 0 | 2 | 0 | 0 |

| module | object | source (cwd) |
|---|---|---|
| autosave | asVerify.o | ? |
| sequencer | seq_main.o | ? |
| sequencer | main.o | ? |

## Non-cacheable calls by reason (sccache `not_cached`)

| run | -E | -MM |
|---|---:|---:|
| R0 | 0 | 0 |
| R0b | 0 | 0 |
| R0c | 0 | 0 |
| R0d | 0 | 0 |
| R0e | 0 | 0 |
| R1 | 2 | 196 |
| R2a | 2 | 196 |
| R2b | 2 | 196 |
| R2c | 2 | 196 |
| R2d | 2 | 196 |
| R2e | 2 | 196 |
| R2f | 2 | 196 |
| R5a | 2 | 196 |
| R5b | 2 | 196 |
| R4 | 2 | 196 |
| R4b | 2 | 196 |
| R4c | 2 | 196 |
| R6 | 2 | 0 |
| R7rel | 2 | 196 |
| R7a | 2 | 196 |
| R7b | 2 | 196 |
| R2shim | 2 | 196 |
| R0shim | 0 | 0 |
| R2dbg | 2 | 196 |
| R7dbg | 2 | 196 |
| R8a | 2 | 196 |
| R8b | 2 | 196 |
| R8c | 2 | 196 |

## Image and cache sizes

| run | image bytes (docker inspect) | seed cache | cache after |
|---|---:|---:|---:|
| R0 | 2920 MiB | – | – |
| R0b | 2920 MiB | – | – |
| R0c | 2920 MiB | – | – |
| R0d | 2920 MiB | – | – |
| R0e | 2920 MiB | – | – |
| R1 | 2971 MiB | – | 9 MiB |
| R2a | 2990 MiB | 9 MiB | 9 MiB |
| R2b | 2990 MiB | 9 MiB | 9 MiB |
| R2c | 2990 MiB | 9 MiB | 9 MiB |
| R2d | 2990 MiB | 9 MiB | 9 MiB |
| R2e | 2990 MiB | 9 MiB | 9 MiB |
| R2f | 2990 MiB | 9 MiB | 9 MiB |
| R5a | 2990 MiB | 9 MiB | 18 MiB |
| R5b | 2990 MiB | 9 MiB | 18 MiB |
| R4 | 2990 MiB | 9 MiB | 16 MiB |
| R4b | 2990 MiB | 9 MiB | 9 MiB |
| R4c | 2990 MiB | 9 MiB | 16 MiB |
| R6 | 2990 MiB | 9 MiB | 9 MiB |
| R7rel | 3010 MiB | – | 14 MiB |
| R7a | 3037 MiB | 14 MiB | 14 MiB |
| R7b | 3037 MiB | 14 MiB | 14 MiB |
| R2shim | 2991 MiB | 9 MiB | 9 MiB |
| R0shim | 2921 MiB | – | – |
| R2dbg | 2992 MiB | 9 MiB | 9 MiB |
| R7dbg | 3038 MiB | 14 MiB | 14 MiB |
| R8a | 3077 MiB | 9 MiB | 9 MiB |
| R8b | 3077 MiB | 9 MiB | 9 MiB |
| R8c | 3077 MiB | 9 MiB | 9 MiB |

