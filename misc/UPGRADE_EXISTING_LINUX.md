# Migrate an existing Linux cabinet

For machines in unknown states that you want fully reset, first use the clean
reinstall step in [fresh setup](FRESH_LINUX_SETUP.md). This migration preserves
the existing operating system and is not a factory reset.

Use this when Docker and the cabinet were installed using the previous
instructions. Initial migration needs internet access to obtain the new image;
subsequent boots can use its local copy offline. Perform migration between games,
since the old image does not persist progress. The new image saves completed
players in the `mole-game-data` volume; previously unrecorded progress cannot
be reconstructed automatically.

Copy the current `misc/linux_setup` and `misc/linux_bash_daemon` files onto the
cabinet. Work from the folder containing `misc`. Do not execute the old remote
bootstrap script or keep two startup launchers enabled.

## 1. Identify the old installation

```bash
sudo docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
sudo systemctl status run-plainraw.service --no-pager
sudo systemctl status arduino-app.service --no-pager
```

A missing service is normal. Previously used container names include `whac-game`,
`my-container`, and `mole-game`; identify which actually runs this cabinet.
Check any other manually created startup units too. Record the old container's
name and image, and preserve configuration if it already exists:

```bash
sudo docker inspect OLD_GAME_CONTAINER
# Run only if this configuration exists:
sudo cp -a /etc/mole-cabinet/cabinet.conf /etc/mole-cabinet/cabinet.conf.before-migration
```

Replace `OLD_GAME_CONTAINER` in all commands with the identified name. Do not
stop or rename unrelated containers. Keep its old image available for recovery.

## 2. Prepare dependencies and configuration

For machines provisioned by the previous large Mint bootstrap, run:

```bash
sudo bash misc/linux_setup
```

The updated script enables SSH and sudo for the invoking administrator, preserves existing cabinet.conf, and does not
start another game. It updates the OS, so use a maintenance window. If you
already have a working Docker installation that the script flags as conflicting,
keep it for this migration rather than removing it blindly. Ensure the launcher
requirements exist:

```bash
sudo apt-get update
sudo apt-get install -y curl python3 coreutils util-linux
sudo systemctl enable --now docker
```

If provisioning was skipped and cabinet.conf does not exist, create it:

```bash
sudo install -d -m 0755 /etc/mole-cabinet
sudo install -m 0600 /dev/null /etc/mole-cabinet/cabinet.conf
```

Do not run that `install ... /dev/null` command over an existing configuration.
Now find the Arduino and edit the configuration:

```bash
ls -l /dev/serial/by-id/
sudo nano /etc/mole-cabinet/cabinet.conf
```

Set all five values:

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

Keep the file root-owned with mode 0600:

```bash
sudo chown root:root /etc/mole-cabinet/cabinet.conf
sudo chmod 0600 /etc/mole-cabinet/cabinet.conf
sudo docker pull myst1cus/mole-game:latest
```

If the repository is private, authenticate with `sudo docker login` first.
Pull successfully before stopping the existing game.

## 3. Disable old launchers and preserve the old game

Disable these only if they exist and belong to this cabinet:

```bash
sudo systemctl disable --now run-plainraw.service
sudo systemctl disable --now arduino-app.service
```

If `mole-cabinet.service` already exists, stop it while migrating:

```bash
sudo systemctl stop mole-cabinet.service
```

These commands may report missing units on some machines. Also disable any
other startup mechanism that launches the old game. An old host Python service
can otherwise compete with the new container for the Arduino.

Preserve the identified old container under a separate recovery name. First
ensure `mole-game-legacy` is not already in use:

```bash
sudo docker container inspect mole-game-legacy
```

A "No such container" result means the name is available. If it exists,
resolve that previous migration before continuing. Then:

```bash
sudo docker update --restart=no OLD_GAME_CONTAINER
sudo docker stop --time 15 OLD_GAME_CONTAINER
sudo docker rename OLD_GAME_CONTAINER mole-game-legacy
```

This leaves the old container and its image available but prevents it from
restarting and occupying the serial device or port 8080. The new launcher will
use `mole-game`. It doesn't automatically roll back to a differently named legacy
container; manual recovery commands are below.

## 4. Install and validate the replacement

```bash
sudo bash misc/linux_bash_daemon
sudo systemctl start mole-cabinet
sudo systemctl status mole-cabinet --no-pager
sudo docker ps --filter name=mole-game
curl --fail http://localhost:8080/health
curl --fail http://localhost:8080/state
```

Verify physical gameplay. Open `http://CABINET_LAN_IP:8080/state` from another
LAN computer. Reboot and check autostart; then test a reboot without internet
while retaining the LAN. Allow the image-pull timeout to finish. JSON status
remains available locally and across the LAN. Retain the old container/image
until satisfied with the migration.

## Recovery if the replacement fails

Stop automatic retries, then stop the new container if it exists:

```bash
sudo systemctl disable --now mole-cabinet
sudo docker update --restart=no mole-game
sudo docker stop --time 15 mole-game
sudo docker update --restart=unless-stopped mole-game-legacy
sudo docker start mole-game-legacy
```

Skip commands targeting `mole-game` if it was never created. Check the restored
container with `sudo docker logs --tail 100 mole-game-legacy`. Keep the old remote
bootstrap disabled so it cannot unexpectedly replace the recovery container.
For a later retry, stop the legacy container and disable its restart policy
again before enabling and starting `mole-cabinet`.

Remote administration uses `ssh YOUR_USER@CABINET_LAN_IP`, then password-protected sudo. Run `linux_setup` from that normal account with sudo (or pass `--admin-user EXISTING_USER` when running as root). The daemon installer now starts/restarts the game immediately; perform migration while the cabinet is idle. See [fresh setup](FRESH_LINUX_SETUP.md) for SSH verification.
