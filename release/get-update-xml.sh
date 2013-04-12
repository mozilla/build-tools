#!/bin/bash

update_xml_url="${1}"
patch_types="${2}"
# failures              is an exported env variable
# update_xml_to_mar     is an exported env variable
# temp_files            is an exported env variable
update_xml="$(mktemp -t update.xml.XXXXXX)"
update_xml_headers="$(mktemp -t update.xml.headers.XXXXXX)"
curl --retry 5 --retry-max-time 30 -k -s -D "${update_xml_headers}" -L "${update_xml_url}" > "${update_xml}"
update_xml_curl_exit_code=$?
if [ "${update_xml_curl_exit_code}" == 0 ]
then
    update_xml_actual_url="$(sed -e "s/$(printf '\r')//" -n -e 's/^Location: //p' "${update_xml_headers}" | tail -1)"
    [ -n "${update_xml_actual_url}" ] && update_xml_url_with_redirects="${update_xml_url} => ${update_xml_actual_url}" || update_xml_url_with_redirects="${update_xml_url}"
    echo "$(date):  Downloaded update.xml file from ${update_xml_url_with_redirects}" >&2
    for patch_type in ${patch_types//,/ }
    do  
        mar_url_and_size="$(sed -e 's/\&amp;/\&/g' -n -e 's/.*<patch .*type="'"${patch_type}"'".* URL="\([^"]*\)".*size="\([^"]*\)".*/\1 \2/p' "${update_xml}" | tail -1)"
        if [ -z "${mar_url_and_size}" ]
        then
            echo "$(date):  FAILURE: No patch type '${patch_type}' found in update.xml from ${update_xml_url_with_redirects}" >&2
            echo "PATCH_TYPE_MISSING ${update_xml_url} ${patch_type} ${update_xml} ${update_xml_headers} ${update_xml_actual_url}" >> "${failures}"
        else
            echo "${mar_url_and_size}"
            echo "$(date):  Successfully extracted mar url and mar file size for patch type '${patch_type}' from ${update_xml_url_with_redirects}" >&2
            # now log that this update xml and patch combination brought us to this mar url and mar file size
            echo "${update_xml_url} ${patch_type} ${mar_url_and_size} ${update_xml_actual_url}" >> "${update_xml_to_mar}"
        fi
    done
else
    if [ -z "${update_xml_actual_url}" ]
    then
        echo "$(date):  FAILURE: Could not retrieve update.xml from ${update_xml_url} for patch type(s) '${patch_types}'" >&2
        echo "UPDATE_XML_UNAVAILABLE ${update_xml_url} ${update_xml} ${update_xml_headers} ${update_xml_curl_exit_code}" >> "${failures}"
    else
        echo "$(date):  FAILURE: update.xml from ${update_xml_url} redirected to ${update_xml_actual_url} but could not retrieve update.xml from here" >&2
        echo "UPDATE_XML_REDIRECT_FAILED ${update_xml_url} ${update_xml_actual_url} ${update_xml} ${update_xml_headers} ${update_xml_curl_exit_code}" >> "${failures}"
    fi
fi

# keep the temp files, in case there are errors later on, just keep a record of their name so can be deleted at end
echo "${update_xml}" >> "${temp_files}"
echo "${update_xml_headers}" >> "${temp_files}"
