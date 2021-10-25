import logging
import os
from logging.config import dictConfig
from typing import cast

import yaml
from flask import Flask, render_template, session as flask_session
from flask_injector import FlaskInjector, request
from flask_session import RedisSessionInterface, Session
from injector import Injector
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics
from redis import Redis
from werkzeug.local import LocalProxy
from yaml import SafeLoader

from husky_musher.blueprints.app import AppBlueprint
from husky_musher.blueprints.saml import MockSAMLBlueprint, SAMLBlueprint
from husky_musher.utils.cache import MockRedis
from husky_musher.utils.redcap import *

if os.environ.get("GUNICORN_LOG_LEVEL", None):
    MetricsClientCls = GunicornInternalPrometheusMetrics
else:
    MetricsClientCls = PrometheusMetrics


__HERE__ = os.path.dirname(os.path.abspath(__file__))


class InvalidNetId(BadRequest):
    detail = "Invalid NetID"
    code = 400


def configure_metrics(app_injector: FlaskInjector, settings: AppSettings):
    app = app_injector.app
    injector_ = app_injector.injector
    cls = PrometheusMetrics
    if os.environ.get("GUNICORN_LOG_LEVEL"):  # If gunicorn is configured and in use
        cls = GunicornInternalPrometheusMetrics
    metrics = cls(
        app,
        defaults_prefix=f"{settings.app_name}_flask",
    )
    app.metrics = metrics
    injector_.binder.bind(PrometheusMetrics, metrics, scope=singleton)
    return metrics


def configure_session_cache(app: Flask, cache: Cache, settings: AppSettings):
    if settings.redis_host:
        app.session_interface = RedisSessionInterface(
            redis=cache.redis, key_prefix=f"{cache.prefix}sessions."
        )
    else:
        Session(app)


def configure_session_settings(app: Flask, settings: AppSettings):
    app.secret_key = settings.secret_key
    app.session_cookie_name = settings.session_cookie_name
    app.permanent_session_lifetime = settings.session_lifetime
    app.config["SESSION_TYPE"] = "redis" if settings.redis_host else "filesystem"
    app.config["SESSION_KEY_PREFIX"] = f"{settings.app_name}:"


def register_error_handlers(app: Flask):
    # Always include a Cache-Control: no-store header in the response so browsers
    # or intervening caches don't save pages across auth'd users.  Unlikely, but
    # possible.  This is also appropriate so that users always get a fresh REDCap
    # lookup.
    @app.after_request
    def set_cache_control(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("page_not_found.html"), 404

    @app.errorhandler(InvalidNetId)
    def handle_bad_request(error):
        netid = error.description
        error.description = "[redacted]"
        app.logger.error(f"Invalid NetID", exc_info=error)
        return render_template("invalid_netid.html", netid=netid), InvalidNetId.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception(f"Unexpected error occurred: {error}")
        return render_template("something_went_wrong.html"), 500


class AppInjectorModule(Module):
    """
    This provides some boilerplate set up for the dependency
    injector. In short: it injects dependencies that can be
    automagically injected.
    """

    @provider
    @singleton
    def provide_redis(self, settings: AppSettings, logger: logging.Logger) -> Redis:
        """Provides a redis client instance."""
        if settings.redis_host:
            client = Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                username=settings.app_name,
                password=settings.redis_password,
            )
            try:
                # This helps ensure at boot that the client can connect
                # to its redis instance, so that we don't run the risk of
                # silently failing to set session information.
                if not all(client.time() or not client.set("husky-musher:test", "ok")):
                    raise ConnectionError
                logger.info(f"Successfully connected to redis.")
                return client
            except Exception as e:
                logger.error(
                    f"Unable to connect to redis host "
                    f"{settings.redis_host} as user {settings.app_name}: "
                    f"{e.__class__}: {str(e)}"
                )
                raise e

        return cast(Redis, MockRedis())

    @provider
    @singleton
    def provide_logger(self, injector: Injector) -> logging.Logger:
        """
        Provides a pre-configured logger that can be used application-wide.
        It is possible and encouraged to create child loggers where needed:

        class Foo:
            @inject
            def __init__(self, logger: Logger):
                self.timer_log = logger.getChild('timer')
                start_time = time.time()
                ...
                end_time = time.time()
                duration = end_time - start_time
                self.timer_log.info(f"Initialized {self}: [{duration}]", duration=duration)

        The above example would yield something like:
        """
        with open(os.path.join(__HERE__, "logging.yaml")) as f:
            logger_settings = yaml.load(f.read(), SafeLoader)
        dictConfig(logger_settings)
        app_logger = logging.getLogger("gunicorn.error").getChild("app")
        formatter = app_logger.handlers[0].formatter
        formatter.injector = injector
        return app_logger

    @provider
    @request
    def provide_session(self) -> LocalProxy:
        return cast(LocalProxy, flask_session)

    @provider
    @singleton
    def provide_app(
        self,
        injector_: Injector,
        app_blueprint: AppBlueprint,
        saml_blueprint: SAMLBlueprint,
        logger: logging.Logger,
    ) -> Flask:
        app = Flask(__name__)
        settings = injector_.get(AppSettings)
        app.logger = logger
        app.register_blueprint(app_blueprint)
        app.register_blueprint(saml_blueprint)
        if settings.use_mock_idp:
            from uw_saml2 import mock, python3_saml

            python3_saml.MOCK = True
            mock.MOCK_LOGIN_URL = "/mock-saml/login"
            app.register_blueprint(injector_.get(MockSAMLBlueprint))

        # Must create FlaskInjector /after/ all blueprints are registered
        flask_injector = FlaskInjector(app, injector=injector_)

        # Then we can configure anything dependent on
        # injected dependencies
        configure_metrics(flask_injector, settings)
        configure_session_settings(app, settings)
        configure_session_cache(app, injector_.get(Cache), settings)
        register_error_handlers(app)
        return app


def create_app_injector() -> Injector:
    """
    Creates an injector instance with the default modules installed.
    """
    modules = [AppInjectorModule, RedcapInjectorModule]
    return Injector(modules)


def create_app(injector_: Optional[Injector] = None):
    """
    Creates a new instance of the application. Optionally, callers
    can pass an instance of an Injector() that may already have some
    configuration or overrides already set up. This is helpful for
    testing.
    """
    if not injector_:
        injector_ = create_app_injector()
    return injector_.get(Flask)


if __name__ == "__main__":
    create_app().run()
