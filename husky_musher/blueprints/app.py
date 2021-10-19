import json
from logging import Logger

from flask import Blueprint, Request, jsonify, redirect, render_template
from injector import inject
from werkzeug.exceptions import BadRequest, MethodNotAllowed, Unauthorized
from werkzeug.local import LocalProxy

from husky_musher.settings import AppSettings
from husky_musher.utils.cache import Cache
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
    def __init__(self, settings: AppSettings, logger: Logger, cache: Cache):
        super().__init__("app", __name__)
        self.logger = logger
        self.cache = cache
        self.settings = settings
        self.add_url_rule("/", view_func=self.render_redirect, methods=("GET",))
        self.add_url_rule("/status", view_func=self.render_status, methods=("GET",))
        self.add_url_rule("/admin", view_func=self.render_admin, methods=("GET", "POST"))

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
        # All users of this application must be signed in
        if not session.get("netid"):
            return redirect("/saml/login")

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

    def _user_is_admin(self, session: LocalProxy) -> bool:
        """
        Checks whether the signed in user's session attributes
        contain an admin group. If there are no admin groups configured,
        always returns false.
        """
        groups = json.loads(session.get('attributes', '{}')).get('groups', [])
        for g in self.settings.admin_user_groups:
            if g in groups:
                return True

        return False

    def _op_cache_delete(self, request: Request):
        if request.method.upper() != 'POST':
            raise MethodNotAllowed
        netid = request.form.get('netid')
        payload = {}
        if netid:
            self.cache.delete(netid)
            payload['message'] = f'Deleted netid {netid} from the cache'
        else:
            payload['message'] = 'Error: No UW NetID supplied'
        return payload

    def render_admin(self, request: Request, session: LocalProxy):
        # The presence of a netid entry indicates the user has signed in.
        if not session.get('netid'):
            # If they haven't, we redirect them to do so.
            return redirect("/saml/login?return_to=/admin")

        if not self._user_is_admin(session):
            raise Unauthorized

        context = {}
        op = request.form.get('operation')
        if op:
            op_method = f'_op_{op}'
            context[op] = getattr(self, op_method)(request)

        return render_template('admin.html', **context)
