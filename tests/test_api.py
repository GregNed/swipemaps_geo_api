import unittest
import requests
import json


class TestAPI(unittest.TestCase):

    def test_healthcheck(self):
        res = requests.get('http://localhost:8000/health/')
        status = json.loads(res.text)['status']
        self.assertEqual(status, 'OK')


if __name__ == '__main__':
    unittest.main()
