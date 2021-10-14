import functools
import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urlencode, urljoin

import requests
from id3c.cli.redcap import Project, is_complete
from injector import Module, inject, provider, singleton
from prometheus_client import Summary
from prometheus_client.registry import CollectorRegistry
from werkzeug.exceptions import BadRequest

from husky_musher.settings import AppSettings
from husky_musher.utils.cache import Cache


class REDCapValue(Enum):
    YES = "1"
    COMPLETE = "2"
    KIOSK_WALK_IN = "4"   # TODO: Not needed?


class REDCapRequestSecondsSummary(Summary):
    pass


class FetchParticipantMetric(REDCapRequestSecondsSummary):
    pass


class RedcapInjectorModule(Module):
    @provider
    @singleton
    def provide_metric_summary(self, registry: CollectorRegistry) -> REDCapRequestSecondsSummary:
        return REDCapRequestSecondsSummary(
            "redcap_request_seconds",
            documentation="Time spent making requests to REDCap",
            labelnames=['function'],
            registry=registry,
        )

    @provider
    @singleton
    def provide_redcap_project(self, settings: AppSettings) -> Project:
        return Project(settings.redcap_api_url, settings.redcap_project_id, token=settings.redcap_api_token)

    @provider
    @singleton
    def provide_prometheus_registry(self) -> CollectorRegistry:
        return CollectorRegistry()

    @provider
    @singleton
    def provide_fetch_participant_metric(
        self, summary: REDCapRequestSecondsSummary
    ) -> FetchParticipantMetric:
        return summary.labels("fetch_participant")


def time_redcap_request(label: Optional[str] = None):
    def decorator(method):
        @functools.wraps(method)
        def inner(*args, **kwargs):
            instance: REDCapClient = args[0]
            with instance.metric_summary.labels(label or method.__name__).time():
                return method(*args, **kwargs)

        return inner

    return decorator


