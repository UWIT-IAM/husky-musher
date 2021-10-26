import os
from unittest import mock

import pytest

from husky_musher.utils.shibboleth import extract_affiliation, get_saml_attributes_from_env


@pytest.mark.parametrize(
    "attributes, expected",
    [
        (
            {"affiliations": ["member", "faculty", "employee", "alum"]},
            {"affiliation_capture": "faculty", "affiliation_capture_oth": ""},
        ),
        (
            {"affiliations": ["member", "student", "staff"]},
            {"affiliation_capture": "student", "affiliation_capture_oth": ""},
        ),
        (
            {"affiliations": ["member", "faculty", "student"]},
            {"affiliation_capture": "student", "affiliation_capture_oth": ""},
        ),
        (
            {"affiliations": ["member", "staff", "alum"]},
            {"affiliation_capture": "staff", "affiliation_capture_oth": ""},
        ),
        (
            {"affiliations": ["member", "employee"]},
            {"affiliation_capture": "staff", "affiliation_capture_oth": ""},
        ),
        (
            {"affiliations": ["member", "affiliate", "alum"]},
            {"affiliation_capture": "other", "affiliation_capture_oth": "affiliate;alum"},
        ),
        ({"affiliations": ["member"]}, {"affiliation_capture": "", "affiliation_capture_oth": ""}),
        ({}, {"affiliation_capture": "", "affiliation_capture_oth": ""}),
    ],
)
def test_extract_affiliation(attributes, expected):
    assert extract_affiliation(attributes) == expected


def test_get_saml_attributes_from_env():
    with mock.patch.dict(os.environ) as env:
        env.update({
            "IDP_ATTR_uwNetID": "foo",
            "IDP_ATTR_email": "foo@uw.edu",
            "IDP_ATTR_registeredGivenName": "First Middle",
            "IDP_ATTR_registeredSurname": "Surname",
            "IDP_ATTR_homeDept": "UW-IT ITI",
            "IDP_ATTR_affiliations": "[\"member\", \"staff\"]",
        })
        attrs = get_saml_attributes_from_env()

    assert attrs == {
        "uwNetID": "foo",
        "email": "foo@uw.edu",
        "registeredGivenName": "First Middle",
        "registeredSurname": "Surname",
        "homeDept": "UW-IT ITI",
        "affiliations": ["member", "staff"],
    }
