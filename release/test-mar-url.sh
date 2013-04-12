#!/bin/bash
mar_url="${1}"
mar_required_size="${2}"
# failures              is an exported env variable
# temp_files            is an exported env variable

mar_header_file="$(mktemp -t http_header.XXXXXX)"
# strip out dos line returns from header if they occur
curl --retry 5 --retry-max-time 30 -k -s -I -L "${mar_url}" > "${mar_header_file}" 2>&1
mar_file_curl_exit_code=$?

# check file size matches what was written in update.xml
mar_actual_size="$(sed -e "s/$(printf '\r')//" -n -e 's/^Content-Length: //p' "${mar_header_file}" | tail -1)"
mar_actual_url="$(sed -e "s/$(printf '\r')//" -n -e 's/^Location: //p' "${mar_header_file}" | tail -1)"
[ -n "${mar_actual_url}" ] && mar_url_with_redirects="${mar_url} => ${mar_actual_url}" || mar_url_with_redirects="${mar_url}"

if [ "${mar_actual_size}" == "${mar_required_size}" ]
then
    echo "$(date):  Mar file ${mar_url_with_redirects} available with correct size (${mar_actual_size} bytes)" >&2
elif [ -z "${mar_actual_size}" ]
then
    echo "$(date):  FAILURE: Could not retrieve http header for mar file from ${mar_url}" >&2
    echo "NO_MAR_FILE ${mar_url} ${mar_header_file} ${mar_file_curl_exit_code} ${mar_actual_url}" >> "${failures}"
else
    echo "$(date):  FAILURE: Mar file incorrect size - should be ${mar_required_size} bytes, but is ${mar_actual_size} bytes - ${mar_url_with_redirects}" >&2
    echo "MAR_FILE_WRONG_SIZE ${mar_url} ${mar_required_size} ${mar_actual_size} ${mar_header_file} ${mar_file_curl_exit_code} ${mar_actual_url}" >> "${failures}"
fi

echo "${mar_header_file}" >> "${temp_files}"
