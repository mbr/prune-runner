# prune-runner

Reclaim disk space on GitHub-hosted Ubuntu runners. Cleanup runs in background systemd services, so subsequent workflow steps can proceed immediately.

The default removes **all supported groups**, including Android, .NET, browsers, the hosted tool cache, and Docker storage. Keep anything later steps depend on.

```yaml
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: mbr/prune-runner@v1
        id: cleanup
      - uses: actions/checkout@v4
      - uses: cachix/install-nix-action@v31
      - run: nix build
```

No checkout, Nix installation, JavaScript bundle, or container is needed by the action itself. For immutable references, pin the action to a commit SHA instead of `v1`.

## Configuration

`remove` defaults to `all`. `keep` defaults to an empty list and takes precedence. Both accept whitespace-separated group names, including multiline YAML. Empty `remove` or `keep: all` selects nothing. Unknown names fail before any cleanup is launched.

Keep selected groups:

```yaml
- uses: mbr/prune-runner@v1
  with:
    keep: |
      docker
      java
      toolcache
```

Remove only selected groups:

```yaml
- uses: mbr/prune-runner@v1
  with:
    remove: |
      android
      dotnet
```

| Group | Removed paths or operation |
| --- | --- |
| `android` | `/usr/local/lib/android` |
| `dotnet` | `/usr/share/dotnet` |
| `haskell` | `/usr/local/.ghcup`, `/opt/ghc` |
| `swift` | `/usr/local/swift`, `/usr/share/swift` |
| `java` | `/usr/lib/jvm` |
| `powershell` | `/usr/local/share/powershell` |
| `browsers` | `/opt/google/chrome`, `/opt/microsoft/msedge` |
| `toolcache` | `/opt/hostedtoolcache` |
| `docker` | Stops `docker.socket`, `docker.service`, and `containerd.service`, then removes `/var/lib/docker` and `/var/lib/containerd` |
| `apt-cache` | Runs `apt-get clean`; installed packages stay installed |

These are directory groups, not dependency-aware language profiles. Keeping `java` does not preserve JDKs inside `toolcache`; keeping `android` does not automatically preserve Java. Missing directories are harmless. Package-manager records and symlinks outside the listed paths are not removed.

## Background execution

Each selected group gets one uniquely named transient systemd service. Services run concurrently as root, with a ten-minute execution limit and a thirty-second stop timeout. Kept groups launch nothing. Docker shutdown and deletion run sequentially inside its service; deletion is skipped if shutdown fails.

The action returns once the services have been submitted, **not when deletion has finished**. Successful submission does not guarantee successful cleanup. A later background failure cannot change the completed action step's status. Results and journals remain available for the lifetime of the runner.

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
