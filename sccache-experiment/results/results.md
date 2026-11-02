# sccache experiment results

## Machine

```
date: 2026-11-02T17:08:45Z
host_os: Ubuntu 24.04.5 LTS
kernel: 6.18.44-fc-v185
nproc: 4
cpu: Intel(R) Xeon(R) Processor
ram: 15 GiB
disk_rotational_flag: zram0    0 vda      1 vdb      1 vdc      1 vdd      1 vde      1 vdf      1 
docker_root_fs: /dev/vda       ext4  252G   12G   27G  31% /var/lib/docker
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
| R1 | sccache, empty cache = release build | 332 | 103% | 296 | 41 | 425 | 0 | 208 | 0.0% | 196 | 19 | 9 MiB |
| R2a | sccache warm (seeded from R1), direct mode on (default) | 326 | 101% | 283 | 13 | 425 | 205 | 3 | 98.6% | 196 | 19 | 9 MiB |

### Variance

| group | n | mean wall s | stdev s | min | max |
|---|---:|---:|---:|---:|---:|
| R0 cold | 1 | 322 | 0.0 | 322 | 322 |
| R2 warm (direct on) | 1 | 326 | 0.0 | 326 | 326 |

## Per-module step wall time (s)

Whole `RUN /exp/step.sh <module>` = ansible.sh incl. apt, clone, configure, make, make clean.

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 27 | 12 | 13 | 13 | 19 | 11 | 11 | 9 | 118 | 41 | 15 | 8 |
| R1 | 28 | 12 | 12 | 13 | 20 | 10 | 14 | 9 | 111 | 46 | 13 | 8 |
| R2a | 29 | 11 | 12 | 11 | 16 | 11 | 10 | 9 | 116 | 38 | 11 | 8 |

## Per-module `make` (build only) wall time (s), from `/usr/bin/time -v`

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 0.8 | 2.7 | 2.4 | 2.7 | 6.3 | 0.5 | 1.5 | 0.3 | 16.1 | 1.1 | 3.0 | 1.5 |
| R1 | 0.9 | 2.7 | 2.5 | 2.6 | 6.7 | 0.6 | 1.6 | 0.4 | 16.9 | 1.3 | 3.1 | 1.5 |
| R2a | 0.7 | 1.1 | 0.7 | 0.9 | 2.2 | 0.5 | 0.7 | 0.3 | 3.2 | 0.6 | 0.4 | 1.4 |

## Per-module sccache hit rate (hits/(hits+misses)) and misses

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | – | – | – | – | – | – | – | – | – | – | – | – |
| R1 | 0% (17m) | 0% (23m) | 0% (7m) | 0% (18m) | 0% (67m) | 0% (4m) | 0% (9m) | 0% (2m) | 0% (50m) | 0% (8m) | 0% (1m) | 0% (2m) |
| R2a | 100% (0m) | 91% (2m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 89% (1m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) | 100% (0m) |

## Where the time goes, by ansible task category (s, summed over modules)

Categories come from the ansible callback timer: `apt` = system/apt/get_url tasks, `clone` = git tasks, `facts` = fact gathering, `ansible_startup` = process start to first task, `ansible_other` = all other tasks (RELEASE fixups, patching, ibek, runtime lists), `make` / `make_clean` = the build and clean tasks, `sccache_srv` = start/zero/stats/stop of the sccache server in the wrapper (experiment overhead). `docker other` = wall minus ansible steps (uv pip install, COPY layers incl. seed cache COPY, manifest, export).

| run | apt | clone | facts | ansible_startup | ansible_other | make | make_clean | ansible_exit | sccache_srv | cascade_preclone | docker other | wall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 122 | 37 | 10 | 4 | 73 | 41 | 9 | 1 | 0 | 0 | 24 | 322 |
| R1 | 122 | 37 | 10 | 4 | 70 | 43 | 9 | 1 | 0 | 0 | 35 | 332 |
| R2a | 132 | 38 | 11 | 4 | 73 | 15 | 10 | 1 | 0 | 0 | 43 | 326 |

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

## Non-cacheable calls by reason (sccache `not_cached`)

| run | -E | -MM |
|---|---:|---:|
| R0 | 0 | 0 |
| R1 | 2 | 196 |
| R2a | 2 | 196 |

## Image and cache sizes

| run | image bytes (docker inspect) | seed cache | cache after |
|---|---:|---:|---:|
| R0 | 2920 MiB | – | – |
| R1 | 2971 MiB | – | 9 MiB |
| R2a | 2990 MiB | 9 MiB | 9 MiB |

