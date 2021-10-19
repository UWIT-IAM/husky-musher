# Configuration

This app is configured through environment variables, which are consumed
by [settings.py](../husky_musher/settings.py).

When running from your laptop, it is easiest to create a file `local.env` to store
environment variables for you run; this will automatically be used by
`./scripts/build-images.sh`, although you can optionall provide the `--env-file` 
argument to specify some other file to use.

Configuring a deployed instance requires heightened privileges. Most values are 
stored as Kubernetes External Secrets in the UW-IT IAM clusters stored in the UW-IT 
Hashicorp Mosler Vault. All values can be overridden by updating the deployment.yml in
the [gcp-k8](https://github.com/uwit-mci-iam/gcp-k8) repository (only visible to those 
with requisite permissions).

In short: if you need to update deployed instances, please reach out to someone in 
the uw_iam group, probably [tomthorogood](https://www.github.com/tomthorogood).


## Environment Variables

The below template includes all usable environment variables; 
any time [settings.py](../husky_musher/settings.py) is updated, please
remember to keep this up to date also.

If this is your first time maintaining this application,
copy this into a `local.env` file. Git will ignore the file
so that it won't be committed.

```
# The API token you want to use to connect to REDCap
REDCAP_API_TOKEN=<PROVIDE YOUR OWN>

# The REDCap API URL
REDCAP_API_URL=https://redcap.iths.org/api/

# The project information for the project you are connecting to
REDCAP_PROJECT_ID=43642  # Test project
REDCAP_EVENT_ID=9        # musher_test_event_arm_1
REDCAP_STUDY_START_DATE=2021-10-12
REDCAP_INSTRUMENT=test_form

# Some basic flask options; you probably don't need to change these
FLASK_ENV=development
FLASK_APP=husky_musher.app
FLASK_RUN_PORT=8000

# SAML Settings; you are not likely to need to change these.
USE_MOCK_IDP=1
SAML_ENTITY_ID=https://musher.iamdev.s.uw.edu/saml
SAML_REDIRECT_PORT=:8000
# When running locally, this group must be in IDP_ATTR_groups
# in order to view the admin endpoint.
APP_ADMIN_GROUPS=["uw_iam_musher-admins"]

# Uncomment the next REDIS_HOST line
# to connect to a locally running redis client
# when the app is running in a docker container
#REDIS_HOST=host.docker.internal

# Uncomment the next REDIS_HOST line
# to connect to a locally running redis client
# when the app is also running locally
# REDIS_HOST=127.0.0.1

# You can configure your local redis instance with the redis command:
#   ACL SETUSER husky-musher +@all -@dangerous ~husky-musher:* >hello
REDIS_PASSWORD=hello

# SAML Attributes
# You can set any attribute by prefixing it with `IDP_ATTR_`, 
# when FLASK_ENV=development. Entries that begin with '{' or '[' 
# will be parsed as JSON.
IDP_ATTR_uwnetid=jjjschmidt  # Not a real netid; too long
IDP_ATTR_email=jjjschmidt@uw.edu 
IDP_ATTR_registeredGivenName="John Jacob"
IDP_ATTR_registeredSurname="Jingleheimer-Schmidt"
IDP_ATTR_homeDept="UW-IT"
IDP_ATTR_affiliations=["member","staff"]
IDP_ATTR_groups=["uw_iam_musher-admins"]
