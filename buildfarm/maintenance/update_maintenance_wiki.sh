#!/bin/bash -e

# Explicitly unset any pre-existing environment variables to avoid variable collision
unset DRY_RUN DEBUG_DIR
WIKI_TEXT_ADDITIONS_FILE=""

function usage {
    echo "Usage: $0 -h"
    echo "Usage: $0 [-r RECONFIG_DIR ] -d [-w WIKI_TEXT_ADDITIONS_FILE]"
    echo "Usage: $0 [-r RECONFIG_DIR ] -w WIKI_TEXT_ADDITIONS_FILE"
    echo
    echo "    -d:                           Dry run; will not make changes, only validates login."
    echo "    -h:                           Display help."
    echo "    -r DEBUG_DIR:                 Copy temporary generated files into directory DEBUG_DIR"
    echo "    -w WIKI_TEXT_ADDITIONS_FILE:  File containing wiki markdown to insert into wiki page."
}

# Simple function to output the name of this script and the options that were passed to it
function command_called {
    echo -n "Command called:"
    for ((INDEX=0; INDEX<=$#; INDEX+=1))
    do
        echo -n " '${!INDEX}'"
    done
    echo ''
    echo "From directory: '$(pwd)'"
}

command_called "${@}" | sed '1s/^/  * /;2s/^/    /'

echo "  * Parsing parameters of $(basename "${0}")..."
# Parse parameters passed to this script
while getopts ":dhr:w:" opt; do
    case "${opt}" in
        d)  DRY_RUN=1
            ;;
        h)  usage
            exit 0
            ;;
        r)  DEBUG_DIR="${OPTARG}"
            ;;
        w)  WIKI_TEXT_ADDITIONS_FILE="${OPTARG}"
            ;;
        ?)  usage >&2
            exit 1
            ;;
    esac
done

DRY_RUN="${DRY_RUN:-0}"
DEBUG_DIR="${DEBUG_DIR:-}"

if [ -n "${DEBUG_DIR}" ]; then
    if [ ! -d "${DEBUG_DIR}" ]; then
        echo "  * Creating directory '${DEBUG_DIR}'..."
        if ! mkdir -p "${DEBUG_DIR}"; then
            echo "ERROR: Directory '${DEBUG_DIR}' could not be created from directory '$(pwd)'." >&2
            exit 70
        fi
    else
        echo "  * Debug directory '${DEBUG_DIR}' exists - OK"
    fi
else
    echo "  * Not storing temporary files (DEBUG_DIR has not been specified)"
fi

# if doing a dry run, not *necessary* to specify a wiki text file, but optional, so if specified, use it
if [ "${DRY_RUN}" == 0 ] || [ -n "${WIKI_TEXT_ADDITIONS_FILE}" ]; then
    if [ -z "${WIKI_TEXT_ADDITIONS_FILE}" ]; then
        echo "ERROR: Must provide a file containing additional wiki text to embed, e.g. '${0}' -w 'reconfig-bugs.wikitext'" >&2
        echo "Exiting..." >&2
        exit 71
    fi
    if [ ! -f "${WIKI_TEXT_ADDITIONS_FILE}" ]; then
        echo "ERROR: File '${WIKI_TEXT_ADDITIONS_FILE}' not found. Working directory is '$(pwd)'." >&2
        echo "This file should contain additional wiki content to be inserted in https://wiki.mozilla.org/ReleaseEngineering/Maintenance." >&2
        echo "Exiting..." >&2
        exit 72
    fi
fi

if [ -z "${WIKI_USERNAME}" ]; then
    echo "ERROR: Environment variable WIKI_USERNAME must be set for publishing wiki page to https://wiki.mozilla.org/ReleaseEngineering/Maintenance" >&2
    echo "Exiting..." >&2
    exit 73
else
    echo "  * Environment variable WIKI_USERNAME defined ('${WIKI_USERNAME}')"
fi

if [ -z "${WIKI_PASSWORD}" ]; then
    echo "ERROR: Environment variable WIKI_PASSWORD must be set for publishing wiki page to https://wiki.mozilla.org/ReleaseEngineering/Maintenance" >&2
    echo "Exiting..." >&2
    exit 74
else
    echo "  * Environment variable WIKI_PASSWORD defined"
fi

# create some temporary files
current_content="$(mktemp -t current-content.XXXXXXXXXX)"
new_content="$(mktemp -t new-content.XXXXXXXXXX)"
cookie_jar="$(mktemp -t cookie-jar.XXXXXXXXXX)"

echo "  * Retrieving current wiki text of https://wiki.mozilla.org/ReleaseEngineering/Maintenance..."
curl -s 'https://wiki.mozilla.org/ReleaseEngineering/Maintenance&action=raw' >> "${current_content}"

# find first "| in production" line in the current content, and grab line number
old_line="$(sed -n '/^| in production$/=' "${current_content}" | head -1)"

echo "  * Preparing wiki page to include new content..."
# create new version of whole page, and put in "${new_content}" file...
{
    # old content, up to 2 lines before the first "| in production" line
    sed -n 1,$((old_line-2))p "${current_content}"
    # the new content to add
    if [ -r "${WIKI_TEXT_ADDITIONS_FILE}" ]; then
        echo '|-'
        echo '| in production'
        echo "| `TZ=America/Los_Angeles date +"%Y-%m-%d %H:%M PT"`"
        echo '|'
        cat "${WIKI_TEXT_ADDITIONS_FILE}"
    fi
    # the rest of the page (starting from line before "| in production"
    sed -n $((old_line-1)),\$p "${current_content}"
} > "${new_content}"

