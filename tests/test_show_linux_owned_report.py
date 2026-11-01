"""Synthetic report files only; no observer import, tasks or native monitoring."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('report_view', Path(__file__).resolve().parents[1]/'scripts/show_linux_owned_report.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture():
    root = '/owned/examples/linux-owned-fixture'
    events = []
    for seq, op in enumerate(['open', 'read', 'close', 'open', 'write', 'close', 'open'], 1):
        path = root + ('/absent.txt' if seq == 7 else '/synthetic.txt')
        a = dict(pid=41, start_ticks=101, syscall_seq=seq, operation=op, phase='ATTEMPT',
                 path=path, observed_monotonic_ns=seq*2, observed_wall_ns=1_700_000_000_000_000_000+seq*2)
        b = dict(a, phase='RESULT', observed_monotonic_ns=seq*2+1,
                 observed_wall_ns=a['observed_wall_ns']+1, retval=-2 if seq == 7 else 1 if op in ('read','write') else 3 if op == 'open' else 0,
                 errno=2 if seq == 7 else None, success=seq != 7,
                 confirmed_positive_bytes=op in ('read','write'))
        if op in ('read','write'):
            a['requested_bytes'] = b['requested_bytes'] = 1
        events.extend([a,b])
    return dict(source='LINUX_PTRACE_OWNED_DIRECT_CHILD', scope='SINGLE_THREAD_TWO_ABSOLUTE_SYNTHETIC_LEAVES',
                status='PASS_SELECTED_OWNED_SYSCALL_MATRIX_WITH_LIMITS',
                time_semantics='OBSERVER_ENTRY_EXIT_STOP_TIMES_NOT_ATOMIC_ACCESS_TIME',
                contents_collected=False, all_descendants_or_all_files=False, test_root=root,
                events=events, identity={'pid':41,'start_ticks':101},
                cleanup={'kill':False,'returncode':0,'pidfd':'CLOSED','fixture_fd':'CLOSED'})


class ViewerTests(unittest.TestCase):
    def test_complete_report_and_attempt_distinction(self):
        text = M.render_report(fixture())
        self.assertIn('14条', text)
        self.assertIn('尝试（尚无成功结论）', text)
        self.assertIn('返回1字节', text)
        self.assertIn('errno=2', text)
        self.assertIn('不重新验收', text)

    def test_partial_failure_keeps_missing_unknown(self):
        r = fixture(); r['status']='NOT_PASS'; r['events']=[]; r.pop('identity'); r['cleanup']={}
        text = M.render_report(r)
        self.assertIn('缺失或不完整，保持UNKNOWN', text)
        self.assertIn('子进程退出=UNKNOWN', text)

    def test_claimed_success_with_missing_events_rejected(self):
        r=fixture();r['events'].pop()
        with self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_claimed_success_with_zero_read_or_write_rejected(self):
        for index in (3, 9):
            r=fixture();r['events'][index].update(retval=0,confirmed_positive_bytes=False)
            with self.subTest(index=index), self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_claimed_success_with_cleanup_conflict_or_gap_rejected(self):
        for key,value in [('returncode',1),('pidfd','CLOSE_UNKNOWN'),('fixture_fd',None),('kill',True)]:
            r=fixture();r['cleanup'][key]=value
            with self.subTest(key=key), self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_claimed_success_with_wrong_negative_case_rejected(self):
        r=fixture();r['events'][-1].update(retval=-13,errno=13)
        with self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_offscope_identity_and_time_rejected(self):
        for key,value in [('path','/PRIVATE_UNEXPECTED'),('pid',42),('observed_monotonic_ns',False)]:
            r=fixture();r['events'][0][key]=value
            with self.subTest(key=key), self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_result_conflicts_and_boolean_counts_rejected(self):
        for key,value in [('retval',True),('success',False),('confirmed_positive_bytes',False),('requested_bytes',0)]:
            r=fixture();r['events'][3][key]=value
            with self.subTest(key=key), self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_unknown_source_or_expanded_scope_rejected(self):
        for key,value in [('source','APP_SELF_LOG'),('scope','ALL_FILES'),('contents_collected',True)]:
            r=fixture();r[key]=value
            with self.subTest(key=key), self.assertRaises(M.InvalidReport): M.render_report(r)

    def test_terminal_escape_is_not_interpreted(self):
        r=fixture();old=r['test_root'];r['test_root']=old+'\x1b[31m'
        for e in r['events']:e['path']=e['path'].replace(old,r['test_root'])
        text=M.render_report(r)
        self.assertNotIn('\x1b',text)
        self.assertIn('\\u001b',text)

    def test_duplicate_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json'
            for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff']:
                p.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaises((M.InvalidReport, ValueError)): M.load_report(p)

    def test_symlink_directory_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json';p.write_bytes(b'x'*(M.MAX_BYTES+1));link=Path(d)/'link';link.symlink_to(p)
            for name in [p,link,Path(d)]:
                with self.subTest(path=name), self.assertRaises((M.InvalidReport,OSError)): M.load_report(name)

    def test_same_fd_change_and_short_read_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json';p.write_text('{}')
            with patch.object(M.os,'read',return_value=b'{'), self.assertRaises(M.InvalidReport): M.load_report(p)
            real=M.os.fstat;count=[0]
            def changed(fd):
                s=real(fd);count[0]+=1
                if count[0]==1:return s
                class Info:
                    st_dev=s.st_dev;st_ino=s.st_ino;st_size=s.st_size;st_mtime_ns=s.st_mtime_ns+1;st_ctime_ns=s.st_ctime_ns
                return Info()
            with patch.object(M.os,'fstat',side_effect=changed), self.assertRaises(M.InvalidReport): M.load_report(p)

    def test_cli_complete_and_failure_does_not_echo_input(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json';p.write_text(json.dumps(fixture()))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(M.main(['--report',str(p)]),0)
            self.assertIn('PID 41',out.getvalue())
            p.write_text('{"secret":"DO_NOT_ECHO"}')
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(M.main(['--report',str(p)]),1)
            self.assertEqual(out.getvalue(),'');self.assertNotIn('DO_NOT_ECHO',err.getvalue())

    def test_view_never_starts_process_or_imports_observer(self):
        with patch('subprocess.Popen',side_effect=AssertionError('NO_PROCESS')):
            self.assertIn('只读展示',M.render_report(fixture()))
        self.assertNotIn('linux_owned_file_observer',M.__dict__)


class TaskViewerTests(unittest.TestCase):
    def report(self):
        events=[]
        for seq,(op,domain,ret) in enumerate([('exec','runtime',0),('read','data',3),('read','data',0),('close','data',0)],1):
            a=dict(pid=41,start_ticks=101,syscall_seq=seq,operation=op,domain=domain,
                   path='/owned/x' if domain=='data' else 'APPROVED_RUNTIME_OBJECT',phase='ATTEMPT',
                   observed_monotonic_ns=seq*2,observed_wall_ns=1700000000000000000+seq*2)
            if domain=='data':a['fd']=0
            if op=='read':a['requested_bytes']=3
            b=dict(a,phase='RESULT',retval=ret,success=True,confirmed_positive_bytes=op=='read' and ret>0,
                   observed_monotonic_ns=seq*2+1,observed_wall_ns=a['observed_wall_ns']+1)
            events.extend([a,b])
        return dict(source='LINUX_COUNT_BYTES_TASK_V1',schema_version=1,task='count-bytes',
                    scope='ONE_INPUT_DIRECT_CHILD_NO_DESCENDANTS',status='PASS_SELECTED_COUNT_BYTES_TASK_WITH_LIMITS',
                    input_path='/owned/x',events=events,identity={'pid':41,'start_ticks':101},
                    input_size=3,observed_read_bytes=3,task_reported_bytes=3,exec_identity_verified=True,
                    contents_collected=False,all_descendants_or_all_files=False,
                    time_semantics='OBSERVER_ENTRY_EXIT_STOP_TIMES_NOT_ATOMIC_ACCESS_TIME',
                    cleanup={'returncode':0,'kill':False,'pidfd':'CLOSED','input_fd':'CLOSED','stdout':'CLOSED'})
    def test_task_report_versioned_and_old_still_works(self):
        self.assertIn('客户文件字节统计',M.render_report(self.report()))
        self.assertIn('自有固定任务',M.render_report(fixture()))
    def test_task_count_conflict_cannot_display_pass(self):
        for key,val in [('task_reported_bytes',4),('observed_read_bytes',0),('exec_identity_verified',False)]:
            r=self.report();r[key]=val
            with self.subTest(key=key),self.assertRaises(M.InvalidReport):M.render_report(r)
    def test_task_missing_data_or_cleanup_unknown_rejected(self):
        r=self.report();r['cleanup']['input_fd']='CLOSE_UNKNOWN'
        with self.assertRaises(M.InvalidReport):M.render_report(r)
        r=self.report();r['events'].pop()
        with self.assertRaises(M.InvalidReport):M.render_report(r)
    def test_failed_task_partial_record_stays_unknown(self):
        r=self.report();r['status']='NOT_PASS';r['events']=[];r['observed_read_bytes']=None;r['cleanup']={}
        self.assertIn('缺失或不完整，保持UNKNOWN',M.render_report(r))
    def test_task_expanded_scope_or_unknown_domain_rejected(self):
        r=self.report();r['scope']='ALL_FILES'
        with self.assertRaises(M.InvalidReport):M.render_report(r)
        r=self.report();r['events'][0]['domain']='secret'
        with self.assertRaises(M.InvalidReport):M.render_report(r)


if __name__ == '__main__':
    unittest.main()