@singleton
class REDCapClient:
    @inject
    def __init__(
        self,
        metric_summary: REDCapRequestSecondsSummary,
        cache: Cache,
        project: Project,
        settings: AppSettings,
        fetch_participant_metric: FetchParticipantMetric,
    ):
        self.fetch_participant_metric = metric_summary.labels("fetch_participant")
        self.cache = cache
        self.project = project
        self.settings = settings
        self.fetch_participant_metric = fetch_participant_metric
        self.metric_summary = metric_summary

    @time_redcap_request("fetch_participant (cached)")
    def fetch_participant(self, user_info: Dict) -> Optional[Dict[str, str]]:
        """
        Exports a REDCap record matching the given *user_info*. Returns None if no
        match is found.

        Raises an :class:`AssertionError` if REDCap returns multiple matches for the
        given *user_info*.
        """
        uw_netid = user_info["uw_netid"]
        record = self.cache.get(uw_netid, load_json=True)

        if not record:
            with self.fetch_participant_metric.time():
                fields = [
                    "uw_netid",
                    "record_id",
                    "enrollment_questions_complete",
#                    "eligibility_screening_complete",
#                    "consent_form_complete",
#                    "enrollment_questionnaire_complete",
                ]

                data = {
                    "token": self.project.api_token,
                    "content": "record",
                    "format": "json",
                    "type": "flat",
                    "csvDelimiter": "",
                    "filterLogic": f'[uw_netid] = "{uw_netid}"',
                    "fields": ",".join(map(str, fields)),
                    "rawOrLabel": "raw",
                    "rawOrLabelHeaders": "raw",
                    "exportCheckboxLabel": "false",
                    "exportSurveyFields": "false",
                    "exportDataAccessGroups": "false",
                    "returnFormat": "json",
                }

                response = requests.post(self.project.api_url, data=data)
                response.raise_for_status()

                records = response.json()

                if not records:
                    return None

                if len(records) > 1:
                    raise BadRequest(
                        f'Multiple records exist with NetID "{uw_netid}": '
                        f'{[r["record_id"] for r in records]}'
                    )

                record = records[0]

            if self.redcap_registration_complete(record):
                self.cache.set(uw_netid, record)

        return record

    @time_redcap_request()
    def register_participant(self, user_info: dict) -> str:
        """
        Returns the REDCap record ID of the participant newly registered with the
        given *user_info*
        """
        # REDCap enforces that we must provide a non-empty record ID. Because we're
        # using `forceAutoNumber` in the POST request, we do not need to provide a
        # real record ID.
        records = [{**user_info, "record_id": "record ID cannot be blank"}]
        data = {
            "token": self.project.api_token,
            "content": "record",
            "format": "json",
            "type": "flat",
            "overwriteBehavior": "normal",
            "forceAutoNumber": "true",
            "data": json.dumps(records),
            "returnContent": "ids",
            "returnFormat": "json",
        }
        response = requests.post(self.project.api_url, data=data)
        response.raise_for_status()
        return response.json()[0]

    @time_redcap_request()
    def generate_survey_link(
        self, record_id: str, event: str, instrument: str, instance: int = None
    ) -> str:
        """
        Returns a generated survey link for the given *instrument* within the
        *event* of the *record_id*.

        Will include the repeat *instance* if provided.
        """
        data = {
            "token": self.project.api_token,
            "content": "surveyLink",
            "format": "json",
            "instrument": instrument,
            "event": event,
            "record": record_id,
            "returnFormat": "json",
        }

        if instance:
            data["repeat_instance"] = str(instance)

        response = requests.post(self.project.api_url, data=data)
        response.raise_for_status()
        return response.text

    def get_todays_repeat_instance(self) -> int:
        """
        Returns the repeat instance number, i.e. days since the start of the study
        with the first instance starting at 1.
        """
        return 1 + (datetime.today() - self.settings.redcap_study_start_date).days

    def get_the_current_week(self) -> int:
        """
        Returns the current program week to redirect the user to the correct first weekly event
        with the first week starting at 1
        """
        return 1 + (datetime.today() - self.settings.redcap_study_start_date).days // 7

    def redcap_registration_complete(self, redcap_record: dict) -> bool:
        """
        Returns True if a given *redcap_record* shows a participant has completed
        the enrollment surveys. Otherwise, returns False.

        >>> self.redcap_registration_complete(None)
        False

        >>> self.redcap_registration_complete({})
        False

        >>> self.redcap_registration_complete({ \
            'eligibility_screening_complete': '1', \
            'consent_form_complete': '2', \
            'enrollment_questionnaire_complete': '0'})
        False

        >>> self.redcap_registration_complete({ \
            'eligibility_screening_complete': '2', \
            'consent_form_complete': '2', \
            'enrollment_questionnaire_complete': '1'})
        False

        >>> self.redcap_registration_complete({ \
            'eligibility_screening_complete': '2', \
            'consent_form_complete': '2', \
            'enrollment_questionnaire_complete': '2'})
        True
        """
        if not redcap_record:
            return False

        return (
            is_complete("enrollment_questions", redcap_record)
#            is_complete("eligibility_screening", redcap_record)
#            and is_complete("consent_form", redcap_record)
#            and is_complete("enrollment_questionnaire", redcap_record)
        )

    @time_redcap_request()
    def fetch_encounter_events_past_week(self, redcap_record: dict) -> List[dict]:
#TODO: don't need this
        """
        Given a *redcap_record*, export the full list of related REDCap instances
        from the Encounter arm of the project that have occurred in the past week.
        """
        fields = [
            "record_id",
            "testing_trigger",
            "testing_determination_complete",
            "kiosk_registration_4c7f_complete",
            "test_order_survey_complete",
        ]
        # Unfortunately, despite its appearance in the returned response from REDCap,
        # `redcap_repeat_instance` is not a field we can query by when exporting
        # REDCap records. However, it does get returned when we request `record_id`
        # as a field.
        #
        # Additionally, the `dateRangeBegin` key in REDCap is not
        # useful to us, because all instances associated with a record are returned,
        # regardless of the instance's creation or modification date.
        data = {
            "token": self.project.api_token,
            "content": "record",
            "format": "json",
            "type": "flat",
            "csvDelimiter": "",
            "events": "encounter_arm_1",
            "records": redcap_record["record_id"],
            "fields": ",".join(map(str, fields)),
            "rawOrLabel": "label",
            "rawOrLabelHeaders": "raw",
            "exportCheckboxLabel": "false",
            "exportSurveyFields": "false",
            "exportDataAccessGroups": "false",
            "returnFormat": "json",
        }

        response = requests.post(self.project.api_url, data=data)
        response.raise_for_status()

        encounters = response.json()
        return [
            e for e in encounters if e["redcap_repeat_instance"] >= self.one_week_ago()
        ]

    def one_week_ago(self) -> int:
