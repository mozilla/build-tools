#!/bin/bash
mar_url="${1}"
mar_required_size="${2}"

mar_headers_file="$(mktemp -t mar_headers.XXXXXXXXXX)"
curl --retry 50 --retry-max-time 300 -k -s -I -L "${mar_url}" > "${mar_headers_file}" 2>&1
mar_file_curl_exit_code=$?

# check file size matches what was written in update.xml
# strip out dos line returns from header if they occur
mar_actual_size="$(sed -e "s/$(printf '\r')//" -n -e 's/^Content-Length: //p' "${mar_headers_file}" | tail -1)"
mar_actual_url="$(sed -e "s/$(printf '\r')//" -n -e 's/^Location: //p' "${mar_headers_file}" | tail -1)"
[ -n "${mar_actual_url}" ] && mar_url_with_redirects="${mar_url} => ${mar_actual_url}" || mar_url_with_redirects="${mar_url}"

if [ "${mar_actual_size}" == "${mar_required_size}" ]
then
    echo "$(date):  Mar file ${mar_url_with_redirects} available with correct size (${mar_actual_size} bytes)" > "$(mktemp -t log.XXXXXXXXXX)"
elif [ -z "${mar_actual_size}" ]
then
    echo "$(date):  FAILURE: Could not retrieve http header for mar file from ${mar_url}" > "$(mktemp -t log.XXXXXXXXXX)"
    echo "NO_MAR_FILE ${mar_url} ${mar_headers_file} ${mar_file_curl_exit_code} ${mar_actual_url}" > "$(mktemp -t failure.XXXXXXXXXX)"
else
    echo "$(date):  FAILURE: Mar file incorrect size - should be ${mar_required_size} bytes, but is ${mar_actual_size} bytes - ${mar_url_with_redirects}" > "$(mktemp -t log.XXXXXXXXXX)"
    echo "MAR_FILE_WRONG_SIZE ${mar_url} ${mar_required_size} ${mar_actual_size} ${mar_headers_file} ${mar_file_curl_exit_code} ${mar_actual_url}" > "$(mktemp -t failure.XXXXXXXXXX)"
fi
