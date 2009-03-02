import unittest
from webtest import TestApp
from google.appengine.ext import webapp
import index

class IndexTest(unittest.TestCase):

  def setUp(self):
      self.application = webapp.WSGIApplication([('/', index.IndexHandler)], debug=True)

  def test_default_page(self):
      app = TestApp(self.application)
      response = app.get('/')
      self.assertEqual('200 OK', response.status)
      self.assertTrue('Hello, World!' in response)

  def test_page_with_param(self):
      app = TestApp(self.application)
      response = app.get('/?name=Bob')
      self.assertEqual('200 OK', response.status)
      self.assertTrue('Hello, Bob!' in response)
