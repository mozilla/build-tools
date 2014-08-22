#!/bin/bash -e

################### TO DO ###################
#
# * Check hg is installed
# * Check hg clone is working (error code 255)
# * Check virtualenv is installed
# * Add an option not to refresh tools repo
# * log reconfig to a file and to console
# * Check connectivity to an arbitrary master and report nicely
# * Summarize failures from manage_masters.py at end of log
# * Option to checkconfig only without update
# * Only update wiki if there really are changes
# * Only reconfig if there really are changes, or if forced
# * Send console output also to a log file
#
#############################################

START_TIME="$(date +%s)"

# Explicitly unset any pre-existing environment variables to avoid variable collision
unset PREPARE_ONLY FORCE_RECONFIG MERGE_TO_PRODUCTION UPDATE_WIKI RECONFIG_DIR WIKI_CREDENTIALS_FILE WIKI_USERNAME WIKI_PASSWORD

# Force python into unbuffered mode, so we get full output, as it happens from the fabric scripts
export PYTHONUNBUFFERED=1

function usage {
    echo
    echo "This script can be used to reconfig interactively, or non-interactively. It will merge"
    echo "buildbotcustom, buildbot-configs, mozharness from default to production(-0.8)."
    echo "It will then reconfig, and afterwards if all was successful, it will also update the"
    echo "wiki page https://wiki.mozilla.org/ReleaseEngineering/Maintenance."
    echo
    echo "Usage: $0 -h"
    echo "Usage: $0 [-f] [-m] [-n] [-p] [-r RECONFIG_DIR] [-t] [-w WIKI_CREDENTIALS_FILE]"
    echo
    echo "    -f:                        Force reconfig, even if no changes merged."
    echo "    -h:                        Display help."
    echo "    -m:                        No merging of default -> production(-0.8) of hg branches."
    echo "    -n:                        No wiki update."
    echo "    -p:                        Prepare only; does not push changes to hg, nor perform"
    echo "                               reconfig, nor update wiki. Useful for validating setup,"
    echo "                               or resolving merge conflicts in advance early rather"
    echo "                               than waiting until real reconfig to resolve conflicts."
    echo "    -r RECONFIG_DIR:           Use directory RECONFIG_DIR for storing temporary files"
    echo "                               (default is /tmp/reconfig). This directory, and any"
    echo "                               necessary parent directories will be created if required."
    echo "    -w WIKI_CREDENTIALS_FILE:  Source WIKI_USERNAME and WIKI_PASSWORD env vars from file"
    echo "                               WIKI_CREDENTIALS_FILE (default is ~/.wikiwriter/config)."
    echo
    echo "EXIT CODES"
    echo "     0        Success"
    echo "     1        Bad command line options specified"
    echo "    64        Could not create directory to store results (RECONFIG_DIR)"
    echo "    65        Wiki credentials file not found"
    echo "    66        Python 2.7 not found in PATH"
    echo "    67        Reconfig aborted by user after incomplete reconfig found"
    echo "    68        Aborted due to incomplete reconfig found but non-interactive session, so"
    echo "              could not ask user how to proceed"
    echo "    69        Error during hg merge (most likely due to merge conflict(s))"
    echo "    70        Theoretically not possible - update_maintenance_wiki.sh tries and fails"
    echo "              to create the RECONFIG_DIR when it detects it does not exist (but should"
    echo "              have already been created by end_to_end_reconfig.sh)"
    echo "    71        Theoretically not possible - no wiki markdown file passed to"
    echo "              update_maintenance_wiki.sh"
    echo "    72        Theoretically not possible - non-existing markdown file passed to"
    echo "              update_maintenance_wiki.sh"
    echo "    73        WIKI_USERNAME not specified in wiki credentials file"
    echo "    74        WIKI_PASSWORD not specified in wiki credentials file"
    echo "    75        Could not retreieve login token from wiki - probably a connectivity issue"
    echo "    76        Wiki user/password not authorized to update wiki page"
    echo "              https://wiki.mozilla.org/ReleaseEngineering/Maintenance"
    echo "    77        Wiki API provided a reason not to supply an edit token for the wiki page,"
    echo "              which is something other than user/password not authorized (which would"
    echo "              result in exit code 76)"
    echo "    78        Wiki API response to request to provide an edit token produced a"
    echo "              non-parsable response"
    echo
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

# writes hg commands to the hg log, and just summarizes command called in main log
function hg_wrapper {
    if [ $1 == 'clone' ]; then
        command=('hg' "${@}" "${RECONFIG_DIR}/${repo}")
    else
        command=('hg' -R "${RECONFIG_DIR}/${repo}" "${@}")
    fi
    command_full="Running:"
    for ((INDEX=0; INDEX<${#command[@]}; INDEX+=1)); do
        command_full="${command_full} '${command[$INDEX]}'"
    done
    echo "  * ${command_full}"
    {
        echo
        echo "$(date): ${command_full}"
        echo
        HG_START="$(date +%s)"
        set +e
        "${command[@]}"
        HG_RETURN_CODE=$?
        set -e
        HG_STOP="$(date +%s)"
        echo
        echo "$(date): Completed ($((HG_STOP - HG_START))s)"
    } >>"${RECONFIG_DIR}/hg-${START_TIME}.log" 2>&1
    return "${HG_RETURN_CODE}"
}

command_called "${@}" | sed '1s/^/  * /;2s/^/    /'

echo "  * Start timestamp: ${START_TIME}"
echo "  * Parsing parameters of $(basename "${0}")..."
# Parse parameters passed to this script
while getopts ":fhmnpr:w:" opt; do
    case "${opt}" in
        f)  FORCE_RECONFIG=1
            ;;
        h)  echo "  * Help option requested"
            usage
            exit 0
            ;;
        m)  MERGE_TO_PRODUCTION=0
            ;;
        n)  UPDATE_WIKI=0
            ;;
        p)  PREPARE_ONLY=1
            ;;
        r)  RECONFIG_DIR="${OPTARG}"
            ;;
        w)  WIKI_CREDENTIALS_FILE="${OPTARG}"
            ;;
        ?)  usage >&2
            exit 1
            ;;
    esac
