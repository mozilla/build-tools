import copy
import json
import jsone
import logging
import requests
import slugid
import taskcluster

log = logging.getLogger(__name__)


def find_action(name, actions):
    for action in actions["actions"]:
        if action["name"] == name:
            return copy.deepcopy(action)
    else:
        return None


def fetch_actions_json(task_id):
    queue = taskcluster.Queue()
    actions_url = queue.buildUrl("getLatestArtifact", task_id, 'public/actions.json')
    q = requests.get(actions_url)
    q.raise_for_status()
    return q.json()


def generate_action_task(project, revision, next_version, build_number, release_promotion_flavor):
    decision_task_route = "gecko.v2.{project}.revision.{revision}.firefox.decision".format(
         project=project, revision=revision)
    index = taskcluster.Index()
    decision_task_id = index.findTask(decision_task_route)["taskId"]
    actions = fetch_actions_json(decision_task_id)

    relpro = find_action("release-promotion", actions)
    context = copy.deepcopy(actions["variables"])  # parameters
    action_task_id = slugid.nice()
    context.update({
        "input": {
            "build_number": build_number,
            "next_version": next_version,
            "release_promotion_flavor": release_promotion_flavor,
        },
        "ownTaskId": action_task_id,
        "taskId": None,
        "task": None,
    })
    action_task = jsone.render(relpro["task"], context)
    # override ACTION_TASK_GROUP_ID, so we know the new ID in advance
    action_task["payload"]["env"]["ACTION_TASK_GROUP_ID"] = action_task_id
    return action_task_id, action_task


def submit_action_task(queue, action_task_id, action_task):
    result = queue.createTask(action_task_id, action_task)
    log.info("Submitted action task %s", action_task_id)
    log.info("Action task:\n%s", json.dumps(action_task, sort_keys=True, indent=2))
    log.info("Result:\n%s", result)
