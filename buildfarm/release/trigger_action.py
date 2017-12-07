import argparse
import json
import logging
import site
import taskcluster
import yaml
import copy

from os import path

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from kickoff.actions import generate_action_task, submit_action_task, find_decision_task_id

log = logging.getLogger(__name__)
SUPPORTED_ACTIONS = [
    "publish_fennec",
    "push_devedition",
    "push_firefox",
    "ship_devedition",
    "ship_fennec",
    "ship_firefox",
]


def get_task(task_id):
    queue = taskcluster.Queue()
    return queue.task(task_id)


def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                        level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action-task-id", required=True,
        help="Task ID of the initial action task (promote_fennec or promote_firefox"
    )
    parser.add_argument("--previous-graph-ids",
                        help="Override previous graphs, inlcuding the decision task")
    parser.add_argument("--release-runner-config", required=True, type=argparse.FileType('r'),
                        help="Release runner config")
    parser.add_argument("--action-flavor", required=True, choices=SUPPORTED_ACTIONS)
    parser.add_argument("--force", action="store_true", default=False,
                        help="Submit action task without asking")
    args = parser.parse_args()
    release_runner_config = yaml.safe_load(args.release_runner_config)
    tc_config = {
        "credentials": {
            "clientId": release_runner_config["taskcluster"].get("client_id"),
            "accessToken": release_runner_config["taskcluster"].get("access_token"),
        },
        "maxRetries": 12,
    }
    queue = taskcluster.Queue(tc_config)

    task = get_task(args.action_task_id)
    action_task_input = copy.deepcopy(task["extra"]["action"]["context"]["input"])
    parameters = task["extra"]["action"]["context"]["parameters"]
    project = parameters["project"]
    revision = parameters["head_rev"]
    previous_graph_ids = args.previous_graph_ids
    if not previous_graph_ids:
        previous_graph_ids = [find_decision_task_id(project, revision)]
    else:
        previous_graph_ids = previous_graph_ids.split(',')
    action_task_input.update({
        "release_promotion_flavor": args.action_flavor,
        "previous_graph_ids": previous_graph_ids + [args.action_task_id],
    })
    action_task_id, action_task = generate_action_task(
            project=parameters["project"],
            revision=parameters["head_rev"],
            action_task_input=action_task_input,
    )

    log.info("Submitting action task %s for %s", action_task_id, args.action_flavor)
    log.info("Project: %s", project)
    log.info("Revision: %s", revision)
    log.info("Next version: %s", action_task_input["next_version"])
    log.info("Build number: %s", action_task_input["build_number"])
    log.info("Task definition:\n%s", json.dumps(action_task, sort_keys=True, indent=2))
    if not args.force:
        yes_no = raw_input("Submit the task? [y/N]: ")
        if yes_no not in ('y', 'Y'):
            log.info("Not submitting")
            exit(1)

    submit_action_task(queue=queue, action_task_id=action_task_id,
                       action_task=action_task)


if __name__ == "__main__":
    main()
