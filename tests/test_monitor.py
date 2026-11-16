"""All fixture facts are synthetic and confined to temporary directories."""
import copy,json,tempfile,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import Mock,patch
from datetime import datetime,timedelta,timezone
import monitor as m
from formats import initial,metric,parse_profile,parse_recent,parse,directory_record
FIX=Path(__file__).parent/'fixtures'
AT='2026-11-16T00:00:00+00:00'
def met(v,precision='public_profile_published_snapshot',sync=None):return{'amount':v,'currency':'USD','display':'$'+str(v),'precision':precision,'synced_at':sync,'source_url':'https://trustmrr.com/startup/fixture-alpha.md','read_at':AT}
def project(slug='fixture-alpha',v=0):
    x=initial(slug,'SYNTHETIC '+slug,'https://trustmrr.com/startup/'+slug);x.update(source_url=x['trustmrr_url']+'.md',read_at=AT,profile_read=True,directory_present=True);x['metrics']['revenue_total']=met(v);return x
class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def cfg(self):return{'request_interval_seconds':0,'request_timeout_seconds':1,'rate_limit_backoff_hours':6,'robots_min_interval_hours':24,'directory_min_interval_hours':12,'recent_min_interval_hours':2,'profile_min_interval_hours':24,'full_min_interval_hours':12,'new_profiles_per_run':0}
    def prep(self,projects=None):
        projects=projects or[project()];snap,version=m.export_snapshot(self.root,projects,{},[],self.root/'library')
        ob,pos=m.seed_observations(projects);past=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat();state={'schema_version':1,'observations':ob,'positive_seen':pos,'first_seen':{p['slug']:AT for p in projects},'latest_version':version,'latest_snapshot':str(snap.relative_to(self.root)),'last_full_at':past,'last_full_day':m.localday(past),'last_full_attempt_day':m.localday(past),'url_cache':{}}
        m.commit(self.root,state,{'at':m.now(),'events':[]},'synthetic-setup.json');m.save(self.root/'watchlist.json',{'projects':[]});return state
    def test_zero_to_positive_is_observed_not_first_sale(self):
        e=m.compare_metric('fixture-alpha','revenue_total',met(0),met(10),{},AT)
        signal=next(x for x in e if x['type']=='first_observed_positive');self.assertIn('NOT proof',signal['note'])
    def test_missing_does_not_become_zero(self):
        self.assertEqual([],m.compare_metric('x','revenue_total',None,met(9),{},AT));self.assertEqual([],m.compare_metric('x','revenue_total',met(0),None,{},AT))
    def test_precision_channels_not_cross_compared(self):
        old=met(0,'directory_display_rounded_or_unknown');self.assertEqual([],m.compare_metric('x','revenue_total',old,met(3),{},AT))
        x=project(v=0);x['metrics']['revenue_total']=old;ob,pos=m.seed_observations([x]);st={'observations':ob,'positive_seen':pos};self.assertEqual([],m.observe(st,project(v=3),AT))
    def test_rounding_only_display_change_no_relative_growth(self):
        es=m.compare_metric('x','mrr',met(100,'directory_display_rounded_or_unknown'),met(101,'directory_display_rounded_or_unknown'),{},AT);self.assertEqual(es[0]['type'],'display_change');self.assertNotIn('relative_change',es[0])
    def test_rolling_decline_not_churn(self):
        es=m.compare_metric('x','revenue_30d',met(20),met(10),{},AT);self.assertIn('NOT prove churn',es[0]['note']);self.assertEqual(es[0]['type'],'metric_decrease')
    def test_sync_revision_not_growth(self):
        es=m.compare_metric('x','mrr',met(10,sync=AT),met(20,sync=AT),{},AT);self.assertEqual(es[0]['type'],'source_revision_noncomparable')
    def test_recent_revenue_period_unknown(self):
        x=parse_recent((FIX/'recent.html').read_text(),AT)[0];self.assertIsNone(x['metrics']['revenue_total']);self.assertIsNone(x['metrics']['revenue_30d']);self.assertEqual(x['metrics']['revenue_unspecified']['amount'],20)
    def test_profile_founded_not_launch(self):
        x=parse_profile((FIX/'profile.md').read_text(),'fixture-alpha',AT);self.assertEqual(x['founded_date'],'2020-01-01');self.assertIsNone(x['launch_date'])
    def test_directory_parse_keeps_zero(self):
        x=directory_record(parse(1,(FIX/'directory.html').read_text(),'',False,AT)[0]);self.assertEqual(x['metrics']['mrr']['amount'],0)
    def test_merge_missing_and_profile_flags(self):
        old=project(v=12);incoming=initial('fixture-alpha','SYNTHETIC','https://trustmrr.com/startup/fixture-alpha');new=m.merge_project(old,incoming);self.assertEqual(new['metrics']['revenue_total']['amount'],12);self.assertTrue(new['directory_present']);self.assertTrue(new['profile_read'])
    def test_hash_ignores_read_time_sync_and_position(self):
        a=project(v=1);b=copy.deepcopy(a);b['read_at']='2099-01-01T00:00:00Z';b['directory_page']=99;b['metrics']['revenue_total']['synced_at']='2099-01-01T00:00:00Z';self.assertEqual(m.semantic_hash([a]),m.semantic_hash([b]))
    def test_lock_prevents_parallel_process(self):
        with m.RunLock(self.root):
            code='from pathlib import Path; from monitor import RunLock,Locked; import sys\ntry:\n with RunLock(Path(sys.argv[1])):sys.exit(9)\nexcept Locked:sys.exit(0)'
            result=subprocess.run([sys.executable,'-c',code,str(self.root)],cwd=Path(m.__file__).parent,capture_output=True);self.assertEqual(result.returncode,0,result.stderr)
    def test_fresh_cache_makes_no_network_request(self):
        state={'url_cache':{}};client=m.PublicClient(self.root,state,self.cfg());p=self.root/'cache/fresh.txt';m.atomic_bytes(p,b'cached synthetic body');url='https://trustmrr.com/recent';state['url_cache'][url]={'body_file':'cache/fresh.txt','validated_at':m.now(),'body_read_at':AT};client.session.get=Mock(side_effect=AssertionError('No network allowed'));body,at=client.get(url,2);self.assertEqual(body,'cached synthetic body');self.assertEqual(client.requests,0)
    def test_public_next_refresh_honored(self):
        state={'url_cache':{}};client=m.PublicClient(self.root,state,self.cfg());p=self.root/'cache/future.txt';m.atomic_bytes(p,b'cached');url='https://trustmrr.com/startup/fixture-alpha.md';state['url_cache'][url]={'body_file':'cache/future.txt','validated_at':'2020-01-01T00:00:00Z','body_read_at':AT,'public_next_refresh_at':'2099-01-01T00:00:00Z'};client.session.get=Mock(side_effect=AssertionError('No network'));client.get(url,24);self.assertEqual(client.requests,0)
    def test_empty_response_keeps_old_cache(self):
        state={'url_cache':{}};client=m.PublicClient(self.root,state,self.cfg());p=self.root/'cache/old.txt';m.atomic_bytes(p,b'old valid synthetic body');url='https://trustmrr.com/recent';state['url_cache'][url]={'body_file':'cache/old.txt','validated_at':'2020-01-01T00:00:00Z','body_read_at':AT};client.session.get=Mock(return_value=Mock(status_code=200,text='',headers={}))
        with self.assertRaises(m.FetchError):client.get(url,2)
        self.assertEqual(p.read_text(),'old valid synthetic body');self.assertEqual(state['url_cache'][url]['body_read_at'],AT)
    def test_403_stops_without_alternate(self):
        state={'url_cache':{}};client=m.PublicClient(self.root,state,self.cfg());client.session.get=Mock(return_value=Mock(status_code=403,text='Denied',headers={}))
        for _ in range(2):
            with self.assertRaises(m.Blocked):client.get('https://trustmrr.com/recent',2)
        self.assertEqual(client.session.get.call_count,1);self.assertTrue(state['manual_review_required'])
    def test_429_backoff(self):
        state={'url_cache':{}};client=m.PublicClient(self.root,state,self.cfg());client.session.get=Mock(return_value=Mock(status_code=429,text='Rate limited',headers={'Retry-After':'30000'}))
        with self.assertRaises(m.Blocked):client.get('https://trustmrr.com/recent',2)
        self.assertGreater((m.dt(state['not_before'])-datetime.now(timezone.utc)).total_seconds(),29900)
    def test_failed_run_does_not_replace_latest_or_observations(self):
        state=self.prep();before=(self.root/'latest/projects.json').read_bytes();client=Mock(requests=0,cache_hits=0);client.check_robots.side_effect=m.FetchError('SYNTHETIC network failure')
        with patch('monitor.PublicClient',return_value=client):result=m.refresh(self.root,self.cfg())
        self.assertEqual(result['status'],'failed');self.assertEqual(before,(self.root/'latest/projects.json').read_bytes());self.assertEqual(m.load(self.root/'state.json')['observations'],state['observations'])
    def test_new_project_and_partial_page_failure_preserve_pool(self):
        state=self.prep([project('fixture-existing',12)]);directory=(FIX/'directory.html').read_text().replace('of 1 startups · Page 1 of 1','of 2 startups · Page 1 of 2');client=Mock(requests=0,cache_hits=0);client.check_robots.return_value=None
        def get(url,*args):
            if url.endswith('/startups'):return directory,m.now()
            if '/page/2'in url:raise m.FetchError('SYNTHETIC page 2 failure')
            if url.endswith('/recent'):return(FIX/'recent.html').read_text(),m.now()
            raise AssertionError(url)
        client.get.side_effect=get
        with patch('monitor.PublicClient',return_value=client):result=m.refresh(self.root,self.cfg())
        self.assertEqual(result['status'],'partial_success');rows=m.load(self.root/'latest/projects.json')['projects'];self.assertEqual({r['slug']for r in rows},{'fixture-existing','fixture-alpha'});change=[p for p in(self.root/'changes').glob('*.json')if p.name!='synthetic-setup.json'][0];events=m.load(change)['events'];self.assertEqual(sum(e['type']=='new_project'for e in events),1);self.assertFalse(any(e['type']=='first_observed_positive'for e in events));self.assertFalse(result['coverage']['full_crawl_completed'])
    def test_commit_recovery_rolls_forward(self):
        state=self.prep();new=project(v=99);snap,ver=m.export_snapshot(self.root,[new],{},[],self.root/'library');state['latest_version']=ver;state['latest_snapshot']=str(snap.relative_to(self.root));m.save(self.root/'.pending-commit.json',{'state':state,'change':{'at':m.now(),'events':[]},'change_filename':'synthetic-recover.json'});self.assertTrue(m.recover_commit(self.root));self.assertEqual(m.load(self.root/'latest/projects.json')['projects'][0]['metrics']['revenue_total']['amount'],99);self.assertFalse((self.root/'.pending-commit.json').exists())
if __name__=='__main__':unittest.main()
