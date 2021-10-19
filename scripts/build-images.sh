#!/usr/bin/env bash
set -e

DOCKER_REPO="ghcr.io/uwit-iam/husky-musher"
APP_VERSION=
APP_DI_URI=
DEPLOYMENT_STAGE=local
ENV_FILE=local.env

function print_help {
   cat <<EOF
   Use: build-images.sh [OPTIONS]
   Options:
   -v, --version   Set a version for your build

   --run           Run the application locally, using the --env-file
   --env-file      Set a dotenv file to use when running the app locally;
                   has no effect unless '--run' is specified. Default: ${ENV_FILE}


   --deploy        Deploy the script after building; not compatible with --run.
                   See docs/operations for more information about deployed instances.

   --test          Will run tests for the built app image; can be used with --deploy
                   and --run; in both cases, the script will fail before
                   deploying/running if tests fail.

   --deployment-stage   Set this to target a specific stage (e.g., dev, eval, prod)
                        when building your deployment image. Defaults to
                        "$DEPLOYMENT_STAGE".

   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

while (( $# ))
do
  case $1 in
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      set -x
      ;;
    --version|-v)
      shift
      APP_VERSION=$1
      ;;
    --deploy)
      DEPLOY=1
      ;;
    --deployment-stage)
      shift
      DEPLOYMENT_STAGE="$1"
      ;;
    --run)
      RUN_DEPLOYMENT_IMAGE=1
      ;;
    --test)
      RUN_TESTS=1
      ;;
    --env-file)
      shift
      ENV_FILE=$1
      if ! [[ -f "${ENV_FILE}" ]]
      then
        echo "No such --env-file: $ENV_FILE"
        exit 1
      fi
      ;;
    *)
      echo "Invalid Option: $1"
      print_help
      exit 1
      ;;
  esac
  shift
done

./scripts/install-build-scripts.sh > /dev/null
source ./.build-scripts/sources/fingerprints.sh
source ./.build-scripts/sources/bash-helpers.sh

function get_dependencies_fingerprint {
  echo "$(calculate_paths_fingerprint Dockerfile pyproject.toml poetry.lock)"
}

function get_app_version {
  echo "${APP_VERSION}"
}

function get_deployment_image_uri {
  echo "${DEPLOYMENT_IMAGE_URI}"
}

function get_dependency_image_uri {
  echo "${APP_DI_URI}"
}

function pull_or_build_dependency_image {
  ./.build-scripts/scripts/pull-or-build-image.sh \
    -i "$(get_dependency_image_uri)" \
    -d Dockerfile \
    -- --target dependencies
}

function build_app_image {
  docker build --target app \
    -t "${DOCKER_REPO}:$(get_app_version)" \
    --build-arg APP_SOURCE="$(get_dependency_image_uri)" \
    --build-arg APP_VERSION=$(get_app_version) .
}

function build_deployment_image {
  docker build --target deployment -t "$(get_deployment_image_uri)" \
    --build-arg DEPLOYMENT_SOURCE="${DOCKER_REPO}:$(get_app_version)" \
    --build-arg DEPLOYMENT_ID=$(get_deployment_image_uri) .
}


APP_DI_URI="${DOCKER_REPO}-deps:$(get_dependencies_fingerprint)"

pull_or_build_dependency_image

if [[ -z "${APP_VERSION}" ]]
then
  APP_VERSION=$(docker run $(get_dependency_image_uri) poetry version -s)
fi
DEPLOYMENT_IMAGE_URI="${DOCKER_REPO}:deploy-${DEPLOYMENT_STAGE}.$(tag_timestamp).v$(get_app_version)"

build_app_image
build_deployment_image

if [[ -n "${RUN_TESTS}" ]]
then
  deployment=$(get_deployment_image_uri)
  docker build -f tests.Dockerfile \
    --build-arg APP_SOURCE=${deployment} \
    -t "${DOCKER_REPO}-tests" .
  set -e
  docker run "${DOCKER_REPO}-tests"
  set +e
fi

if [[ -n "${RUN_DEPLOYMENT_IMAGE}" ]]
then
  deployment=$(get_deployment_image_uri)
  MOUNT="--mount type=bind,source=$(pwd)/husky_musher,target=/musher/husky_musher"
  docker run \
    $MOUNT \
    $(test ! -f "$ENV_FILE" || echo "--env-file ${ENV_FILE}") \
    -it -p 8000:8000 -p 6379:6379 "${deployment}"
fi

if [[ -n "${DEPLOY}" ]]
then
  docker push $(get_deployment_image_uri)
fi