# login, store cookies in "${cookie_jar}" temporary file, and get login token...
echo "  * Logging in to wiki and getting login token and session cookie..."
json="$(curl -s -c "${cookie_jar}" -d action=login -d lgname="${WIKI_USERNAME}" -d lgpassword="${WIKI_PASSWORD}" -d format=json 'https://wiki.mozilla.org/api.php')"
login_token="$(echo "${json}" | sed -n 's/.*"token":"//p' | sed -n 's/".*//p')"
if [ -z "${login_token}" ]; then
    {
        echo "ERROR: Could not retrieve login token"
        echo "    Ran: curl -s -c '${cookie_jar}' -d action=login -d lgname='${WIKI_USERNAME}' -d lgpassword=********* -d format=json 'https://wiki.mozilla.org/api.php'"
        echo "    Output retrieved:"
        echo "${json}" | sed 's/^/        /'
    } >&2
    exit 75
 fi
echo "  * Login token retrieved: '${login_token}'"
# login again, using login token received (see https://www.mediawiki.org/wiki/API:Login)
echo "  * Logging in again, and passing login token just received..."
curl -s -b "${cookie_jar}" -d action=login -d lgname="${WIKI_USERNAME}" -d lgpassword="${WIKI_PASSWORD}" -d lgtoken="${login_token}" 'https://wiki.mozilla.org/api.php' 2>&1 > /dev/null
# get an edit token, remembering to pass previous cookies (see https://www.mediawiki.org/wiki/API:Edit)
echo "  * Retrieving an edit token for making wiki changes..."
edit_token_page="$(curl -b "${cookie_jar}" -s -d action=query -d prop=info -d intoken=edit -d titles=ReleaseEngineering/Maintenance 'https://wiki.mozilla.org/api.php')"
edit_token="$(echo "${edit_token_page}" | sed -n 's/.*edittoken=&quot;//p' | sed -n 's/&quot;.*//p')"
if [ -z "${edit_token}" ]; then
    error_received="$(echo "${edit_token_page}" | sed -n 's/.*&lt;info xml:space=&quot;preserve&quot;&gt;<\/span>\(.*\)<span style="color:blue;">&lt;\/info&gt;<\/span>.*/\1/p')"
    if [ "${error_received}" == "Action 'edit' is not allowed for the current user" ]; then
        {
            echo "ERROR: Either user '${WIKI_USERNAME}' is not authorized to publish changes to the wiki page https://wiki.mozilla.org/ReleaseEngineering/Maintenance,"
            echo "    or the wrong password has been specified for this user (not dispaying password here for security reasons)."
        }
        exit 76
    elif [ -n "${error_received}" ]; then
        {
            echo "ERROR: Problem getting an edit token for updating wiki: ${error_received}"
        } >&2
        exit 77
    else
        {
            echo "ERROR: Could not retrieve edit token"
            echo "    Ran: curl -b '${cookie_jar}' -s -d action=query -d prop=info -d intoken=edit -d titles=ReleaseEngineering/Maintenance 'https://wiki.mozilla.org/api.php'"
            echo "    Output retrieved:"
            echo "${edit_token_page}" | sed 's/^/        /'
        } >&2
        exit 78
    fi
 fi
echo "  * Edit token retrieved: '${edit_token}'"
# now post new content...
EXIT_CODE=0
if [ "${DRY_RUN}" == 0 ]; then
    publish_log="$(mktemp -t publish-log.XXXXXXXXXX)"
    echo "  * Publishing updated maintenance page to https://wiki.mozilla.org/ReleaseEngineering/Maintenance..."
    curl -s -b "${cookie_jar}" -H 'Content-Type:application/x-www-form-urlencoded' -d action=edit -d title='ReleaseEngineering/Maintenance' -d 'summary=reconfig' -d "text=$(cat "${new_content}")" --data-urlencode token="${edit_token}" 'https://wiki.mozilla.org/api.php' 2>&1 > "${publish_log}"
    echo "  * Checking whether publish was successful..."
    if grep -q Success "${publish_log}"; then
        echo "  * Maintenance wiki updated successfully."
    else
        echo "ERROR: Failed to update wiki page https://wiki.mozilla.org/ReleaseEngineering/Maintenance." >&2
        EXIT_CODE=68
    fi
    [ -n "${DEBUG_DIR}" ] && cp "${publish_log}" "${DEBUG_DIR}/publish.log"
    rm "${publish_log}"
else
    echo "  * Not publishing changes to https://wiki.mozilla.org/ReleaseEngineering/Maintenance since this is a dry run..."
fi
# Be kind and logout.
echo "  * Logging out of wiki"
curl -s -b "${cookie_jar}" -d action=logout 'https://wiki.mozilla.org/api.php' >/dev/null

if [ -n "${DEBUG_DIR}" ]; then
    echo "  * Backing up temporary files generated during wiki publish before they get deleted..."
    cp "${cookie_jar}"      "${DEBUG_DIR}/cookie_jar.txt"
    cp "${new_content}"     "${DEBUG_DIR}/new_wiki_content.txt"
    cp "${current_content}" "${DEBUG_DIR}/old_wiki_content.log"
fi

# remove temporary files
echo "  * Deleting temporary files..."
rm "${cookie_jar}"
rm "${new_content}"
rm "${current_content}"

exit "${EXIT_CODE}"
