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

### Variance

| group | n | mean wall s | stdev s | min | max |
|---|---:|---:|---:|---:|---:|
| R0 cold | 1 | 322 | 0.0 | 322 | 322 |

## Per-module step wall time (s)

Whole `RUN /exp/step.sh <module>` = ansible.sh incl. apt, clone, configure, make, make clean.

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 27 | 12 | 13 | 13 | 19 | 11 | 11 | 9 | 118 | 41 | 15 | 8 |

## Per-module `make` (build only) wall time (s), from `/usr/bin/time -v`

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 0.8 | 2.7 | 2.4 | 2.7 | 6.3 | 0.5 | 1.5 | 0.3 | 16.1 | 1.1 | 3.0 | 1.5 |

## Per-module sccache hit rate (hits/(hits+misses)) and misses

| run | iocStats | sequencer | sscan | calc | asyn | busy | autosave | pvlogging | ADCore | ffmpegServer | ADSimDetector | ioc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | – | – | – | – | – | – | – | – | – | – | – | – |

## Where the time goes, by ansible task category (s, summed over modules)

Categories come from the ansible callback timer: `apt` = system/apt/get_url tasks, `clone` = git tasks, `facts` = fact gathering, `ansible_startup` = process start to first task, `ansible_other` = all other tasks (RELEASE fixups, patching, ibek, runtime lists), `make` / `make_clean` = the build and clean tasks, `sccache_srv` = start/zero/stats/stop of the sccache server in the wrapper (experiment overhead). `docker other` = wall minus ansible steps (uv pip install, COPY layers incl. seed cache COPY, manifest, export).

| run | apt | clone | facts | ansible_startup | ansible_other | make | make_clean | ansible_exit | sccache_srv | cascade_preclone | docker other | wall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 122 | 37 | 10 | 4 | 73 | 41 | 9 | 1 | 0 | 0 | 24 | 322 |

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

## Non-cacheable calls by reason (sccache `not_cached`)

| run |  |
|---|
| R0 |  |

## Image and cache sizes

| run | image bytes (docker inspect) | seed cache | cache after |
|---|---:|---:|---:|
| R0 | 2920 MiB | – | – |

