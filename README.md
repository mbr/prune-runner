# prune-runner

The standard `ubuntu-latest` (`ubuntu-24.04` at the time of this writing in 2026) VM image on Github actions is full of ~~trash~~ unused things, which leaves only (TKTK) GB out of the (TKTK) GB disk image for the actual application code.

This Github action removes various components from the image in a systemd background job, i.e. as long as your tests are not filling up space faster than we can delete them, there should not be an issue. Deleting everything takes about TKTK seconds total

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


## Components deleted

TKTK table of name, size, ~ space freed


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