#TODO: don't need this
        """
        Return the REDCap instance instance currently representing one week ago.
        """
        return self.get_todays_repeat_instance() - 7

    def max_instance_testing_triggered(
#TODO: don't need this
        self, redcap_record: List[dict]
    ) -> Optional[int]:
        """
        Returns the most recent instance number in a *redcap_record* with
        `testing_trigger` = "Yes".

        Returns None if no such instances exist.
        """
        events_testing_trigger_yes = [
            encounter
            for encounter in redcap_record
            if encounter["testing_trigger"] == "Yes"
        ]

        if not events_testing_trigger_yes:
            return None

        return self._max_instance(events_testing_trigger_yes)

    def max_instance(
#TODO: don't need this
        self,
        instrument: str,
        redcap_record: List[dict],
        since: int,
        complete: bool = True,
    ) -> Optional[int]:
        """
        Returns the most recent instance number in a *redcap_record* on or after the
        given filter instance *since*. Filters also by events with an *instrument*
        marked according to the given variable *complete* (True filters for only
        completed instances, and False filters only for incomplete or unverified
        instances). The default value for *complete* is True.

        Returns None if no completed insrument is found.

        >>> self.max_instance('kiosk_registration_4c7f', [ \
            {'redcap_repeat_instance': '1', 'kiosk_registration_4c7f_complete': '2'}], \
            since=0)
        1

        >>> self.max_instance('kiosk_registration_4c7f', [ \
            {'redcap_repeat_instance': '1', 'kiosk_registration_4c7f_complete': ''}, \
            {'redcap_repeat_instance': '2', 'kiosk_registration_4c7f_complete': '1'}, \
            {'redcap_repeat_instance': '3', 'kiosk_registration_4c7f_complete': '0'}], \
            since=0)

        >>> self.max_instance('kiosk_registration_4c7f', [ \
            {'redcap_repeat_instance': '1', 'kiosk_registration_4c7f_complete': ''}, \
            {'redcap_repeat_instance': '2', 'kiosk_registration_4c7f_complete': '1'}, \
            {'redcap_repeat_instance': '3', 'kiosk_registration_4c7f_complete': '0'}], \
            since=0, complete=False)
        3

        >>> self.max_instance('kiosk_registration_4c7f', [ \
            {'redcap_repeat_instance': '1', 'kiosk_registration_4c7f_complete': '2'}, \
            {'redcap_repeat_instance': '2', 'kiosk_registration_4c7f_complete': '2'}, \
            {'redcap_repeat_instance': '3', 'kiosk_registration_4c7f_complete': '0'}], \
            since=2)
        2

        >>> self.max_instance('kiosk_registration_4c7f', [ \
            {'redcap_repeat_instance': '1', 'kiosk_registration_4c7f_complete': '0'}, \
            {'redcap_repeat_instance': '2', 'kiosk_registration_4c7f_complete': '0'}, \
            {'redcap_repeat_instance': '3', 'kiosk_registration_4c7f_complete': '2'}], \
            since=2, complete=False)
        2

        >>> self.max_instance('kiosk_registration_4c7f', [ \
            {'redcap_repeat_instance': '1', 'kiosk_registration_4c7f_complete': '2'}, \
            {'redcap_repeat_instance': '2', 'kiosk_registration_4c7f_complete': '2'}, \
            {'redcap_repeat_instance': '3', 'kiosk_registration_4c7f_complete': '0'}], \
            since=3)

        >>> self.max_instance('test_order_survey', [ \
            {'redcap_repeat_instance': '1', 'test_order_survey_complete': '1', \
                'kiosk_registration_4c7f_complete': ''}, \
            {'redcap_repeat_instance': '2', 'test_order_survey_complete': '', \
                'kiosk_registration_4c7f_complete': '2'}], \
            since=0)
        """
        events_instrument_complete = [
            encounter
            for encounter in redcap_record
            if encounter[f"{instrument}_complete"] != ""
            and is_complete(instrument, encounter) == complete
        ]

        # Filter since the latest instance where testing was triggered.
        # If no instance exists, do not filter. Note: at this point in the code, we
        # already are only considering instances in the past week.
        if since is not None:
            events_instrument_complete = list(
                filter(
                    lambda encounter: int(encounter["redcap_repeat_instance"]) >= since,
                    events_instrument_complete,
                )
            )

        if not events_instrument_complete:
            return None

        return self._max_instance(events_instrument_complete)

    def _max_instance(self, redcap_record: List[dict]) -> int:
