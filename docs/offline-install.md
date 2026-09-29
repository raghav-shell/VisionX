# Offline installation and reproducible deployment

VisionSentinel has no runtime network dependency. Build artifacts may be prepared on a connected build host, verified, then transferred to an air-gapped operator host.

## Build host

```bash
docker compose build
docker save visionsentinel:local -o dist/visionsentinel-local.tar
cp docker-compose.yml dist/
cp deploy/users.example.json dist/users.json
chmod 0600 dist/users.json
python scripts/write_checksums.py dist
```

Replace both sample passwords in `dist/users.json` before transfer. Never commit that file.

## Air-gapped host

```bash
sha256sum -c SHA256SUMS
docker load -i visionsentinel-local.tar
mkdir -p deploy
mv users.json deploy/users.json
docker compose up -d
```

The service is bound to `127.0.0.1:8000` by default. Persistent evidence, reports, keys, SQLite state and uploaded assets live in the Docker volume `visionsentinel-data`; back it up through your platform’s volume-backup mechanism.

## Security notes

- The image runs as UID/GID `10001`, not root.
- `VISIONSENTINEL_INSECURE_COOKIES=1` is solely for the localhost HTTP compose configuration. Use HTTPS and remove it for any non-local deployment.
- The account seed file is mounted read-only, checked for mode `0600`, and is not copied into the image.
- Generate and verify `SHA256SUMS` before transfer. This checks delivery integrity, not the trustworthiness of the build host.
