import copy
import json
import jsone
import logging
import requests
import slugid
import taskcluster

from util.retry import retry

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

    def _get():
        q = requests.get(actions_url)
        q.raise_for_status()
        return q.json()

    return retry(_get)


def find_decision_task_id(trust_domain, project, revision):
    decision_task_route = "{trust_domain}.v2.{project}.revision.{revision}.taskgraph.decision".format(
        trust_domain=trust_domain,
        project=project,
        revision=revision,
    )
    index = taskcluster.Index()

    def _get():
        return index.findTask(decision_task_route)["taskId"]

    return retry(_get)


def generate_action_task(decision_task_id, action_task_input):
    actions = fetch_actions_json(decision_task_id)
    relpro = find_action("release-promotion", actions)
    context = copy.deepcopy(actions["variables"])  # parameters
    action_task_id = slugid.nice()
    context.update({
        "input": action_task_input,
        "ownTaskId": action_task_id,
        "taskId": None,
        "task": None,
        "taskGroupId": decision_task_id,
    })
    action_task = jsone.render(relpro["task"], context)
    return action_task_id, action_task


def submit_action_task(queue, action_task_id, action_task):
    result = queue.createTask(action_task_id, action_task)
    log.info("Submitted action task %s", action_task_id)
    log.info("Action task:\n%s", json.dumps(action_task, sort_keys=True, indent=2))
    log.info("Result:\n%s", result)