#TODO: don't need this
        """
        Internal helper method for :func:`max_instance`. Returns the repeat instance
        number associated with the most recent encounter in the given
        *redcap_record* data.

        Assumes that every event in the given *redcap_record* has a non-empty value
        for 'redcap_repeat_instance'. Raises a :class:`KeyError` if
        'redcap_repeat_instance' is missing, or a :class:`ValueError` if
        'redcap_repeat_instance' is an empty string.

        Assumes that the given *redcap_record* contains at least one event with
        an associated 'redcap_repeat_instance'. Otherwise, throws a
        :class:`ValueError`.

        >>> self._max_instance([ \
            {'redcap_repeat_instance': '1'}, {'redcap_repeat_instance': '2'}, \
            {'redcap_repeat_instance': '5'}, {'redcap_repeat_instance': '10'}])
        10

        >>> self._max_instance([{'redcap_repeat_instance': '0'}])
        0

        >>> self._max_instance([])
        Traceback (most recent call last):
        ...
        ValueError: Expected non-empty *redcap_record*

        >>> self._max_instance([{'some_key': 'a value'}])
        Traceback (most recent call last):
        ...
        KeyError: "Expected every event in the given *redcap_record* to contain a key for 'redcap_repeat_instance'"

        >>> self._max_instance([{'redcap_repeat_instance': ''}])
        Traceback (most recent call last):
        ...
        ValueError: Expected every event in the given *redcap_record* to contain a non-empty string for 'redcap_repeat_instance'
        """
        if not redcap_record:
            raise ValueError("Expected non-empty *redcap_record*")

        try:
            max_instance = max(
                int(event["redcap_repeat_instance"]) for event in redcap_record
            )

        except KeyError:
            raise KeyError(
                "Expected every event in the given *redcap_record* to contain a "
                "key for 'redcap_repeat_instance'"
            )
        except ValueError:
            raise ValueError(
                "Expected every event in the given *redcap_record* to contain a "
                "non-empty string for 'redcap_repeat_instance'"
            )

        return max_instance

    @time_redcap_request()
    def create_new_testing_determination(self, redcap_record: dict):
#TODO: don't need this
        """
        Given a *redcap_record* to import, creates a new Testing Determination form
        instance with some pre-filled data fit for a kiosk walk-in.

        Raises an :class:`AssertionError` if the REDCap record import did not update
        exactly one record.
        """
        record = [
            {
                "record_id": redcap_record["record_id"],
                "redcap_event_name": "encounter_arm_1",
                "redcap_repeat_instance": str(self.get_todays_repeat_instance()),
                "testing_trigger": REDCapValue.YES,
                "testing_type": REDCapValue.KIOSK_WALK_IN,
                "testing_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "testing_determination_internal_complete": REDCapValue.COMPLETE,
            }
        ]

        data = {
            "token": self.project.api_token,
            "content": "record",
            "format": "json",
            "type": "flat",
            "overwriteBehavior": "normal",
            "forceAutoNumber": "false",
            "data": json.dumps(record),
            "returnContent": "ids",
            "returnFormat": "json",
        }

        response = requests.post(self.project.api_url, data=data)
        response.raise_for_status()

        assert (
            len(response.json()) == 1
        ), f"REDCap updated {len(response.json())} records, expected 1."

    def need_to_create_new_td_for_today(self, instances: Dict[str, int]) -> bool:
#TODO: don't need this
        """
        Returns True if we need to create a new TD instance for today. Otherwise,
        returns False.

        We need to create a new TD instance for today in the following conditions:
            1. No TD instance with [testing_trigger] = "Yes" exists in the past 7
               days.
            2. No complete TOS instance exists on or after the target TD instance,
               and a complete KR instance exists on or after the target TD instance.
            3. A complete TOS instance exists on or after the target TD instance,
               the TOS instance is not from today, and a complete KR instance exists
               on or after the target TD instance.

        *target_instance* is a TD instance number with [testing_trigger] = "Yes" in the
        past 7 days.

        *complete_tos_instance* is a TOS instance number marked complete on or after the
        given *target_instance*.

        *complete_kr_instance* is a KR instance number marked complete on or after the
        given *target_intance*.

        >>> self.need_to_create_new_td_for_today({'target': None, 'complete_tos': 1, 'complete_kr': 1})
        True

        >>> self.need_to_create_new_td_for_today({'target': 1, 'complete_tos': None, 'complete_kr': 1})
        True

        >>> self.need_to_create_new_td_for_today({'target': 1, 'complete_tos': 1, 'complete_kr': 1})
        True

        >>> self.need_to_create_new_td_for_today({'target': 1, 'complete_tos': None, 'complete_kr': None})
        False

        >>> self.need_to_create_new_td_for_today({'target': 1, 'complete_tos': None, 'complete_kr': 1})
        True

        >>> self.need_to_create_new_td_for_today({'target': 1, \
            'complete_tos': self.get_todays_repeat_instance(), 'complete_kr': 1})
        False

        >>> self.need_to_create_new_td_for_today({'target': 1, \
            'complete_tos': self.get_todays_repeat_instance(), 'complete_kr': None})
        False
        """
        if not instances["target"]:
            return True

        if instances["complete_tos"] != self.get_todays_repeat_instance():
            if instances["complete_kr"] is not None:
                return True

        return False

    def need_to_create_new_kr_instance(self, instances: Dict[str, int]) -> bool:
