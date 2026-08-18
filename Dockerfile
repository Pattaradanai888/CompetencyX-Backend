FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    # `default-groups = ["dev"]` in pyproject.toml makes every `uv run` re-sync the dev
    # group, which would re-download ruff/pytest from PyPI on each container start and
    # undo the `--no-dev` install below. The image is already provisioned; never re-sync.
    UV_NO_SYNC=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN chmod +x docker/entrypoint.sh

EXPOSE 8000

CMD ["./docker/entrypoint.sh"]
