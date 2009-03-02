import unittest
from google.appengine.api import urlfetch


class AppEngineAPITest(unittest.TestCase):
    
    def test_urlfetch(self):
        response = urlfetch.fetch('http://www.google.com')
        self.assertEquals(0, response.content.find('<html>'))

