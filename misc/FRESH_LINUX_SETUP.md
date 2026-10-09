# Fresh Linux cabinet

Use Ubuntu or Ubuntu-based Linux Mint on AMD64 or ARM64. Initial provisioning
requires internet. After an image is cached, the game and LAN status API work offline.

## Optional: reset an existing machine to a clean Mint installation

For machines with unknown packages, services and configuration, use a clean OS
reinstall before running these scripts. `linux_setup` provisions the existing OS;
it does not restore factory settings or remove arbitrary previous customizations.

1. Back up anything you want to retain to another machine or external drive.
   This includes personal files, SSH keys, cabinet configuration and Docker
   player-progress data if that progress needs to survive. An erased installation
   loses its cached images and progress; record the cabinet's network settings too.
2. Prepare a bootable USB installer for Ubuntu-based Linux Mint.
3. At the cabinet, boot from that USB and start the Mint installer.
4. For a dedicated cabinet whose OS disk can be completely erased, select the
   installer's erase-disk installation option. Verify the target disk carefully;
   disconnect other storage containing data you want to keep. If another OS or
   partition must remain, use a partition-preserving installation instead.
5. Create a normal administrator account with a password, finish installation,
   remove the installer USB when prompted, and boot into the new installation.
6. Connect to the network and follow the two-script setup below. Test SSH and sudo
   from your administration computer before leaving the cabinet.

This is an OS reinstall, not a manufacturer factory-image restoration. It replaces
old Linux services, packages and configuration on the erased disk. It does not
reset BIOS/UEFI settings or Arduino firmware. SSH host keys will change: when your
administration computer reports a changed host key, verify that it is the machine
you just reinstalled before replacing its saved SSH fingerprint.

Disk erasure is performed locally through the installer, not by either cabinet
script or through an SSH session. If you want to keep the installed Linux OS, use
[the migration instructions](UPGRADE_EXISTING_LINUX.md) instead; migration is not
a complete system reset.

## Install Linux, clone, run two scripts

During Linux installation, create a normal administrator account with a password
and connect the machine to your cabinet LAN. Connect the Arduino Mega with a working USB bootloader and a cabinet sketch
that prints `READY`. The current Docker controller checks its firmware identity
and automatically uploads the bundled sketch when it differs. An unresponsive
board requires manual diagnosis rather than a blind upload.
Configure BIOS/UEFI to power on after AC power returns.

Run these commands from that administrator account:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/CrackpotGumption/mole_code.git
cd mole_code
sudo bash misc/linux_setup
sudo bash misc/linux_bash_daemon
```

The first script updates Linux, installs Docker, OpenSSH and supporting tools,
enables SSH, Docker and Avahi hostname discovery at boot, grants the invoking account sudo access, disables
sleep, and creates `/etc/mole-cabinet/cabinet.conf` if it does not exist. Existing
configuration is preserved. If running directly as root, explicitly select an
existing normal account with `bash misc/linux_setup --admin-user YOUR_USER`.

The second script installs and immediately starts the boot service. Keep
`misc/collect_host_info.py` and `misc/host_agent.py` beside it; the installer uses that file to report host
versions and machine identity through `/diagnostics`. Defaults use
`myst1cus/mole-game:latest`, automatically select the only connected USB serial
device, publish status on port 8080, and store progress in `mole-game-data`.
No configuration editing is needed for a cabinet with one Arduino and a public
Docker image. If the Docker repository is private, run `sudo docker login` before
the second script. The current application must be built and published to Docker
Hub for cabinets to receive these changes; cloning Python files does not update
the downloaded image.

The launcher attempts to pull the newest image, falls back to the cached version
when offline, and restores the previous container if a replacement fails startup.
A first installation needs a published image and internet, or a preloaded image.
If Docker packages conflict, the first script reports them rather than removing
existing workloads. Resolve the reported packages before retrying.

## Verify and reboot

```bash
sudo systemctl status ssh mole-cabinet --no-pager
sudo docker ps --filter name=mole-game
curl --fail http://localhost:8080/health
curl --fail http://localhost:8080/state
hostname -I
sudo reboot
```

After reboot, verify the status endpoint and test physical badge reads, hits,
movement, lights, audio and payout. The current payout is seven tickets, with a
two-second-per-ticket firmware timeout (14 seconds total). The current Docker image automatically synchronizes the Mega firmware at startup.

## Remote administration

Use the administrator username created during installation and the cabinet LAN IP:

```bash
ssh YOUR_USER@CABINET_LAN_IP
sudo systemctl status mole-cabinet --no-pager
sudo journalctl -u mole-cabinet -n 100 --no-pager
sudo docker logs --tail 100 mole-game
```

SSH uses the existing account password or installed SSH keys; sudo asks for that
account's password. The script does not enable root SSH or passwordless sudo and
preserves existing SSH authentication settings. For a machine configured for
key-only SSH, install your public key in that account's `~/.ssh/authorized_keys`.
From a Linux/macOS administration machine with `ssh-copy-id`, you can install it
with `ssh-copy-id YOUR_USER@CABINET_LAN_IP` while password SSH is available.
Test remote login and `sudo -v` before leaving the cabinet.

An already-active UFW firewall receives an OpenSSH allow rule. Other firewalls or
network ACLs must permit SSH (normally TCP 22). Use a DHCP reservation for a stable
LAN IP; these scripts do not configure network addresses or off-site access.

To update the setup scripts later:

```bash
cd mole_code
git pull
sudo bash misc/linux_setup
sudo bash misc/linux_bash_daemon
```

The second script restarts the launcher and checks for the newest Docker image.
Run updates when no players are using the cabinet.

## LAN status and offline recovery

Open `http://CABINET_LAN_IP:8080/state` from the LAN, or
`http://localhost:8080/state` on the cabinet. `/health` is also available.
The cabinet also advertises its hostname using mDNS: a machine named `mole4`
is available as `http://mole4.local:8080/state` and
`http://mole4.local:8080/health`. SSH can use `ssh YOUR_USER@mole4.local`.
Give each cabinet a unique hostname during installation. To change an existing
cabinet name, run `sudo hostnamectl set-hostname mole4`, update the old hostname's
entry in `/etc/hosts` if present, then reboot. Local discovery requires a client
that supports mDNS and a LAN that allows multicast UDP 5353; it does not normally
cross VLANs or guest-network isolation. An active firewall may need an mDNS rule.
Bare names such as `mole4` require router/local DNS support; use `mole4.local`
for discovery provided by these scripts.
The `/diagnostics` endpoint reports software/firmware versions, host information,
connection/error details, and game/solve state. Host facts are a launch-time
snapshot. These endpoints return JSON. Existing firewall rules may need TCP 8080 allowed;
Docker-published ports have their own firewall behavior. Keep SSH and the
unauthenticated status API on the trusted cabinet network.

Test rebooting without internet while retaining the LAN. Allow about a minute
for the bounded image-pull attempt plus startup. Keep the cached Docker image
and the `mole-game-data` volume. Every cabinet restart starts a new game: no completed players, active puzzle,
payout or maintenance state is restored. The volume retains observational game
logs and machine settings/firmware history. Administrators can inspect
`/game/events` and explicitly restore through the API when needed.

## API administration

The installer enables `mole-host-agent.service`. No API token or authentication
header is required; router/LAN access controls who can administer the cabinet.
The API exposes host diagnostics/logs, serial receipts, maintenance/recovery,
game reset/restore, configuration, firmware retry, updates and host power controls.
See [API guide](API.md) for requests. Hardware changes require maintenance mode.
