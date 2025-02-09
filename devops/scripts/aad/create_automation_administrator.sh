#!/bin/bash
set -euo pipefail
# Use this for debug only
# set -o xtrace
# AZURE_CORE_OUTPUT=jsonc # force CLI output to JSON for the script (user can still change default for interactive usage in the dev container)

function show_usage()
{
    cat << USAGE

Utility script for creating an automation administrator for TRE. This is optional and is used when you
want to run the E2E tests locally or automatically register bundles in the TRE.
You must be logged in using Azure CLI with sufficient privileges to modify Azure Active Directory to run this script.

Usage: $0 --name "mytre" [--admin-consent]

Options:
    -n,--name                   Required. The prefix for the app (registration) names e.g., "TRE".

USAGE
    exit 1
}

if ! command -v az &> /dev/null; then
    echo "This script requires Azure CLI" 1>&2
    exit 1
fi

# Get the directory that this script is in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

declare currentUserId=""
declare msGraphUri="https://graph.microsoft.com/v1.0"
declare appName=""

# Initialize parameters specified from command line
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--name)
            appName=$2
            shift 2
        ;;
        *)
            echo "Invalid option: $1."
            show_usage
            exit 2
        ;;
    esac
done

###################################
# CHECK INCOMMING PARAMETERS      #
###################################
if [[ $(az account list --only-show-errors -o json | jq 'length') -eq 0 ]]; then
    echo "Please run az login -t <tenant> --allow-no-subscriptions"
    exit 1
fi

if [[ -z "$appName" ]]; then
    echo "Please specify the application name" 1>&2
    show_usage
fi
appName="$appName Automation Admin"
currentUserId=$(az ad signed-in-user show --query 'objectId' --output tsv --only-show-errors)
tenant=$(az rest -m get -u "${msGraphUri}/domains" -o json | jq -r '.value[] | select(.isDefault == true) | .id')

echo -e "\e[96mCreating the Automation Admin in the \"${tenant}\" Azure AD tenant.\e[0m"

# Load in helper functions
# shellcheck disable=SC1091
source "${DIR}/get_existing_app.sh"
# shellcheck disable=SC1091
source "${DIR}/wait_for_new_app_registration.sh"
# shellcheck disable=SC1091
source "${DIR}/create_or_update_service_principal.sh"

# Get an existing object if it's been created before.
appObjectId=""
appId=""
existingApp=$(get_existing_app --name "${appName}") || null
if [ -n "${existingApp}" ]; then
    appObjectId=$(echo "${existingApp}" | jq -r '.objectId')
    appId=$(echo "${existingApp}" | jq -r .appId)
fi

automationApp=$(jq -c . << JSON
{
    "displayName": "${appName}",
    "api": {
        "requestedAccessTokenVersion": 2
    },
    "signInAudience": "AzureADMyOrg"
}
JSON
)

# Is the app already registered?
if [[ -n ${appObjectId} ]]; then
  echo "\"${appName}\" already exists. Skipping creation."
else
    echo "\"${appName}\" doesn't exist - creating..."
    appId=$(az rest --method POST --uri "${msGraphUri}/applications" --headers Content-Type=application/json --body "${automationApp}" --output tsv --query "appId")

    # Poll until the app registration is found in the listing.
    wait_for_new_app_registration "${appId}"
fi

# Make the current user an owner of the application.
az ad app owner add --id "${appId}" --owner-object-id "$currentUserId" --only-show-errors

# Create a Service Principal for the app.
spPassword=$(create_or_update_service_principal "${appId}" "${appName}")

echo -e "\n\e[96mAAD_TENANT_ID=\"$(az account show --output json | jq -r '.tenantId')\""
echo -e "** Please copy the following variables to /templates/core/.env **"
echo -e "\n\e[33mTEST_ACCOUNT_CLIENT_ID=\"${appId}\""
echo -e "TEST_ACCOUNT_CLIENT_SECRET=\"${spPassword}\"\e[0m"