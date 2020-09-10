import os
import json
import requests
from flask import Flask, redirect, request
from typing import Dict


REDCAP_API_TOKEN = os.environ['REDCAP_API_TOKEN']
REDCAP_API_URL = os.environ['REDCAP_API_URL']
IS_COMPLETE = 1
app = Flask(__name__)


def fetch_net_ids() -> Dict[str, str]:
    """
    Fetches all the existing NetIDs in the given REDCap project.
    """
    data = {
        'token': REDCAP_API_TOKEN,
        'content': 'record',
        'format': 'json',
        'type': 'flat',
        'csvDelimiter': '',
        'fields[0]': 'netid',
        'fields[1]': 'record_id',
        'fields[2]': 'eligibility_screening_complete',
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'exportSurveyFields': 'false',
        'exportDataAccessGroups': 'false',
        'returnFormat': 'json'
    }
    response = requests.post(REDCAP_API_URL, data=data)
    response.raise_for_status()

    return {
        record['netid']: {
            'record_id': record['record_id'],
            'eligibility_screening_complete': record['eligibility_screening_complete']
        } for record in response.json()
    }

def register_net_id(net_id: str) -> str:
    """
    Returns the REDCap record ID of the participant newly registered under the
    given *net_id*.
    """
    # REDCap enforces that we must provide a non-empty record ID. Because we're
    # using `forceAutoNumber` in the POST request, we do not need to provide a
    # real record ID.
    values = [{'netid': net_id, 'record_id': 'record ID cannot be blank'}]
    data = {
        'token': REDCAP_API_TOKEN,
        'content': 'record',
        'format': 'json',
        'type': 'flat',
        'overwriteBehavior': 'normal',
        'forceAutoNumber': 'true',
        'data': json.dumps(values),
        'returnContent': 'ids',
        'returnFormat': 'json'
    }
    response = requests.post(REDCAP_API_URL, data=data)
    response.raise_for_status()
    return response.json()[0]

def eligibility_screening_complete(user_data: Dict[str, str]) -> bool:
    """
    Returns True if a participant's eligiblity screening questionnaire is
    complete according to their *user_data*. Otherwise returns False.
    """
    def is_complete(code: str) -> bool:
        return int(code) >= IS_COMPLETE

    eligibility_screening_response = user_data.get('eligibility_screening_complete')

    if not eligibility_screening_response:
        return False

    return is_complete(eligibility_screening_response)

def generate_survey_link(record_id: str) -> str:
    """
    Returns a generated survey link to the eligibility screening instrument for
    the given *record_id*.
    """
    data = {
        'token': REDCAP_API_TOKEN,
        'content': 'surveyLink',
        'format': 'json',
        'instrument': 'eligibility_screening',
        'event': 'enrollment_arm_1',  # TODO subject to change
        'record': record_id,
        'returnFormat': 'json'
    }
    response = requests.post(REDCAP_API_URL, data=data)
    response.raise_for_status()
    return response.text


@app.route('/')
def main():
    # Get NetID from Shibboleth data
    net_id = request.remote_user

    while not net_id:
        # TODO: Redirect to Shibboleth login
        net_id = 'KaasenG'
        pass

    registered_users = fetch_net_ids()

    if net_id not in registered_users:
        # If not in REDCap project, create new record
        registered_users[net_id] = {'record_id': register_net_id(net_id)}

    record_id = registered_users[net_id]['record_id']

    # TODO -- generate a survey link for a particular day
    # We are awaiting finalization of the REDCap project to know how
    # daily attestations (repeating instruments) will be implemented.
    eligibility_screening_response = registered_users.get('eligibility_screening_complete')

    if eligibility_screening_complete(registered_users[net_id]):
        return f"Congrats, {net_id}, you're already registered under record ID " \
            f"{registered_users[net_id]['record_id']} and your eligibility " \
            "screening is complete!"

    # Generate a link to the eligibility questionnaire, and then redirect
    return redirect(generate_survey_link(record_id))
