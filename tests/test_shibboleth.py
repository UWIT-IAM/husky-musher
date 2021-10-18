import os
from unittest import mock

import pytest

from husky_musher.utils.shibboleth import extract_affiliation, get_saml_attributes_from_env


@pytest.mark.parametrize(
    "attributes, expected",
    [
        (
            {"affiliations": ["member", "faculty", "employee", "alum"]},
            {"affiliation": "faculty", "affiliation_other": ""},
        ),
        (
            {"affiliations": ["member", "student", "staff"]},
            {"affiliation": "student", "affiliation_other": ""},
        ),
        (
            {"affiliations": ["member", "faculty", "student"]},
            {"affiliation": "student", "affiliation_other": ""},
        ),
        (
            {"affiliations": ["member", "staff", "alum"]},
            {"affiliation": "staff", "affiliation_other": ""},
        ),
        (
            {"affiliations": ["member", "employee"]},
            {"affiliation": "staff", "affiliation_other": ""},
        ),
        (
            {"affiliations": ["member", "affiliate", "alum"]},
            {"affiliation": "other", "affiliation_other": "affiliate;alum"},
        ),
        ({"affiliations": ["member"]}, {"affiliation": "", "affiliation_other": ""}),
        ({}, {"affiliation": "", "affiliation_other": ""}),
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
