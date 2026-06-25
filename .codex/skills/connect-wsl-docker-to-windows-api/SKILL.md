---
name: connect-wsl-docker-to-windows-api
description: Diagnose and connect Docker or FastGPT containers running under WSL to an HTTP API running on Windows. Use when Windows can call the API, WSL can reach it only through localhost, a container can ping the host but TCP curl is refused, host.docker.internal is unavailable, or a WSL socat relay through a Docker bridge is needed.
---

# Connect WSL/Docker to a Windows API

Establish the actual network path before changing firewall, proxy, or application code. Prefer a bridge-scoped relay when WSL can reach the Windows API through `127.0.0.1` but Docker containers cannot.

## Diagnose the three network scopes

1. Verify the Windows API on Windows:

   ```powershell
   uvicorn package.api:app --host 0.0.0.0 --port 8006
   curl.exe http://127.0.0.1:8006/health
   ```

2. Test from WSL:

   ```bash
   curl -v --noproxy '*' http://127.0.0.1:8006/health
   ip route
   ```

   With WSL mirrored networking, the default gateway may be the physical router rather than the Windows host. Do not assume the default gateway is the Windows API address. A successful WSL request to `127.0.0.1` proves Windows loopback forwarding is available.

3. Test inside the target container:

   ```sh
   GW=$(ip route | awk '/default/ {print $3; exit}')
   echo "$GW"
   curl -v --noproxy '*' "http://$GW:8006/health"
   ```

   `Connection refused` means nothing is listening on that Docker bridge address and port. Adding `host.docker.internal:host-gateway` only creates name resolution; it does not create a listener or relay.

Treat `ping` and `curl` separately: ping verifies ICMP reachability, while curl requires a reachable TCP listener. Use `--noproxy '*'` during diagnosis. Change `NO_PROXY` only when verbose curl output proves an HTTP proxy is being used; a successful direct call does not require a `NO_PROXY` change.

## Create a temporary WSL relay

Use this method when the API runs on Windows, WSL can call it through `127.0.0.1`, and the container cannot call it directly.

Ask before installing packages. Install `socat` in WSL if it is absent:

```bash
sudo apt update
sudo apt install -y socat
```

Read the gateway from inside the target container. For example, FastGPT may report `172.24.0.1`:

```sh
GW=$(ip route | awk '/default/ {print $3; exit}')
echo "$GW"
```

Run the relay in WSL, binding only to that Docker bridge address:

```bash
DOCKER_GW=172.24.0.1
RELAY_PORT=18006
WINDOWS_API_PORT=8006

sudo socat -d -d \
  TCP-LISTEN:${RELAY_PORT},bind=${DOCKER_GW},reuseaddr,fork \
  TCP:127.0.0.1:${WINDOWS_API_PORT}
```

Binding to the specific bridge is safer than `0.0.0.0`. Keep the command in the foreground for the first validation.

## Validate and configure the caller

From the container:

```sh
curl -v --noproxy '*' http://172.24.0.1:18006/health
```

After a `200 OK`, use the relay URL in FastGPT or the other containerized caller:

```text
http://172.24.0.1:18006/review
```

Validate with a dry-run request before enabling paid model calls. Do not add the bridge address to `NO_PROXY` unless the application actually routes it through a configured proxy.

## Persist only after validation

If a persistent relay is requested, create a narrowly scoped systemd service whose `ExecStart` contains the verified bridge address and ports. Ask before creating or enabling it. Recheck the bridge gateway whenever Docker networks are recreated because the address can change.

Stop a foreground relay with `Ctrl+C`. Remove or update any persistent relay when the API port, Docker network, or WSL networking mode changes.

## Common wrong turns

- Do not use the physical router address as the Windows host merely because it is WSL's default gateway.
- Do not assume successful ping proves the TCP port is reachable.
- Do not change API input schemas to solve a transport-layer connection refusal.
- Do not open a broad Windows firewall rule before confirming where the request stops.
- Do not bind the relay to all interfaces unless remote exposure is explicitly required and secured.
