import json
import logging
import os
import traceback
from typing import Any, Dict, Optional, Type, TypeVar

import injector
from flask import Request
from injector import Injector
from werkzeug.local import LocalProxy

ROOT_LOGGER = "gunicorn.error"
PRETTY_JSON = os.environ.get("FLASK_ENV", "production") == "development"

T = TypeVar("T")


class JsonFormatter(logging.Formatter):
    """
    A formatter adhering to the structure advised in
    https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry.
    """

    injector: Injector = None
    # All of our logs must be children of the gunicorn.error log as long
    # as we continue to use gunicorn.
    root_logger: str = ROOT_LOGGER

    def _get_optional_injected(self, cls: Type[T]) -> Optional[T]:
        """
        Since log entries may happen outside of request scopes (e.g., during
        application start or crash, or during asynchronous processes, if any),
        we need to make sure that we don't get runtime errors when logging things;
        this will return `None` if the given class is not valid in the current scope.
        """
        if not self.injector:
            return None
        try:
            return self.injector.get(cls)
        except (
            # If injector tries to create an instance of an unbound object
            # but the object cannot be created
            injector.CallError,
            # If the injector tries to fetch an instance outside its
            # specified scope
            RuntimeError,
            # If the injector tries to fetch something it has no knowledge
            # of whatsoever.
            KeyError,
        ):
            return None

    def get_request(self) -> Optional[Request]:
        return self._get_optional_injected(Request)

    def get_session(self) -> Optional[LocalProxy]:
        return self._get_optional_injected(LocalProxy)

    def sanitize_logger_name(self, name: str):
        """
        Removes the scary looking 'gunicorn.error' string from the logs
        so as not to confuse anyone and also have nicer looking logs.
        """
        if name.startswith(self.root_logger):
            name = name.replace(self.root_logger, "")
            if not name:
                # All gunicorn logs go to the gunicorn.error log,
                # we rename it in our json payload to make it
                # more approachable
                name = "gunicorn_worker"
            if name.startswith("."):
                name = name[1:]
        return name

    def _append_request_log(self, data: Dict[str, Any]):
        request = self.get_request()
        if request:
            request_log = {
                "method": request.method,
                "url": request.url,
                "remoteIp": request.headers.get("X-Forwarded-For", request.remote_addr),
                "id": id(request),
            }
            session = self.get_session()
            if session and session.get("netid"):
                request_log["uwnetid"] = session["netid"]
            data["request"] = request_log

    @staticmethod
    def _append_custom_attrs(record: logging.LogRecord, data: Dict[str, Any]):
        if hasattr(record, "extra_keys"):
            extras = {key: getattr(record, key, None) for key in record.extra_keys}
            data.update(extras)

    @staticmethod
    def _append_exception_info(record: logging.LogRecord, data: Dict[str, Any]):
        if record.exc_info:
            exc_type, exc_message, tb = record.exc_info
            data["exception"] = {
                "message": f"{exc_type.__name__}: {exc_message}",
                "traceback": traceback.format_tb(tb, limit=20),
            }

    def format(self, record):
        data = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "line": f"{record.filename}#{record.funcName}:{record.lineno}",
            "logger": self.sanitize_logger_name(record.name),
        }
        self._append_request_log(data)
        self._append_custom_attrs(record, data)
        self._append_exception_info(record, data)

        kwargs = {}
        if PRETTY_JSON:
            kwargs["indent"] = 4
        return json.dumps(data, default=str, **kwargs)
