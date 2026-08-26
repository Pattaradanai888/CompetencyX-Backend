FROM python:3.12-slim AS builder

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /build

# Dependencies are installed before the source is copied so that editing code does
# not invalidate this layer. The cache mount keeps wheels across builds.
#
# Two constraints come from Railway's builder: a cache mount must carry an id, and
# that id has to literally spell out s/<service id>-<target> for the cache to be
# reused. It also supports no mount type other than cache, which is why the lock
# files are copied in rather than bind-mounted for the install.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=s/2ac3782d-47d9-493b-a8a8-a9796b4f5510-/root/.cache/uv,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . /build

# --no-dev drops the dev group that pyproject declares as a default group,
# so pytest/ruff stay out of the runtime image.
RUN --mount=type=cache,id=s/2ac3782d-47d9-493b-a8a8-a9796b4f5510-/root/.cache/uv,target=/root/.cache/uv \
    uv sync --frozen --no-dev && \
    chmod +x /build/docker/entrypoint.sh /build/docker/pre-deploy.sh

RUN mkdir -p /usr/src/app && \
    cp -r /build/. /usr/src/app/


# Runtime stage: interpreter, the prepared venv, and the app. No build tooling.
FROM python:3.12-slim AS production

ENV APPLICATION_ROOT=/usr/src/app \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=2 \
    WEB_TIMEOUT=120

RUN useradd --create-home --uid 1001 appuser

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
COPY --from=builder --chown=appuser:appuser /usr/src/app "$APPLICATION_ROOT"

WORKDIR "$APPLICATION_ROOT"

# collectstatic writes into static_root/ at boot, so the app must own its directory.
USER appuser

EXPOSE 8000

CMD ["./docker/entrypoint.sh"]
