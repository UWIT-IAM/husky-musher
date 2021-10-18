ARG APP_SOURCE=ghcr.io/uwit-iam/husky-musher:latest
FROM ${APP_SOURCE} AS test-dependencies
WORKDIR /build
RUN poetry install --no-root --no-interaction

FROM test-dependencies
WORKDIR /musher
COPY ./tests ./tests
ENTRYPOINT ["bash", "-c", "pytest"]
