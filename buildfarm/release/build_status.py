import taskcluster

from kickoff import task_for_revision

import logging
log = logging.getLogger(__name__)


# TODO: Bug 1300147. Avoid having 7 parameters by using a release object that contains only what's needed.
def are_en_us_builds_completed(index, queue, release_name, branch, revision, tc_product_name, platforms):
    try:
        tasks_to_watch = [
            task_for_revision(index, branch, revision, tc_product_name, platform)['taskId']
            for platform in platforms
        ]
    except taskcluster.exceptions.TaskclusterRestFailure:
        log.debug('At least one task is not created yet for %s', release_name)
        return False

    log.debug('All tasks have been found: %s', tasks_to_watch)
    return _are_all_tasks_completed(queue, tasks_to_watch)


def _are_all_tasks_completed(queue, taskIds):
    return all([queue.status(taskId)['status']['state'] == 'completed' for taskId in taskIds])