done

echo "  * Setting defaults for parameters not provided in command line options..."

PREPARE_ONLY="${PREPARE_ONLY:-0}"
FORCE_RECONFIG="${FORCE_RECONFIG:-0}"
MERGE_TO_PRODUCTION="${MERGE_TO_PRODUCTION:-1}"
UPDATE_WIKI="${UPDATE_WIKI:-1}"
RECONFIG_DIR="${RECONFIG_DIR:-/tmp/reconfig}"
WIKI_CREDENTIALS_FILE="${WIKI_CREDENTIALS_FILE:-${HOME}/.wikiwriter/config}"

##### Now check parsed parameters are valid...

echo "  * Validating parameters..."

if [ "${PREPARE_ONLY}" == 0 ]; then
    echo "  * Will be preparing *and performing* reconfig, all being well."
else
    echo "  * Preparing reconfig only; will not enact changes."
fi

if [ ! -d "${RECONFIG_DIR}" ]; then
    echo "  * Storing reconfig output under '${RECONFIG_DIR}'..."
    if ! mkdir -p "${RECONFIG_DIR}"; then
        echo "ERROR: Directory '${RECONFIG_DIR}' could not be created from directory '$(pwd)'." >&2
        exit 64
    fi
else
    echo "  * Reconfig directory '${RECONFIG_DIR}' exists - OK"
fi

# Convert ${RECONFIG_DIR} to an absolute directory, in case it is relative, by stepping into it...
pushd "${RECONFIG_DIR}" >/dev/null
if [ "${RECONFIG_DIR}" != "$(pwd)" ]; then
    echo "  * Reconfig directory absolute path: '$(pwd)'"
fi
RECONFIG_DIR="$(pwd)"
popd >/dev/null

