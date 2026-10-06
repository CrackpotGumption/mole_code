# Fresh Linux cabinet

Use Ubuntu or Ubuntu-based Linux Mint on an AMD64 or ARM64 machine. Initial
setup needs internet access. The installed game can subsequently run offline.
Use the current scripts from this checkout; they have not necessarily been
committed or published with the repository yet.

## 1. Prepare the machine

Install Linux, create a normal administrator user, and connect to the network.
Connect the Arduino by USB. Configure BIOS/UEFI to power on after AC power
returns. Choose a DHCP reservation or static LAN IP if other machines need a
stable status URL. The Linux scripts do not configure BIOS or networking.

Copy `linux_setup` and `linux_bash_daemon` from this repository's `misc` folder
into a `misc` folder on the cabinet. Open a terminal in the folder containing
`misc` and run:

```bash
sudo bash misc/linux_setup
```

This updates the OS, installs Docker and tools, enables Docker at boot,
disables sleep, and creates the root-owned cabinet configuration. If the script
reports conflicting Docker packages, stop and resolve that existing installation
before retrying; it deliberately does not remove other workloads automatically.

## 2. Configure the Arduino and image

Find the stable Arduino path:

```bash
ls -l /dev/serial/by-id/
sudo nano /etc/mole-cabinet/cabinet.conf
```

Use these settings, replacing the serial path with the complete path printed
above (not the symlink target):

```bash
IMAGE='myst1cus/mole-game:latest'
CONTAINER_NAME='mole-game'
SERIAL_DEVICE='/dev/serial/by-id/REPLACE_WITH_YOUR_ARDUINO'
STATUS_BIND='0.0.0.0'
STATUS_PORT=8080
FAILURE_SECONDS=15
VICTORY_SECONDS=45
AUDIO_ENABLED=1
AUDIO_DEVICE='default'
```

If `SERIAL_DEVICE` is empty, the launcher selects a USB serial device only when
exactly one is present. A stable explicit path is preferred for cabinet use.
The Arduino needs this project's compatible firmware; these scripts do not
flash it. The image supports raw `ACCEL` packets and legacy `HIT` packets.

Pull the game before starting to check registry access and seed the offline cache:

```bash
sudo docker pull myst1cus/mole-game:latest
```

If the Hub repository is private, first run `sudo docker login --username myst1cus`
(or use a read-only deployment account with access). The boot service runs as
root and uses root's Docker credentials. Do not put credentials in cabinet.conf.

## 3. Install and start autostart

```bash
sudo bash misc/linux_bash_daemon
sudo systemctl start mole-cabinet
sudo systemctl status mole-cabinet --no-pager
sudo docker ps --filter name=mole-game
curl --fail http://localhost:8080/health
curl --fail http://localhost:8080/state
```

The service waits for USB, attempts to pull the newest image, then starts the
container. A failed pull uses the locally stored version. Updates that fail
startup restore the previous container, when present, and retry later.
A service error can be diagnosed with:

```bash
sudo journalctl -u mole-cabinet -n 100 --no-pager
sudo docker logs --tail 100 mole-game
```

Reboot after successful setup:

```bash
sudo reboot
```

Verify that the game and status endpoints return after reboot. Then verify
physical badge reads, hits, mole movement, lights, and ticket payout on the
cabinet. Software startup checks cannot confirm mechanical operation.

## LAN and offline use

On another computer on the same LAN, open
`http://CABINET_LAN_IP:8080/state`. On the cabinet use
`http://localhost:8080/state`. `/health` is also available. These endpoints
return JSON, not an HTML dashboard. Internet access is unnecessary for them.

Existing firewall rules may need to allow TCP 8080 on your trusted cabinet LAN.
Docker port publication has its own firewall behavior; do not assume UFW alone
restricts it. Do not expose this unauthenticated API to the public internet.

Test a reboot with internet disconnected while retaining the local network.
Allow up to about a minute for the bounded image-pull attempt plus startup.
Keep the cached image: don't run image-pruning commands that remove it.
Completed players survive container restarts and reboots in the `mole-game-data`
volume. An unfinished player rescans their badge and restarts their puzzle.
Do not delete that volume. A completed full game remains completed until its
checkpoint is deliberately cleared for a new group.
