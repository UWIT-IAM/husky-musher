# Application Operations

## Self-service non-developer operations

### Add a user as an administrator

**Only members of the UW-IT IAM team can do this**.

- Go to the [UW Groups Service](https://groups.uw.edu)
- Find the 'uw_iam_musher-admins' group (link intentionally omitted)
- Add the required netid to the group

### Delete a survey participant from the Musher cache

**Only [admins](#add-a-user-as-an-administrator) may do this**.

- Go to the `/admin` endpoint of the application
- Enter the user's UW NetID under "Delete Cache Entry"
- Click on `Expire cache entry`

The update is immediate. The user's data will be refreshed when they next visit the app.
The message will show as a success even if the user was not found in the cache.

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