# Only validate wiki credentials if we are updating wiki...
if [ "${UPDATE_WIKI}" == '1' ]; then
    echo "  * Wiki update enabled."
    # To avoid user getting confused about parent directory, tell user the
    # absolute path of the credentials file...
    PARENT_DIR="$(dirname "${WIKI_CREDENTIALS_FILE}")"
    if [ ! -e "${PARENT_DIR}" ]; then
    echo "  * Wiki credentials file parent directory '${PARENT_DIR}' not found; creating..." >&2
        mkdir -p "${PARENT_DIR}"
    fi
    pushd "${PARENT_DIR}" >/dev/null
    ABS_WIKI_CREDENTIALS_FILE="$(pwd)/$(basename "${WIKI_CREDENTIALS_FILE}")"
    popd >/dev/null
    if [ "${WIKI_CREDENTIALS_FILE}" == "${ABS_WIKI_CREDENTIALS_FILE}" ]; then
        echo "  * Wiki credentials file location: '${WIKI_CREDENTIALS_FILE}'"
    else
        echo "  * Wiki credentials file location: '${WIKI_CREDENTIALS_FILE}' (absolute path: '${ABS_WIKI_CREDENTIALS_FILE}')"
    fi
    if [ ! -e "${ABS_WIKI_CREDENTIALS_FILE}" ]; then
        echo "  * Wiki credentials file '${ABS_WIKI_CREDENTIALS_FILE}' not found; creating..." >&2
        {
            echo 'export WIKI_USERNAME="naughtymonkey"'
            echo 'export WIKI_PASSWORD="nobananas"'
        } > "${WIKI_CREDENTIALS_FILE}"
        echo "  * Created credentials file '${ABS_WIKI_CREDENTIALS_FILE}'. Please edit this file, setting appropriate values, then rerun." >&2
        exit 65
    else
        source "${WIKI_CREDENTIALS_FILE}"
    fi
else
    echo "  * Not updating wiki."
fi

# Now step into directory this script is in...
cd "$(dirname "${0}")"

if [ "${UPDATE_WIKI}" == '1' ]; then
    # Now validate wiki credentials by performing a dry run...
    echo "  * Testing login credentials for wiki..."
    ./update_maintenance_wiki.sh -d
fi

# Test python version, and availability of fabric...
echo "  * Checking python version is 2.7..."
if ! python --version 2>&1 | grep -q '^Python 2\.7'; then
    echo "ERROR: Python version 2.7 not found - please make sure python 2.7 is in your PATH." >&2
    exit 66
fi

echo "  * Checking fabric module is available in python environment..."
if ! python -c 'import fabric' >/dev/null 2>&1; then
    echo "  * Fabric module not found"
    if [ ! -e "${RECONFIG_DIR}/fabric-virtual-env" ]; then
        echo "  * Creating virtualenv directory '${RECONFIG_DIR}/fabric-virtual-env' for fabric installation..."
        echo "  * Logging to: '${RECONFIG_DIR}/virtualenv-fabric-installation.log'..."
        virtualenv "${RECONFIG_DIR}/fabric-virtual-env" >"${RECONFIG_DIR}/virtualenv-fabric-installation.log" 2>&1
        source "${RECONFIG_DIR}/fabric-virtual-env/bin/activate"
        echo "  * Installing fabric under '${RECONFIG_DIR}/fabric-virtual-env'..."
        pip install fabric >"${RECONFIG_DIR}/virtualenv-fabric-installation.log" 2>&1
    else
        echo "  * Attempting to use existing fabric installation found in '${RECONFIG_DIR}/fabric-virtual-env'"
        source "${RECONFIG_DIR}/fabric-virtual-env/bin/activate"
    fi
fi

echo "  * Re-checking if fabric module is now available in python environment..."
if ! python -c 'import fabric' >/dev/null 2>&1; then
    echo "  * Could not successfully install fabric into python environemnt." >&2
else
    echo "  * Fabric installed successfully into python environment"
fi

# Check if a previous reconfig did not complete
if [ -f "${RECONFIG_DIR}/pending_changes" ]; then
    echo "  * It looks like a previous reconfig did not complete"
    echo "  * Checking if 'standard in' is connected to a terminal..."
    if [ -t 0 ]; then
        # 'standard in' is connected to a terminal, can ask user a question!
        echo "  * Please select one of the following options:"
        echo "        1) Continue with existing reconfig (e.g. if you have resolved a merge conflict)"
        echo "        2) Delete saved state for existing reconfig, and start from fresh"
        echo "        3) Abort and exit reconfig process"
        choice=''
        while [ "${choice}" != 1 ] && [ "${choice}" != 2 ] && [ "${choice}" != 3 ]; do
            echo -n "    Your choice: "
            read choice
        done
        case "${choice}" in
            1) echo "  * Continuing with stalled reconfig..."
               ;;
            2) echo "  * Cleaning out previous reconfig from '${RECONFIG_DIR}'..."
               rm -rf "${RECONFIG_DIR}"/{buildbot-configs,buildbotcustom,pending_changes,mozharness,reconfig_update_for_maintenance.wiki}
               ;;
            3) echo "  * Aborting reconfig..."
               exit 67
               ;;
        esac
    else
        # 'standard in' not connected to a terminal, assume no user connected...
        echo "  * Non-interactive shell detected, cannot ask whether to continue or not, therefore aborting..."
        exit 68
    fi
