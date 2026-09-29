#!/bin/sh
# Queues background cleanup using systemd.
set -efu

supported='android dotnet haskell swift java powershell browsers toolcache docker'

# Validates group names and normalizes whitespace for membership checks.
normalize() {
    names=' '
    for name in $1; do
        case " $supported all " in
            *" $name "*) names="$names$name " ;;
            *)
                printf 'Unknown cleanup group: %s\n' "$name" >&2
                exit 1
                ;;
        esac
    done
    printf '%s' "$names"
}

remove=$(normalize "${PRUNE_RUNNER_REMOVE-all}")
keep=$(normalize "${PRUNE_RUNNER_KEEP-}")

IFS= read -r nonce </proc/sys/kernel/random/uuid
prefix="prune-runner-$nonce"
selected=''
for group in $supported; do
    case "$remove" in *" all "* | *" $group "*) ;; *) continue ;; esac
    case "$keep" in *" all "* | *" $group "*) continue ;; esac
    selected="${selected:+$selected }$group"
done
[ -n "$selected" ] || exit 0

sudo -n true
for group in $selected; do
    case "$group" in
        android) set -- /usr/bin/rm -rf -- /usr/local/lib/android ;;
        dotnet) set -- /usr/bin/rm -rf -- /usr/share/dotnet ;;
        haskell) set -- /usr/bin/rm -rf -- /usr/local/.ghcup /opt/ghc ;;
        swift) set -- /usr/bin/rm -rf -- /usr/local/swift /usr/share/swift ;;
        java) set -- /usr/bin/rm -rf -- /usr/lib/jvm ;;
        powershell) set -- /usr/bin/rm -rf -- /usr/local/share/powershell ;;
        browsers) set -- /usr/bin/rm -rf -- /opt/google/chrome /opt/microsoft/msedge ;;
        toolcache) set -- /usr/bin/rm -rf -- /opt/hostedtoolcache ;;
        docker) set -- /bin/sh -eu -c '/usr/bin/systemctl stop docker.socket docker.service containerd.service
exec /usr/bin/rm -rf -- /var/lib/docker /var/lib/containerd' ;;
    esac
    unit="$prefix-$group.service"
    sudo -n systemd-run --system --quiet --no-block --unit="$unit" \
        --property=Type=oneshot --property=RemainAfterExit=yes \
        --property=TimeoutStartSec=10min --property=TimeoutStopSec=30s \
        --property=StandardOutput=journal --property=StandardError=journal \
        --setenv=PATH=/usr/sbin:/usr/bin:/sbin:/bin -- "$@"
    printf 'Queued %s: %s\n' "$group" "$unit"
done
