import logging, unittest
from main import Url

class UrlTest(unittest.TestCase):
  def test_sane_domain(self):
    url = Url('google.com')
    self.assertEqual('google.com', url.original_domain)
    self.assertEqual('http://google.com', url.domain)
    
  def test_domain_with_http(self):
    url = Url('http://google.com')
    self.assertEqual('http://google.com', url.original_domain)
    self.assertEqual('http://google.com', url.domain)

  def test_domain_with_http_encoded(self):
    url = Url('http%3A//google.com')
    self.assertEqual('google.com', url.original_domain)
    self.assertEqual('http://google.com', url.domain)