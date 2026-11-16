"""Synthetic temporary export fixtures; never added to the factual dataset."""
import json,tempfile,unittest,zipfile
from pathlib import Path
from build_data import build
from monitor import semantic_hash

class ExportVersionTests(unittest.TestCase):
    def test_all_export_versions_follow_sanitized_facts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=root/'data';(data/'raw').mkdir(parents=True)
            project={'slug':'fixture-export-metadata','name':'Synthetic fixture','trustmrr_url':'https://example.invalid/startup/fixture-export-metadata'}
            payload={'metadata':{'semantic_version_sha256':'stale-synthetic-hash'},'projects':[project]}
            for name,obj in [('projects.json',payload),('version.json',{'semantic_version_sha256':'stale-synthetic-hash'}),('annotations.json',{'projects':{}}),('monitor-state.json',{'latest_version':'stale-synthetic-hash'})]:
                (data/name).write_text(json.dumps(obj))
            build(root);expected=semantic_hash([project])
            self.assertEqual(json.loads((data/'projects.json').read_text())['metadata']['semantic_version_sha256'],expected)
            self.assertEqual(json.loads((data/'metadata.json').read_text())['semantic_version_sha256'],expected)
            self.assertEqual(json.loads((data/'index.json').read_text())['metadata']['semantic_version_sha256'],expected)
            self.assertEqual(json.loads((data/'version.json').read_text())['semantic_version_sha256'],expected)
            self.assertEqual(json.loads((data/'monitor-state.json').read_text())['latest_version'],expected)
            with zipfile.ZipFile(data/'trustmrr-data.zip') as z:
                self.assertEqual(json.loads(z.read('data/projects.json'))['metadata']['semantic_version_sha256'],expected)
