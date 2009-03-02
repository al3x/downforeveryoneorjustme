import unittest

from google.appengine.ext import webapp
from main import FrontPage, CheckDomain
from webtest import TestApp

class MainTest(unittest.TestCase):
  def setUp(self):
    self.application = webapp.WSGIApplication([('/', FrontPage)], debug=True)

  def test_front_page(self):
    app = TestApp(self.application)
    response = app.get('/')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('down for everyone' in response)


class CheckDomainTest(unittest.TestCase):
  def setUp(self):
    self.application = webapp.WSGIApplication([(r'/(.*)', CheckDomain)], debug=True)
    
  def test_page_with_param(self):
    app = TestApp(self.application)
    response = app.get('/google.com')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('google.com' in response)

  def test_known_bad_domain(self):
    app = TestApp(self.application)
    response = app.get('/cse.ohio-state.edu')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('cse.ohio-state.edu' in response)
    self.assertTrue('down' in response)
    
  def test_amazon(self):
    app = TestApp(self.application)
    response = app.get('/amazon.com')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('amazon.com' in response)
    self.assertFalse('interwho' in response)
    
  def test_google_with_http(self):
    app = TestApp(self.application)
    response = app.get('/http://google.com')
    self.assertEqual('200 OK', response.status)
    self.assertTrue('google.com' in response)
    self.assertFalse('interwho' in response)