# prune-runner

The standard `ubuntu-latest` (`ubuntu-24.04` at the time of this writing in 2026) VM image on Github actions is full of ~~trash~~ unused things, which leaves only 14.3 GB out of the 76.9 GB disk image for the actual application code. This action cleans up **37 GB** of space total.

This Github action removes various components from the image in a systemd background job, i.e. as long as your tests are not filling up space faster than we can delete them, there should not be an issue. Deleting everything took about 125 seconds total in a cold-run measurement.

## Usage

Simply run the prune action first, it should take only a few hundred milliseconds to start the background deletion jobs.

```yaml
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: mbr/prune-runner@v1
        id: cleanup
      - uses: actions/checkout@v4
      # ...
```

If the job finishes before deletion is through, it does not hold up the completion of CI.


## Components deleted

| Group | Component | Approx. space freed (GB) |
| --- | --- | ---: |
| `android` | Android SDK | 11.8 |
| `dotnet` | .NET SDKs | 6.2 |
| `haskell` | GHC and GHCup | 3.9 |
| `swift` | Swift toolchain | 3.7 |
| `java` | Preinstalled JDKs | 1.5 |
| `powershell` | PowerShell | 1.4 |
| `browsers` | Chrome and Edge | Up to 1.3 |
| `toolcache` | Cached language runtimes and toolchains | 5.3 |
| `docker` | Docker/containerd images, containers, volumes, and cache | 2.0 |

Measured on Ubuntu image `20260920.314.1`, using decimal GB.


## Configuration

`remove` defaults to `all`, `keep` defaults to an empty list and beats `remove`. Both accept whitespace-separated group names, including multiline YAML.

To keep selected groups:

```yaml
- uses: mbr/prune-runner@v1
  with:
    keep: |
      docker
      java
      toolcache
```

To remove only specific groups:

```yaml
- uses: mbr/prune-runner@v1
  with:
    remove: |
      android
      dotnet
```


---

Two outputs describe the submission:

- `groups`: selected group names, separated by spaces.
- `units`: systemd service names, separated by spaces. Empty when nothing is selected.

Inspect them in a later step:

```yaml
- name: Inspect cleanup
  if: always()
  env:
    PRUNE_UNITS: ${{ steps.cleanup.outputs.units }}
  run: |
    for unit in $PRUNE_UNITS; do
      systemctl show "$unit" --property=Id,SubState,Result,ExecMainStatus
      sudo journalctl --no-pager --unit="$unit"
    done
```

A successfully finished service has `SubState=exited`, `Result=success`, and `ExecMainStatus=0`. For a completion gate, poll the units until they finish and reject failed results. Inspection alone does not wait or fail on a worker error.

## Runner requirements

Only disposable GitHub-hosted Ubuntu VMs with systemd are accepted. Self-hosted runners, container jobs, macOS, and Windows are rejected.

Deletion is irreversible. Do not install or use software in selected paths while cleanup is running. Keep `docker` if later steps need Docker or Docker-based actions. Normal Nix downloads under `/nix` do not target the directories being deleted, though concurrent cleanup can compete for disk I/O.

While the repository is private, reuse from other private repositories requires GitHub's action-sharing access setting. Public workflows cannot consume a private action.
