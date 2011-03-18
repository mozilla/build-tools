import mock
import unittest

from util.retry import retry

ATTEMPT_N = 1

def _succeedOnSecondAttempt(foo=None, exception=Exception):
    global ATTEMPT_N
    if ATTEMPT_N == 2:
        ATTEMPT_N += 1
        return
    ATTEMPT_N += 1
    raise exception("Fail")

def _alwaysPass():
    global ATTEMPT_N
    ATTEMPT_N += 1
    return True

def _alwaysFail():
    raise Exception("Fail")

class NewError(Exception):
    pass

class OtherError(Exception):
    pass

def _raiseCustomException():
    return _succeedOnSecondAttempt(exception=NewError)

class TestRetry(unittest.TestCase):
    def setUp(self):
        global ATTEMPT_N
        ATTEMPT_N = 1

    def testRetrySucceed(self):
        # Will raise if anything goes wrong
        retry(_succeedOnSecondAttempt, attempts=2)
    
    def testRetryFailWithoutCatching(self):
        self.assertRaises(Exception, retry, _alwaysFail, exceptions=())

    def testRetryFailEnsureRaisesLastException(self):
        self.assertRaises(Exception, retry, _alwaysFail)

    def testRetrySelectiveExceptionSucceed(self):
        retry(_raiseCustomException, attempts=2, retry_exceptions=(NewError,))

    def testRetrySelectiveExceptionFail(self):
        self.assertRaises(NewError, retry, _raiseCustomException, attempts=2,
                          retry_exceptions=(OtherError,))

    # TODO: figure out a way to test that the sleep actually happened
    def testRetryWithSleep(self):
        retry(_succeedOnSecondAttempt, attempts=2, sleeptime=1)

    def testRetryOnlyRunOnce(self):
        """Tests that retry() doesn't call the action again after success"""
        global ATTEMPT_N
        retry(_alwaysPass, attempts=3)
        # ATTEMPT_N gets increased regardless of pass/fail
        self.assertEquals(2, ATTEMPT_N)

    def testRetryReturns(self):
        ret = retry(_alwaysPass)
        self.assertEquals(ret, True)

    def testRetryCleanupIsCalled(self):
        cleanup = mock.Mock()
        retry(_succeedOnSecondAttempt, cleanup=cleanup)
        self.assertEquals(cleanup.call_count, 1)