fi

### If we get this far, all our preflight checks have passed, so now on to business...
echo "  * All preflight checks passed in '$(basename "${0}")'."

# Merges mozharness, buildbot-configs from default -> production.
# Merges buildbostcustom from default -> production-0.8.
# Returns 0 if something got merged, otherwise returns 1.
function merge_to_production {
    [ "${MERGE_TO_PRODUCTION}" == 0 ] && return 0
    echo "  * hg log for this session: '${RECONFIG_DIR}/hg-${START_TIME}.log'"
    for repo in mozharness buildbot-configs buildbotcustom; do
        if [ -d "${RECONFIG_DIR}/${repo}" ]; then
            echo "  * Existing hg clone of ${repo} found: '${RECONFIG_DIR}/${repo}' - pulling for updates."
            hg_wrapper pull
        else
            echo "  * Cloning ssh://hg.mozilla.org/build/${repo} into '${RECONFIG_DIR}/${repo}'..."
            hg_wrapper clone "ssh://hg.mozilla.org/build/${repo}"
        fi
        if [ "${repo}" == 'buildbotcustom' ]; then
            branch='production-0.8'
        else
            branch='production'
        fi
        hg_wrapper up -r "${branch}"
        echo "  * Finding ${repo} changesets that would get merged from default to ${branch}..."
        {
            echo "Merging from default"
            echo
            hg -R "${RECONFIG_DIR}/${repo}" merge -P default
        } > "${RECONFIG_DIR}/${repo}_preview_changes.txt" 2>/dev/null
        # Merging can fail if there are no changes between default and "${branch}"
        set +e
        hg_wrapper merge default
        RETVAL="${?}"
        set -e
        if [ "${RETVAL}" == '255' ]; then
            echo "  * No new changes found in ${repo}"
        elif [ "${RETVAL}" != '0' ]; then
            echo "ERROR: An error occurred during hg merge (exit code was ${RETVAL}). Please resolve conflicts/issues in '${RECONFIG_DIR}/${repo}',"
            echo "       push to ${branch} branch, and run this script again." >&2
            exit 69
        else
            echo "  * Merge resulted in change"
        fi
        # Still commit and push, even if no new changes, since a merge conflict might have been resolved
        hg_wrapper commit -l "${RECONFIG_DIR}/${repo}_preview_changes.txt"
        if [ "${PREPARE_ONLY}" == '0' ]; then
            echo "  * Pushing '${RECONFIG_DIR}/${repo}' ${branch} branch to ssh://hg.mozilla.org/build/${repo}..."
            hg_wrapper push
        fi
        echo "${repo}" >> "${RECONFIG_DIR}/pending_changes"
    done
    grep summary "${RECONFIG_DIR}"/*_preview_changes.txt | \
        awk '{sub (/ r=.*$/,"");print substr($0, index($0,$2))}' | \
        sed 's/[Bb]ug \([0-9]*\):* *-* */\* {{bug|\1}} - /' | \
        sed 's/^[ \t]*//;s/[ \t,;]*$//' | \
        sed 's/^\([^\*]\)/\* \1/' | \
        sort -u >> "${RECONFIG_DIR}/reconfig_update_for_maintenance.wiki"
    [ -f "${RECONFIG_DIR}/pending_changes" ] && return 0 || return 1
}

