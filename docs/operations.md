# Application Operations

## Manage dependencies

### Patch dependencies

To update to the latest versions within allowed guidance, use `poetry lock`; this 
will update the `poetry.lock` file; you should test, commit, and create a pull 
request for this update.

### Add a new dependency

`poetry add <package-name>=<version>`

If you don't know what version to pick, just use `poetry add <package-name>`.

Unless you know there a reason to pin a specific version of a dependency,
it is recommended to pin only the major (`x`) and minor (`y`) versions of dependencies.
If you are currently using version `1.2.3` of something, add version `^1.2` as a 
dependency, so that you automatically pick up patches on future builds.

You then also need to run `poetry install` if you want the dependency to install to 
your local system.

### Upgrade or re-pin a dependency

You can edit [pyproject.toml](../pyproject.toml) 
to change the version guidance for dependencies.

## Run Tests

`./scripts/build-images.sh --test` will build a test image and run all tests for you.

Otherwise, you can install all dependencies using poetry, and then run `pytest`.

## Deploy this app

### Manually

You can manually deploy by running 

`./scripts/build-images.sh --deployment-stage dev --deploy`

You should combine this with tests:

`./scripts/build-images.sh --test --deploy --deployment-stage dev`

To push to the Github docker registry, you must
have a Personal Access Token with the correct scopes, and permissions to push.

See [Github's official documentation on working with packages.](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry)

### Using Github

Coming soon . . . 

## View logs

Logs are available to those who have an Operator role with the UW-IT IAM kubernetes 
clusters. Go to https://uwiam.page.link/dev-musher-logs (replace `dev` with `eval` or 
`prod` as needed`).

## Manage deployed environment variables and secrets

Coming soon . . . 
