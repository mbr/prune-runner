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

An omitted or empty `remove` selects every supported group. Otherwise, specify the groups to remove, separated by whitespace, including multiline YAML. Unknown names fail when encountered; jobs already queued continue running.

To remove only specific groups:

```yaml
- uses: mbr/prune-runner@v1
  with:
    remove: |
      android
      dotnet
```

Deletion is irreversible. Do not install or use software in selected paths while cleanup is running. Use an explicit list without `docker` if later steps need Docker or Docker-based actions. Normal Nix downloads under `/nix` do not target the directories being deleted, though concurrent cleanup can compete for disk I/O.

While the repository is private, reuse from other private repositories requires GitHub's action-sharing access setting. Public workflows cannot consume a private action.
