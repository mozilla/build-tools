import os, sys
sys.path.append('..')
import graphserver
import unittest
import tempfile
import json

class GraphserverTestCase(unittest.TestCase):

    def setUp(self):
        graphserver.app.config.from_object('config.TestConfig')
        self.app = graphserver.app.test_client()

    def test_empty_db(self):
        rv = self.app.get('/')
        assert 'No machines' in rv.data
        assert 'No branches' in rv.data

    def test_add_empty_branch_web(self):
        rv = self.app.post('/branches', data=dict(
            branch_name='',
        ), follow_redirects=True)
        assert 'cannot be blank' in rv.data

    def test_add_branch(self):
        rv = self.app.post('/branches', data=dict(
            branch_name='new_branch',
            _method='insert'
        ), follow_redirects=True)
        assert 'new_branch' in rv.data
        resp = self.app.get('/branches?format=json', follow_redirects=True)
        results = json.loads(resp.data)
        assert results['1'] == 'new_branch'

    def test_delete_branch(self):
        rv = self.app.post('/branches', data=dict(
            id=1,
            branch_name='new_branch',
            _method='delete'
        ), follow_redirects=True)
        rv = self.app.get('/')
        assert 'No branches' in rv.data

    def test_delete_nonexistent_branch_json(self):
        resp = self.app.get('/branches?format=json', follow_redirects=True)
        results_pre = json.loads(resp.data)
        rv = self.app.post('/branches', data=dict(
            id=14,
            format='json',
            _method='delete'
        ), follow_redirects=True)
        resp = self.app.get('/branches?format=json', follow_redirects=True)
        results_post = json.loads(resp.data)
        assert results_pre == results_post

    def test_add_empty_branch_json(self):
        resp = self.app.get('/branches?format=json', follow_redirects=True)
        results_pre = json.loads(resp.data)
        rv = self.app.post('/branches', data=dict(
            branch_name='',
            format='json',
        ), follow_redirects=True)
        resp = self.app.get('/branches?format=json', follow_redirects=True)
        results_post = json.loads(resp.data)
        assert results_pre == results_post

    def test_add_machine(self):
        rv = self.app.post('/machines', data=dict(
            os_id=13,
            is_throttling=1,
            cpu_speed=1.12,
            machine_name='new_machine',
            is_active=0,
        ), follow_redirects=True)
        assert 'new_machine' in rv.data
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results = json.loads(resp.data)
        assert results['1'] == 'new_machine'

    def test_add_machine_with_blank_strings_json(self):
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results_pre = json.loads(resp.data)
        rv = self.app.post('/machines', data=dict(
            os_id=12,
            is_throttling=1,
            cpu_speed=1.12,
            machine_name='',
            is_active=0,
            format='json',
        ), follow_redirects=True)
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results_post = json.loads(resp.data)
        assert results_pre == results_post

    def test_add_machine_with_non_numeric_json(self):
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results_pre = json.loads(resp.data)
        rv = self.app.post('/machines', data=dict(
            os_id='OS',
            is_throttling='s',
            cpu_speed='',
            machine_name='',
            is_active='',
            format='json',
        ), follow_redirects=True)
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results_post = json.loads(resp.data)
        assert results_pre == results_post

    def test_delete_nonexistent_machine_json(self):
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results_pre = json.loads(resp.data)
        rv = self.app.post('/machines', data=dict(
            id=14,
            format='json',
            _method='delete'
        ), follow_redirects=True)
        resp = self.app.get('/machines?format=json', follow_redirects=True)
        results_post = json.loads(resp.data)
        assert results_pre == results_post

    def test_delete_machine(self):
        rv = self.app.post('/machines', data=dict(
            id=1,
            machine_name='new_machine',
            _method='delete'
        ), follow_redirects=True)
        rv = self.app.get('/')
        assert 'No machines' in rv.data

if __name__ == '__main__':
    unittest.main()