"""Synthetic credential-shaped text only; generated values are never real credentials."""
import unittest
from redaction import scrub,redact_text,sensitive,MARKER
from formats import parse_profile
class RedactionTests(unittest.TestCase):
 def fake(self):return'rk_'+'live_'+'X'*32
 def test_restricted_key_is_detected(self):self.assertTrue(sensitive(self.fake()))
 def test_website_omitted_but_project_retained(self):
  value={'slug':'fixture-only','website_url':'https://example.invalid/?key='+self.fake(),'name':'SYNTHETIC'};out=scrub(value);self.assertIsNone(out['website_url']);self.assertEqual(out['slug'],'fixture-only');self.assertEqual(out['publication_redactions'],['website_url'])
 def test_raw_markdown_website_is_not_a_broken_credential_link(self):
  key=self.fake();text='- Website: [https://example.invalid/?key='+key+'](https://example.invalid/?key='+key+')';out=redact_text(text);self.assertNotIn(key,out);self.assertEqual(out,'- Website: Not provided (redacted unsafe source URL)')
 def test_nested_archive_fields_are_scrubbed(self):
  value={'projects':[{'description':'SYNTHETIC '+self.fake()}]};out=scrub(value);self.assertIn(MARKER,out['projects'][0]['description']);self.assertFalse(sensitive(out['projects'][0]['description']))
if __name__=='__main__':unittest.main()

class URLSafetyTests(unittest.TestCase):
 def test_only_http_https_without_authentication(self):
  from redaction import url_problem
  for value in['javascript:synthetic','data:text/html,synthetic','file:///synthetic','https://user:pass@example.invalid/','https://example.invalid/?access_token=synthetic','https://example.invalid/#token=synthetic']:
   self.assertIsNotNone(url_problem(value))
  self.assertIsNone(url_problem('https://example.invalid/project?q=public'))
 def test_nested_sensitive_field_names_omitted(self):
  out=scrub({'nested':{'api_key':'SYNTHETIC_VALUE_ONLY','password':'SYNTHETIC_VALUE_ONLY'}})
  self.assertIsNone(out['nested']['api_key']);self.assertIsNone(out['nested']['password'])
 def test_markup_and_encoded_scheme_removed(self):
  from redaction import text_findings
  text='<script>SYNTHETIC</script> https://user:pass@example.invalid/'
  out=redact_text(text);self.assertEqual(text_findings(out),[])
  self.assertIsNone(scrub({'website_url':'%6aavascript:synthetic'})['website_url'])
