import getpass
import json
import urllib.parse
from logging import Logger
from typing import Dict

import uw_saml2
from flask import Blueprint, Request, redirect
from injector import inject
from uw_saml2.idp.uw import UwIdp
from werkzeug.local import LocalProxy

from husky_musher.settings import AppSettings


class SAMLBlueprint(Blueprint):
    @inject
    def __init__(
        self,
        idp_config: UwIdp,
        settings: AppSettings,
        logger: Logger,
    ):
        super().__init__("saml", __name__, url_prefix="/saml")
        self.idp_config = idp_config
        self.add_url_rule("/login", view_func=self.login, methods=["GET", "POST"])
        self.add_url_rule("/logout", view_func=self.log_out)
        self.settings = settings
        self.logger = logger

    def process_saml_request(self, request: Request, session: LocalProxy, **kwargs):
        dest_url = request.form.get("RelayState") or request.host_url
        post_args: Dict = request.form.copy()
        post_args.setdefault("RelayState", request.host_url)
        remote_ip = request.headers.get("X-Forwarded-For")
        self.logger.info(
            f"Processing SAML POST request from {remote_ip} to access {dest_url} with POST: {post_args}"
        )
        attributes = uw_saml2.process_response(post_args, **kwargs)
        session["attributes"] = json.dumps(attributes)
        session["netid"] = attributes["uwnetid"]
        self.logger.info(f"Signed in user {session['netid']}")
        return redirect(dest_url)

    def login(self, request: Request, session: LocalProxy):
        session.clear()
        acs_hostname = urllib.parse.urlparse(request.host_url).hostname
        acs_host = f"https://{acs_hostname}"
        acs_url = urllib.parse.urljoin(acs_host, self.settings.saml_acs_path)
        args = {
            "entity_id": self.settings.saml_entity_id,
            "acs_url": acs_url,
        }
        remote_ip = request.headers.get("X-Forwarded-For")

        if request.method == "GET":
            args["return_to"] = f"{acs_host}"
            self.logger.info(
                f"Getting SAML redirect URL for {remote_ip} to SAML sign in with args {args}"
            )
            url = uw_saml2.login_redirect(**args, force_authn=True)
            return redirect(url)

        return self.process_saml_request(request, session, **args)

    @staticmethod
    def log_out(session: LocalProxy):
        session.clear()
        return redirect("/")


class MockSAMLBlueprint(Blueprint):
    @inject
    def __init__(self):
        super().__init__("mock-saml", __name__, url_prefix="/mock-saml")
        self.add_url_rule(
            "/login", view_func=self.process_saml_request, methods=["GET"]
        )

    @staticmethod
    def process_saml_request(request: Request, session: LocalProxy, **kwargs):
        session["netid"] = getpass.getuser()
        session["attributes"] = json.dumps({"uid": getpass.getuser()})
        return redirect("/")
