#!/usr/bin/env python
import os
from os import path
import logging
import site
import sys

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))
# Use explicit version of python-requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lib/python/vendor/requests-0.10.8"))

from balrog.submitter.api import Rule, Release


if __name__ == '__main__':
    from argparse import ArgumentParser, REMAINDER
    parser = ArgumentParser()

    parser.add_argument("-a", "--api-root", dest="api_root", required=True)
    parser.add_argument("-c", "--credentials-file", dest="credentials_file", required=True)
    parser.add_argument("-u", "--username", dest="username", required=True)
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False)
    parser.add_argument("-r", "--rule-id", dest="rule_ids", action="append", required=True)
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", default=False)
    parser.add_argument("action", nargs=1, choices=["lock", "unlock"])
    parser.add_argument("action_args", nargs=REMAINDER)

    args = parser.parse_args()

    logging_level = logging.INFO
    if args.verbose:
        logging_level = logging.DEBUG
    logging.basicConfig(stream=sys.stdout, level=logging_level,
                        format="%(message)s")

    credentials = {}
    execfile(args.credentials_file, credentials)
    auth = (args.username, credentials['balrog_credentials'][args.username])

    rule_api = Rule(args.api_root, auth)

    if args.action == ["lock"]:
        my_args = args.action_args
        if len(my_args) > 1:
            parser.error("Unsupported number of args for the lock command.")

        for rule_id in args.rule_ids:
            release_name = None
            if len(my_args) == 1:
                release_name = args[0]

            if not release_name:
                rule_data, _ = rule_api.get_data(rule_id)
                latest_blob_name = rule_data["mapping"]
                release_api = Release(args.api_root, auth)
                release_data, _ = release_api.get_data(latest_blob_name)
                buildid = None
                for p in release_data["platforms"].values():
                    enUS = p.get("locales", {}).get("en-US", {})
                    next_buildid = enUS.get("buildID")
                    if next_buildid > buildid:
                        buildid = next_buildid
                if not buildid:
                    logging.error("Couldn't find latest buildid for rule %s", rule_id)
                    sys.exit(1)

                root_name = "-".join(latest_blob_name.split("-")[:-1])
                release_name = "%s-%s" % (root_name, buildid)

            if not args.dry_run:
                logging.info("Locking rule %s to %s", rule_id, release_name)
                rule_api.update_rule(rule_id, mapping=release_name)
            else:
                logging.info("Would've locked rule %s to %s", rule_id, release_name)

    elif args.action == ["unlock"]:
        if args.action_args:
            parser.error("Unlock command does not accept any args.")

        for rule_id in args.rule_ids:
            rule_data, _ = rule_api.get_data(rule_id)
            root_name = "-".join(rule_data["mapping"].split("-")[:-1])
            release_name = "%s-latest" % root_name

            if not args.dry_run:
                logging.info("Unlocking rule %s back to %s", rule_id, release_name)
                rule_api.update_rule(rule_id, mapping=release_name)
            else:
                logging.info("Would've unlocked rule %s back to %s", rule_id, release_name)
