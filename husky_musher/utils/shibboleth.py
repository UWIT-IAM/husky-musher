import json
import os
from typing import Any, Dict


class AttributeURN:
    """
    Not all attributes are provided with friendly names by the
    uw_saml2 dependency. We alias them here so that our code is easier to read
    and maintain. If the package ever starts using the friendly names, we should
    pick them up natively once the friendly names are supported.

    Authorized users can learn more from
    https://wiki.cac.washington.edu/display/infra/Guide+to+NameID+Formats+and+Attributes+Available+from+the+UW+IdP
    """

    home_dept = "urn:oid:2.5.4.11"
    registered_surname = "urn:oid:1.2.840.113994.200.31"
    email = "urn:oid:0.9.2342.19200300.100.1.3"
    registered_given_name = "urn:oid:1.2.840.113994.200.32"


def extract_user_info(environ: dict) -> Dict[str, str]:
    """
    Extracts attributes of the authenticated user, provided by UW's IdP via our
    Shibboleth SP, from the request environment *environ*.

    Keys of the returned dict match those used by our REDCap project.
    """
    return {
        "uw_netid": environ.get("uwnetid"),
        # This won't always be @uw.edu.
        "uw_email": environ.get("email", environ.get(AttributeURN.email, "")),
        "first_name": environ.get(
            "registered_given_name", environ.get(AttributeURN.registered_given_name, "")
        ),
        "last_name": environ.get(
            "registered_surname", environ.get(AttributeURN.registered_surname, "")
        ),
        # Department is generally a colon-separated set of
        # increasingly-specific labels, starting with the School.
        "uw_school": environ.get("home_dept", environ.get(AttributeURN.home_dept, "")),
        **extract_affiliation(environ),
    }


def extract_affiliation(environ: dict) -> Dict[str, str]:
    """
    Transforms a multi-value affiliation string into our REDCap fields.

    Keys of the returned dict match those used by our REDCap project.

    For examples, see tests/test_shibboleth.py:test_extract_affiliation
    """

    affiliations = [a for a in environ.get("affiliations", []) if a != "member"]

    result = {"affiliation": "", "affiliation_other": ""}

    for affiliation in ("student", "faculty", "staff"):
        if affiliation in affiliations:
            result["affiliation"] = affiliation
            return result

    if "employee" in affiliations:
        result["affiliation"] = "staff"
    elif len(affiliations) > 0:
        result["affiliation"] = "other"
        result["affiliation_other"] = ";".join(sorted(affiliations))
    return result


def get_saml_attributes_from_env() -> Dict[str, Any]:
    """
    When testing locally or via docker, we don't use a real IdP,
    but mock the IdP instead. You can declare which attributes are
    included in the mocked IdP payload by setting it as an
    environment variable prefixed with `IDP_ATTR_`.

    Bear in mind that in the "real world," not all attributes
    are available using human-readable names (see AttributeURN),
    so a success locally does not necessary mean that
    the value will succeed when deployed.

    Also, the keys that /are/ human readable
    will be pre-pythonified by the uw_saml2 package,
    so use python naming conventions when pulling them out:
        uwNetID becomes uwnetid
        unscopedAffiliations becomes unscopd_affiliations
        (and so forth)
    """
    def import_value(string: str) -> Any:
        if string and string.startswith('[') or string.startswith('{'):
            return json.loads(string)
        return string

    attributes = {
        k.split("IDP_ATTR_")[1]: import_value(v)
        for k, v in os.environ.items()
        if k.startswith("IDP_ATTR_")
    }
    return attributes
