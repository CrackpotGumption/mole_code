# Linux cabinet installation

Detailed instructions:
- [API administration and recovery](API.md)
- [Fresh Linux installation, including an optional clean OS reset](FRESH_LINUX_SETUP.md)
- [Migration from the previous instructions](UPGRADE_EXISTING_LINUX.md)

These scripts support Ubuntu and Ubuntu-based Linux Mint. Initial provisioning
requires internet access. Booting an already installed cabinet does not.

1. Keep the complete `misc` folder on the cabinet, including the host collector and agent, and run:
   `sudo bash misc/linux_setup`
2. Edit `/etc/mole-cabinet/cabinet.conf`:
   - `IMAGE` defaults to `myst1cus/mole-game:latest`; publish it before deployment.
   - Set `SERIAL_DEVICE` to the Arduino's `/dev/serial/by-id/...` path.
     If empty, the launcher selects a device only when exactly one is present.
   - Port 8080 is published on all host interfaces by default.
3. Install autostart: `sudo bash misc/linux_bash_daemon`
4. Once an image is published/configured, start it with:
   `sudo systemctl start mole-cabinet`
5. Reboot after provisioning to apply power-management and group changes.
   Configure the BIOS to power on after AC power is restored if required.

Provisioning updates packages, installs Docker, curl, Python for tooling and
USB utilities, enables unattended security updates, and prevents sleep/lid
suspension. The game and pyserial run inside the Docker image. Provisioning
does not launch a container, change the hostname, grant Docker group access,
or enable a separate host Python game service. Existing cabinet configuration
is preserved on reruns. Conflicting Docker installations require explicit
removal before provisioning continues.

The autostart installer writes a local launcher and `mole-cabinet.service`.
It enables the service for future boots and starts/restarts it immediately.
The previous `run-plainraw.service`, if present, is disabled. No remote scripts
are downloaded. The configuration must stay root-owned since it is sourced
by a root service.

On each boot the launcher waits up to 60 seconds for the Arduino, tries a
bounded image pull (45 seconds), and uses the cached image if the pull fails.
The first installation needs either a successful pull or an image imported
with `sudo docker load -i game-image.tar`. An image placeholder causes a clear
failure without stopping existing containers.

Updates use the resolved local image ID, pass through only the selected serial
device, set `ARDUINO_PORT`, mount `mole-game-data` for durable completed-player
progress, publish the status port, and rotate container logs
at 10 MB with three files. The previous container is retained until the new
container's `/state` endpoint responds. Failed creation/startup restores the
previous container, and systemd retries after 60 seconds. This check verifies
application startup; it cannot prove physical sensors or the ticket dispenser
work. The Docker restart policy handles subsequent process exits.

Offline status URLs on the cabinet or another LAN computer:
- `http://localhost:8080/state` on the cabinet
- `http://CABINET_LAN_IP:8080/state` from the LAN
- `/health` is also available; these are JSON endpoints, not an HTML dashboard.

A local network connection and cabinet IP are still necessary for access from
another computer. Configure a DHCP reservation or static address separately.
Existing firewall/network rules may need to permit port 8080. The status API
has no authentication, so expose it only on a trusted cabinet network.

Diagnostics:
```
sudo systemctl status mole-cabinet
sudo journalctl -u mole-cabinet -f
sudo docker logs --tail 100 mole-game
sudo systemctl restart mole-cabinet  # retry/update now
```

A leftover `mole-game-previous` container indicates an interrupted update. The
launcher refuses to overwrite it; inspect/recover it before retrying. Repeated
image updates retain cached images; manage old image storage as needed without
removing the offline fallback image.

Hardware-free verification:
`python3 -B -m unittest discover -s misc/tests -v`

Audio defaults to enabled when the host has `/dev/snd`; playback uses the
container's ALSA device. Set `AUDIO_DEVICE` for the actual cabinet speaker,
`AUDIO_ENABLED=0` for silent operation, and `FAILURE_SECONDS` for the failure
animation duration (default 15 seconds). Existing config files are preserved:
add these keys manually if desired. See `python/README.md` for sound replacement
and device-check instructions.

The final winning celebration uses `VICTORY_SECONDS` (default 45). Python
now follows the standard v2 wiring. The updated v2 sketch includes nonblocking
ticket payout and RGB player lights for interactive bashing during payout;
flash the updated firmware alongside the image. See `python/README.md`.
