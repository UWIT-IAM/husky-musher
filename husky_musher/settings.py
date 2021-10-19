import os
from datetime import datetime

from injector import singleton


@singleton
class AppSettings:
    app_name = os.environ.get("APP_NAME", "husky-musher")
    flask_env = os.environ.get("FLASK_ENV")
    version = os.environ.get("APP_VERSION")
    deployment_id = os.environ.get("DEPLOYMENT_ID")
    redcap_api_url = os.environ.get("REDCAP_API_URL")
    redcap_api_token = os.environ.get("REDCAP_API_TOKEN")
    redcap_project_id = os.environ.get("REDCAP_PROJECT_ID")
    redcap_event_id = os.environ.get("REDCAP_EVENT_ID")
    redcap_study_start_date = datetime.strptime(
        os.environ.get("REDCAP_STUDY_START_DATE", "1970-01-01"), "%Y-%m-%d"
    )
    redcap_instrument = os.environ.get("REDCAP_INSTRUMENT")
    saml_acs_path = os.environ.get("SAML_ACS_PATH")
    saml_entity_id = os.environ.get("SAML_ENTITY_ID")
    saml_redirect_port = os.environ.get('SAML_REDIRECT_PORT')
    use_mock_idp = bool(os.environ.get("USE_MOCK_IDP"))

    session_cookie_name = os.environ.get("SESSION_COOKIE_NAME", "edu.uw.musher.session")
    session_lifetime = int(os.environ.get("SESSION_LIFETIME_SECONDS") or 60)
    secret_key = os.environ.get("SECRET_KEY", "NotSecured")

    # If redis_host is defined, it will be used. Otherwise,
    # a mock redis client will be created.
    redis_host = os.environ.get("REDIS_HOST")
    redis_port = os.environ.get("REDIS_PORT", 6379)
    redis_password = os.environ.get("REDIS_PASSWORD")

    @property
    def in_development(self):
        return self.flask_env == "development"