# Return code of merge_to_production is 0 if merge performed successfully and changes made
if merge_to_production || [ "${FORCE_RECONFIG}" == '1' ]; then
    production_masters_url='http://hg.mozilla.org/build/tools/raw-file/tip/buildfarm/maintenance/production-masters.json'
    if [ "${PREPARE_ONLY}" == '1' ]; then
        echo "  * Preparing reconfig only; not running: '$(pwd)/manage_masters.py' -f '${production_masters_url}' -j16 -R scheduler -R build -R try -R tests show_revisions update"
        echo "  * Preparing reconfig only; not running: '$(pwd)/manage_masters.py' -f '${production_masters_url}' -j32 -R scheduler -R build -R try -R tests checkconfig reconfig"
        echo "  * Preparing reconfig only; not running: '$(pwd)/manage_masters.py' -f '${production_masters_url}' -j16 -R scheduler -R build -R try -R tests show_revisions"
    else
        # Split into two steps so -j option can be varied between them
        echo "  * Running: '$(pwd)/manage_masters.py' -f '${production_masters_url}' -j16 -R scheduler -R build -R try -R tests show_revisions update"
        ./manage_masters.py -f "${production_masters_url}" -j16 -R scheduler -R build -R try -R tests show_revisions update >>"${RECONFIG_DIR}/manage_masters-${START_TIME}.log" 2>&1
        echo "  * Running: '$(pwd)/manage_masters.py' -f '${production_masters_url}' -j32 -R scheduler -R build -R try -R tests checkconfig reconfig"
        ./manage_masters.py -f "${production_masters_url}" -j32 -R scheduler -R build -R try -R tests checkconfig reconfig >>"${RECONFIG_DIR}/manage_masters-${START_TIME}.log" 2>&1
        # delete this now, since changes have been deployed
        [ -f "${RECONFIG_DIR}/pending_changes" ] && mv "${RECONFIG_DIR}/pending_changes" "${RECONFIG_DIR}/pending_changes_${START_TIME}"
        echo "  * Running: '$(pwd)/manage_masters.py' -f '${production_masters_url}' -j16 -R scheduler -R build -R try -R tests show_revisions"
        ./manage_masters.py -f "${production_masters_url}" -j16 -R scheduler -R build -R try -R tests show_revisions >>"${RECONFIG_DIR}/manage_masters-${START_TIME}.log" 2>&1
    fi
fi

if [ "${UPDATE_WIKI}" == "1" ]; then
    if [ "${PREPARE_ONLY}" == '1' ]; then
        ./update_maintenance_wiki.sh -d -r "${RECONFIG_DIR}" -w "${RECONFIG_DIR}/reconfig_update_for_maintenance.wiki"
    else
        ./update_maintenance_wiki.sh -r "${RECONFIG_DIR}" -w "${RECONFIG_DIR}/reconfig_update_for_maintenance.wiki"
        for file in "${RECONFIG_DIR}"/*_preview_changes.txt
        do
            mv "${file}" "$(echo "${file}" | sed "s/\\.txt\$/_${START_TIME}&/")"
        done 2>/dev/null || true
    fi
fi

echo "  * Summary of changes:"
cat "${RECONFIG_DIR}/reconfig_update_for_maintenance.wiki" | sed 's/^/        /'
echo "  * Reconfig of masters completed."

# Manage foopies after everything else.
# No easy way to see if there are changes to the tools repo since there is no production branch
# and we do not tag it - so aside from running show_revision and then checking if every version
# is already on the latest commit, we should probably just run it regardless
devices_json_url='http://hg.mozilla.org/build/tools/raw-file/tip/buildfarm/mobile/devices.json'
if [ "${PREPARE_ONLY}" == '1' ]; then
    echo "  * Preparing foopy update only; not running: '$(pwd)/manage_foopies.py' -f '${devices_json_url}' -j16 -H all show_revision update"
    echo "  * Preparing foopy update only; not running: '$(pwd)/manage_foopies.py' -f '${devices_json_url}' -j16 -H all show_revision"
else
    echo "  * Running: '$(pwd)/manage_foopies.py' -f '${devices_json_url}' -j16 -H all show_revision update"
    ./manage_foopies.py -f "${devices_json_url}" -j16 -H all show_revision update >>"${RECONFIG_DIR}/manage_foopies-${START_TIME}.log" 2>&1
    echo "  * Running: '$(pwd)/manage_foopies.py' -f '${devices_json_url}' -j16 -H all show_revision"
    ./manage_foopies.py -f "${devices_json_url}" -j16 -H all show_revision >>"${RECONFIG_DIR}/manage_foopies-${START_TIME}.log" 2>&1
fi
echo "  * Foopies updated. Directory '${RECONFIG_DIR}' contains artefacts from reconfig process."

STOP_TIME="$(date +%s)"
echo "  * Finish timestamp: ${STOP_TIME}"
echo "  * Time taken: $((STOP_TIME - START_TIME))s"
