import json
from logging import Logger

from flask import Blueprint, jsonify, redirect
from injector import inject
from werkzeug.local import LocalProxy

from husky_musher.settings import AppSettings
from husky_musher.utils.redcap import REDCapClient
from husky_musher.utils.shibboleth import (
    extract_user_info,
    get_saml_attributes_from_env,
)


class AppBlueprint(Blueprint):
    """
    The main external interface to the app; serves the API.
    """

    @inject
    def __init__(self, settings: AppSettings, logger: Logger):
        super().__init__("app", __name__)
        self.logger = logger
        self.settings = settings
        self.add_url_rule("/", view_func=self.render_redirect, methods=("GET",))
        self.add_url_rule("/status", view_func=self.render_status, methods=("GET",))

    def render_status(self):
        return (
            jsonify(
                {
                    "version": self.settings.version,
                    "deployment_id": self.settings.deployment_id,
                }
            ),
            200,
        )

    def render_redirect(
        self,
        client: REDCapClient,
        session: LocalProxy,
    ):
        if not session.get("netid"):
            return redirect("/saml/login")

        # Get NetID and other attributes from Shibboleth data
        if self.settings.in_development:
            attributes = get_saml_attributes_from_env()
        else:
            attributes = json.loads(session["attributes"])

        user_info = extract_user_info(attributes)
        redcap_record = client.fetch_participant(user_info)

        if not redcap_record:
            # If not in REDCap project, create new record
            new_record_id = client.register_participant(user_info)
            redcap_record = {"record_id": new_record_id}

        # Because of REDCap's survey queue logic, we can point a participant to an
        # upstream survey. If they've completed it, REDCap will automatically direct
        # them to the next, uncompleted survey in the queue.
        event = "enrollment_arm_1"
        instrument = "enrollment_questions"

        # If all enrollment event instruments are complete, point participants
        # to today's daily attestation instrument.
        # If the participant has already completed the daily attestation,
        # REDCap will prevent the participant from filling out the survey again.
        if client.redcap_registration_complete(redcap_record):
            current_week = str(client.get_the_current_week())
            event = "week_" + current_week + "_arm_1"
            instrument = "test_form"

        # Generate a link to the appropriate questionnaire, and then redirect.
        survey_link = client.generate_survey_link(
            redcap_record["record_id"], event, instrument
        )
        return redirect(survey_link)
