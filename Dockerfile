# Build stage: install the package and its dependencies into an isolated prefix.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY pipeline ./pipeline
RUN pip install --no-cache-dir --prefix=/install .

# Runtime stage: only the installed packages, running as a non-root user.
FROM python:3.12-slim
COPY --from=builder /install /usr/local
RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /home/app
ENTRYPOINT ["nfl-pipeline"]
CMD ["--help"]
