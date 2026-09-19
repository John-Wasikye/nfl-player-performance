# Build stage: install the package and its dependencies into an isolated prefix.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY pipeline ./pipeline
RUN pip install --no-cache-dir --prefix=/install .

# Runtime stage: only the installed packages and the dbt project, running as a non-root user.
FROM python:3.12-slim
COPY --from=builder /install /usr/local
# LightGBM needs the OpenMP runtime, which the slim image does not include.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
USER app
WORKDIR /home/app
COPY --chown=app:app dbt ./dbt
# dbt writes build output and logs next to the project by default; keep them out of the image.
ENV DBT_DIR=/home/app/dbt \
    DBT_TARGET_PATH=/tmp/dbt-target \
    DBT_LOG_PATH=/tmp/dbt-logs \
    DBT_SEND_ANONYMOUS_USAGE_STATS=False
ENTRYPOINT ["nfl-pipeline"]
CMD ["--help"]
