ARG APP_SOURCE=dependencies
ARG DEPLOYMENT_SOURCE=app

FROM ghcr.io/uwit-iam/uw-saml-poetry:latest AS postgresql-base
RUN apt-get update && \
    apt-get -y install git libpq-dev gcc && \
    pip install psycopg2 && \
    apt-get -y remove libpq-dev gcc

FROM postgresql-base AS dependencies
WORKDIR /build
COPY poetry.lock pyproject.toml ./
RUN poetry install --no-root --no-interaction --no-dev && \
    apt-get -y remove git

FROM ${APP_SOURCE} as app
ARG APP_VERSION
WORKDIR /musher
ENV PROMETHEUS_MULTIPROC_DIR='/tmp/prometheus' \
    GUNICORN_LOG_LEVEL=DEBUG \
    FLASK_ENV=development \
    PYTHONPATH=/app:$PYTHONPATH \
    APP_VERSION=${APP_VERSION}
COPY gunicorn.conf.py ./
COPY husky_musher ./husky_musher
RUN mkdir -pv $PROMETHEUS_MULTIPROC_DIR


FROM ${DEPLOYMENT_SOURCE} as deployment
ARG DEPLOYMENT_ID="None"
ENV DEPLOYMENT_ID=$DEPLOYMENT_ID
CMD gunicorn -c 'gunicorn.conf.py' 'husky_musher.app:create_app()'