#TODO: don't need this
        """
        Returns True if we need to create a new KR instance for the target TD
        instance. Otherwise, returns False.

        We need to create a new KR instance in the following conditions. Both of
        these conditions assume a TD instance with [testing_trigger] = "Yes" exists
        in the past 7 days.
            1. No complete TOS instance exists on or after the target TD instance,
               and no KR instance exists on or after the target TD instance.
            2. A complete TOS instance exists on or after the target TD instance,
               the TOS instance is not from today, and no KR instance exists on or
               after the target TD instance.

        *target_instance* is a TD instance number with [testing_trigger] = "Yes" in the
        past 7 days.

        *complete_tos_instance* is a TOS instance number marked complete on or after the
        given *target_instance*.

        *complete_kr_instance* is a KR instance number marked complete on or after the
        given *target_intance*.

        >>> self.need_to_create_new_kr_instance({'target': None, 'complete_tos': 1, 'complete_kr': 1, 'incomplete_kr': None})
        False

        >>> self.need_to_create_new_kr_instance({'target': 1, 'complete_tos': None, 'complete_kr': 1, 'incomplete_kr': None})
        False

        >>> self.need_to_create_new_kr_instance({'target': 1, 'complete_tos': 1, 'complete_kr': 1, 'incomplete_kr': None})
        False

        >>> self.need_to_create_new_kr_instance({'target': 1, 'complete_tos': None, 'complete_kr': None, 'incomplete_kr': None})
        True

        >>> self.need_to_create_new_kr_instance({'target': 1, 'complete_tos': None, 'complete_kr': None, 'incomplete_kr': 2})
        False

        >>> self.need_to_create_new_kr_instance({'target': 1, 'complete_tos': None, 'complete_kr': 1, 'incomplete_kr': None})
        False

        >>> self.need_to_create_new_kr_instance({'target': 1, \
            'complete_tos': self.get_todays_repeat_instance(), 'complete_kr': 1, 'incomplete_kr': None})
        False

        >>> self.need_to_create_new_kr_instance({'target': 1, \
            'complete_tos': self.get_todays_repeat_instance(), 'complete_kr': None, 'incomplete_kr': None})
        False
        """
        # Just to be safe, check to make sure we don't need to create a TD instance
        # for today instead.
        if self.need_to_create_new_td_for_today(instances):
            return False

        complete_tos_instance = instances["complete_tos"]
        kr_exists = (
            instances["complete_kr"] is not None
            or instances["incomplete_kr"] is not None
        )

        if complete_tos_instance != self.get_todays_repeat_instance():
            return not kr_exists

        return False

    def kiosk_registration_link(
#TODO: don't need this
        self, redcap_record: dict, instances: Dict[str, int]
    ) -> str:
        """
        Given information about recent *instances* of a *redcap_record*, returns an
        internal link to the correct instance of a Kiosk Registration instrument
        according to the pre-determined logic flow.
        """
        incomplete_kr_instance = instances["incomplete_kr"]

        if self.need_to_create_new_td_for_today(instances):
            # Create TD instance based on # of days since project start.
            self.create_new_testing_determination(redcap_record)
            instance = self.get_todays_repeat_instance()

        elif self.need_to_create_new_kr_instance(instances):
            instance = instances["target"]

        elif incomplete_kr_instance is not None:
            instance = incomplete_kr_instance

        else:
            raise Exception("Logic error when generating survey links.")

        return self.generate_redcap_link(redcap_record, instance)

    def generate_redcap_link(self, redcap_record: dict, instance: int):
#TODO: don't need this
        """
        Given a *redcap_record*, generate a link to the internal REDCap portal's
        Kiosk Registration form for the record's given REDCap repeat *instance*.
        """
        query = urlencode(
            {
                "pid": self.project.id,
                "id": redcap_record["record_id"],
                "arm": "musher_test_event_arm_1",
                "event_id": self.settings.redcap_event_id,
                "page": "kiosk_registration_4c7f",
                "instance": instance,
            }
        )

        return urljoin(
            self.project.base_url,
            f"redcap_v{self.project.redcap_version}/DataEntry/index.php?{query}",
        )
