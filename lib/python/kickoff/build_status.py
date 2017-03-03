from datetime import datetime, timedelta
from dateutil import parser, tz
from taskcluster.exceptions import TaskclusterRestFailure

import logging
log = logging.getLogger(__name__)


_BUILD_WATCHERS = {}


# TODO: Bug 1300147. Avoid having 7 parameters by using a release object that
# contains only what's needed.
def are_en_us_builds_completed(index, release_name, submitted_at, revision,
                               platforms, queue, tc_task_indexes):
    try:
        watcher = _BUILD_WATCHERS[release_name]
    except KeyError:
        watcher = EnUsBuildsWatcher(index, release_name, submitted_at,
                                    revision, platforms, queue,
                                    tc_task_indexes)
        _BUILD_WATCHERS[release_name] = watcher
        log.debug('New watcher created for "%s"', release_name)

    result = watcher.are_builds_completed()

    if result is True:
        del _BUILD_WATCHERS[release_name]
        log.debug('Builds for "%s" are completed. Watcher deleted',
                  release_name)

    return result


class LoggedError(Exception):
    def __init__(self, message):
        log.exception(message)
        Exception.__init__(self, message)


class EnUsBuildsWatcher:
    # TODO: Bug 1300147 as well
    def __init__(self, index, release_name, submitted_at, revision,
                 platforms, queue, tc_task_indexes):
        self.taskcluster_index = index

        self.release_name = release_name
        self.revision = revision
        self.task_per_platform = {p: None for p in platforms}
        self.queue = queue
        self.tc_task_indexes = tc_task_indexes

        self._timeout_watcher = TimeoutWatcher(start_timestamp=submitted_at)

    def are_builds_completed(self):
        if self._timeout_watcher.timed_out:
            raise TimeoutWatcher.TimeoutError(
                self.release_name, self._timeout_watcher.start_timestamp)

        self._fetch_completed_tasks()

        return len(self._platforms_with_no_task) == 0

    def _fetch_completed_tasks(self):
        platforms_with_no_task = self._platforms_with_no_task
        log.debug('Release "%s" still has to find tasks for %s',
                  self.release_name, platforms_with_no_task)

        for platform in platforms_with_no_task:
            try:
                # Tasks are always completed if they are referenced in the
                # index https://docs.taskcluster.net/reference/core/index
                # Assuming that the signed tasks are completed after their
                # unsigned counterparts
                route = self.tc_task_indexes[platform]['signed'].format(
                    rev=self.revision)
                task_id = self.taskcluster_index.findTask(route)['taskId']
                # Bug 1307326 - consider only tasks indexed with rank > 0.
                # If `rank` is unknown use tier-1 tasks.
                task = self.queue.task(task_id)
                rank = task["extra"].get("index", {}).get("rank")
                tier = task["extra"].get("treeherder", {}).get("tier")
                if rank is None:
                    eligible = tier == 1
                else:
                    eligible = rank != 0
                if  not eligible:
                    log.debug("Ignoring task %s because rank (%s) or tier (%s)",
                              task_id, rank, tier)
                    continue
            except TaskclusterRestFailure:
                log.debug('Task for platform "%s" is not yet created for '
                          'release "%s"', platform, self.release_name)
                continue

            log.debug('Task "%s" was found for release "%s" and platform "%s"',
                      task_id, self.release_name, platform)
            self.task_per_platform[platform] = task_id

    @property
    def _platforms_with_no_task(self):
        return [platform for platform, task in
                self.task_per_platform.iteritems() if task is None]


class TimeoutWatcher:
    MAX_WAITING_TIME = timedelta(days=1)

    def __init__(self, start_timestamp):
        self.start_timestamp = parser.parse(start_timestamp)

    @staticmethod
    def _now():
        # Can't use utcnow(), because dateutil gives offset-aware datetimes
        return datetime.now(tz.tzutc())

    @property
    def timed_out(self):
        return self._now() - self.start_timestamp >= self.MAX_WAITING_TIME

    class TimeoutError(LoggedError):
        def __init__(self, release_name, start_timestamp):
            LoggedError.__init__(
                self,
                '{} has spent more than {} between the release being submitted'
                ' on ship-it (at {} [UTC]) and now.'.format(
                    release_name, TimeoutWatcher.MAX_WAITING_TIME,
                    start_timestamp)
            )

    class AlreadyStartedError(Exception):
        # Common error, there's no need to log it.
        pass
