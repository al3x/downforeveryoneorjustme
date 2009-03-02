import main
import unittest

from google.appengine.ext import webapp
from webtest import TestApp

class MainTest(unittest.TestCase):
  def setUp(self):
    self.application = webapp.WSGIApplication([('/', main.FrontPage)], debug=True)

  def test_default_page(self):
    app = TestApp(self.application)
    response = app.get('/')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('down for everyone' in response)

  def test_page_with_param(self):
    app = TestApp(self.application)
    response = app.get('/?q=google.com')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('google.com' in response)

  def test_subdomain(self):
    app = TestApp(self.application)
    response = app.get('/?q=cse.ohio-state.edu')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('cse.ohio-state.edu' in response)
    self.assertFalse('interwho' in response)
    
  def test_amazon(self):
    app = TestApp(self.application)
    response = app.get('/?q=amazon.com')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('amazon.com' in response)
    self.assertFalse('interwho' in response)
    
  def test_amazon(self):
    app = TestApp(self.application)
    response = app.get('/?q=http://google.com')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('google.com' in response)
    self.assertFalse('interwho' in response)