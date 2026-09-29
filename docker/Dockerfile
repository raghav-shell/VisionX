# syntax=docker/dockerfile:1
# Build the static dashboard separately, then serve it from the same origin as
# the FastAPI application. No CDN, proxy, or runtime package installation is used.
FROM node:22-bookworm-slim AS dashboard-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VISIONSENTINEL_HOME=/var/lib/visionsentinel \
    VISIONSENTINEL_DASHBOARD=/opt/visionsentinel/dashboard
WORKDIR /opt/visionsentinel
RUN groupadd --gid 10001 visionsentinel \
 && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/visionsentinel --shell /usr/sbin/nologin visionsentinel
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=dashboard-build /build/frontend/out ./dashboard/
COPY scripts/seed_users.py scripts/entrypoint.sh ./scripts/
RUN chmod 0555 ./scripts/entrypoint.sh \
 && mkdir -p "$VISIONSENTINEL_HOME" \
 && chown -R visionsentinel:visionsentinel /opt/visionsentinel "$VISIONSENTINEL_HOME"
USER visionsentinel:visionsentinel
EXPOSE 8000
VOLUME ["/var/lib/visionsentinel"]
ENTRYPOINT ["/opt/visionsentinel/scripts/entrypoint.sh"]
CMD ["visionsentinel", "server", "--host", "0.0.0.0", "--port", "8000"]
