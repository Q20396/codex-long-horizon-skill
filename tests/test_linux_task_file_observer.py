"""Pure synthetic state transitions and temporary non-sensitive files only."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

S=importlib.util.spec_from_file_location('task_observer',Path(__file__).resolve().parents[1]/'scripts/linux_task_file_observer.py')
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.row={'path':'/usr/bin/wc','resolved_path':'/usr/bin/wc','device':1,'inode':7,'size':1,'sha256':'a'*64}
        self.runtime=M.RuntimeRows({'/usr/bin/wc':self.row});self.runtime.absent=frozenset(['/etc/ld.so.preload'])
        self.e=M.TaskEvidence({'pid':41,'start_ticks':7},'/owned/data.txt',{'device':1,'inode':8},3,self.runtime)
        self.tick=0
    def stamp(self):
        self.tick+=1;return self.tick,1700000000000000000+self.tick
    def entry(self,n,args,path=''):
        self.e.entry(n,args,self.stamp(),lambda _:path,lambda *a:None)
    def pair(self,n,args,ret,path='',error=0):
        self.entry(n,args,path);self.e.exit(ret,error,self.stamp(),lambda *a:None)
    def execute(self):
        self.entry(59,[123,0,0,0,0,0],'/usr/bin/wc');self.e.exec_stop(lambda _:None)
        self.e.exit(0,0,self.stamp(),lambda *a:None)
    def complete(self,size=3):
        self.execute()
        if size:self.pair(0,[0,999,size,0,0,0],size)
        self.pair(0,[0,999,100,0,0,0],0)
        self.pair(3,[0,0,0,0,0,0],0)
    def test_real_task_argv_not_fixed_synthetic_helper(self):
        self.assertEqual(M.ARGV,['/usr/bin/wc','-l','-c'])
        self.assertIn('os.execve',M.CHILD);self.assertNotIn('synthetic.txt',M.CHILD)
    def test_positive_count_from_observed_reads(self):
        self.complete();self.assertEqual(self.e.qualify(0,b'0 3\n'),3)
        self.assertEqual(self.e.read_bytes,3)
        self.assertEqual([x['retval'] for x in self.e.events if x['operation']=='read' and x['phase']=='RESULT'],[3,0])
    def test_zero_file_not_positive_read(self):
        self.e.size=0;self.complete(0);self.assertEqual(self.e.qualify(0,b'0 0\n'),0)
        self.assertFalse(any(x.get('confirmed_positive_bytes') for x in self.e.events if x['domain']=='data'))
    def test_count_self_report_never_replaces_read(self):
        self.execute();self.pair(0,[0,0,100,0,0,0],0);self.pair(3,[0,0,0,0,0,0],0)
        with self.assertRaises(M.Rejected):self.e.qualify(0,b'0 3\n')
    def test_short_reads_sum_and_no_buffer_copy(self):
        self.execute();self.pair(0,[0,999,3,0,0,0],1);self.pair(0,[0,999,3,0,0,0],2)
        self.pair(0,[0,999,3,0,0,0],0);self.pair(3,[0,0,0,0,0,0],0)
        self.assertEqual(self.e.qualify(0,b'0 3\n'),3)
        self.assertNotIn('999',json.dumps(self.e.events))
    def test_seek_or_data_write_rejected(self):
        for nr in (8,1):
            with self.subTest(nr=nr),self.assertRaises(M.Rejected):self.entry(nr,[0,0,1,0,0,0])
    def test_unknown_clone_vector_and_namespace_rejected(self):
        for nr in (56,19,272,999):
            with self.subTest(nr=nr),self.assertRaises(M.Rejected):self.entry(nr,[0]*6)
    def test_runtime_readonly_exact_paths(self):
        self.pair(257,[-100,12,os.O_CLOEXEC,0,0,0],3,'/usr/bin/wc')
        self.pair(0,[3,999,8,0,0,0],1);self.pair(3,[3,0,0,0,0,0],0)
        self.assertEqual(self.e.read_bytes,0)
        with self.assertRaises(M.Rejected):self.entry(257,[-100,12,os.O_WRONLY,0,0,0],'/usr/bin/wc')
    def test_runtime_absence_must_stay_absent(self):
        self.pair(21,[12,4,0,0,0,0],-2,'/etc/ld.so.preload',1)
        self.assertEqual(self.e.events[-1]['success'],False)
        self.entry(21,[12,4,0,0,0,0],'/etc/ld.so.preload')
        with self.assertRaises(M.Rejected):self.e.exit(0,0,self.stamp(),lambda *a:None)
    def test_unknown_path_never_in_events(self):
        with self.assertRaises(M.Rejected):self.entry(2,[1,0,0,0,0,0],'/PRIVATE_SENTINEL')
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(self.e.events))
    def test_data_mmap_and_unbound_runtime_mmap_rejected(self):
        for fd in (0,7):
            with self.subTest(fd=fd),self.assertRaises(M.Rejected):self.entry(9,[0,4096,1,2,fd,0])
    def test_exec_event_identity_and_repeat(self):
        self.entry(59,[1,0,0,0,0,0],'/usr/bin/wc')
        with self.assertRaises(RuntimeError):self.e.exec_stop(Mock(side_effect=RuntimeError('bad identity')))
        self.assertFalse(self.e.exec_event)
    def test_missing_events_and_output_rejected(self):
        with self.assertRaises(M.Rejected):self.e.exit(0,0,self.stamp(),lambda *a:None);self.e.exit(0,0,self.stamp(),lambda *a:None)
        self.e=M.TaskEvidence({'pid':41,'start_ticks':7},'/owned/data.txt',{},3,self.runtime);self.complete()
        for out in (b'3\n',b'0 4\n',b'0 secret\n',b'x'*129):
            with self.subTest(out=out),self.assertRaises(M.Rejected):self.e.qualify(0,out)
    def test_read_budget_and_failed_read(self):
        self.execute();self.entry(0,[0,0,3,0,0,0])
        with self.assertRaises(M.Rejected):self.e.exit(-5,1,self.stamp(),lambda *a:None)
    def test_prelaunch_default_and_wrong_os_never_spawn(self):
        with patch.object(M.subprocess,'Popen',side_effect=AssertionError('no spawn')),patch.object(M.ctypes,'CDLL',side_effect=AssertionError('no native')):
            with self.assertRaises(M.Rejected):M.run_task('/owned','x','manifest',None)
            with patch.object(M.sys,'platform','darwin'),self.assertRaises(M.Rejected):M.run_task('/owned','x','manifest','NEW_COUNT_BYTES_TASK_GRANTED')
    def test_leaf_escape_and_type_rejected_before_open(self):
        with patch.object(M.os,'open',side_effect=AssertionError('no open')):
            for name in ('../x','a/b','','..','x\x00'):
                with self.subTest(name=name),self.assertRaises(M.Rejected):M.open_input('/owned',name)
    def test_input_never_reads_content(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'nonsecret');p.chmod(0o600)
            with patch.object(M.B,'safe_parent'),patch.object(M.os,'read',side_effect=AssertionError('no input read')):
                fd,s,path=M.open_input(d,'x');os.close(fd);self.assertEqual(s.st_size,9)
    def test_input_symlink_and_overlimit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'x'*(M.MAX_INPUT+1));p.chmod(0o600);(Path(d)/'link').symlink_to(p)
            with patch.object(M.B,'safe_parent'):
                for name in ('x','link'):
                    with self.subTest(name=name),self.assertRaises((M.Rejected,OSError)):M.open_input(d,name)
    def test_manifest_exact_objects_no_auto_learning(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'m';p.write_text(json.dumps({'version':1,'executable':'/usr/bin/wc','objects':[self.row],'absent_paths':['/etc/ld.so.preload']}))
            r=M.load_runtime(p,{'device':-1,'inode':-1});self.assertEqual(set(r),{'/usr/bin/wc'});self.assertEqual(len(r.manifest_sha256),64)
            p.write_text('{"version":1,"version":1}')
            with self.assertRaises(M.Rejected):M.load_runtime(p,{'device':-1,'inode':-1})

    def test_runtime_hardlink_input_rejected_before_body_read(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'binary';p.write_bytes(b'nonsecret');p.chmod(0o600);st=p.stat()
            row=dict(self.row,resolved_path=str(p),device=st.st_dev,inode=st.st_ino,size=st.st_size)
            rows=M.RuntimeRows({'/usr/bin/wc':row})
            real=M.os.path.realpath
            with patch.object(M.os.path,'realpath',side_effect=lambda x:str(p) if x=='/usr/bin/wc' else real(x)),patch.object(M.os,'read',side_effect=AssertionError('no body read')):
                with self.assertRaises(M.Rejected):M.verify_runtime(rows,999999999,M.identity(st))

    def test_manifest_is_input_hardlink_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data';p.write_bytes(b'nonsecret');q=Path(d)/'manifest';os.link(p,q)
            with patch.object(M.os,'read',side_effect=AssertionError('no manifest body read')):
                with self.assertRaises(M.Rejected):M.load_runtime(q,M.identity(p.stat()))

    def test_invalid_clock_or_event_limit_not_success(self):
        with self.assertRaises(M.Rejected):self.e.emit('read','ATTEMPT','data',(False,1))
        self.e.events=[{}]*96
        with self.assertRaises(M.Rejected):self.e.emit('read','ATTEMPT','data',(1,1))

    def test_manifest_overlap_closes_input_and_never_launches(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'examples').mkdir();(root/'data').write_bytes(b'nonsecret');(root/'data').chmod(0o600)
            with patch.object(M.B,'safe_parent'),patch.object(M.sys,'platform','linux'),patch.object(M.sys,'version_info',(3,12,3)),patch.object(M.platform,'machine',return_value='x86_64'),patch.object(M.os,'pidfd_open',create=True),patch.object(M.signal,'pidfd_send_signal',create=True),patch.object(M.subprocess,'Popen',side_effect=AssertionError('no spawn')),patch.object(M.ctypes,'CDLL',side_effect=AssertionError('no native')),patch.object(M.os,'read',side_effect=AssertionError('no content read')):
                result,path=M.run_task(root,'data',root/'data','NEW_COUNT_BYTES_TASK_GRANTED',root)
            self.assertEqual(result['status'],'NOT_PASS');self.assertEqual(result['reason'],'INPUT_MANIFEST_OVERLAP')
            self.assertEqual(result['cleanup']['input_fd'],'CLOSED');self.assertTrue(path.is_file())

    def test_directory_close_failure_still_closes_input_once(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'nonsecret');p.chmod(0o600)
            actual_open=M.os.open;actual_close=M.os.close;seen=[];directory=[]
            def opening(*args,**kw):
                fd=actual_open(*args,**kw)
                if args[1] & M.os.O_DIRECTORY:directory.append(fd)
                return fd
            def closing(fd):
                seen.append(fd);actual_close(fd)
                if fd in directory:raise OSError('synthetic-directory-close')
            with patch.object(M.B,'safe_parent'),patch.object(M.os,'open',side_effect=opening),patch.object(M.os,'close',side_effect=closing):
                with self.assertRaises(OSError) as caught:M.open_input(d,'x')
            self.assertTrue(caught.exception.cleanup_unknown);self.assertEqual(len(seen),2);self.assertEqual(len(set(seen)),2)

    def test_metadata_primary_survives_both_close_failures(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'x'*(M.MAX_INPUT+1));p.chmod(0o600)
            actual_close=M.os.close;seen=[]
            def closing(fd):
                seen.append(fd);actual_close(fd);raise OSError('synthetic-close')
            with patch.object(M.B,'safe_parent'),patch.object(M.os,'close',side_effect=closing):
                with self.assertRaises(M.Rejected) as caught:M.open_input(d,'x')
            self.assertEqual(str(caught.exception),'INPUT_TYPE_SIZE_OWNER');self.assertTrue(caught.exception.cleanup_unknown)
            self.assertEqual(len(caught.exception.additional_close_kinds),2);self.assertEqual(len(set(seen)),2)

    def test_manifest_primary_survives_close_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'nonsecret');actual_close=M.os.close
            def closing(fd):actual_close(fd);raise OSError('synthetic-close')
            with patch.object(M.os,'close',side_effect=closing),patch.object(M.os,'read',side_effect=AssertionError('no body')):
                with self.assertRaises(M.Rejected) as caught:M.load_runtime(p,M.identity(p.stat()))
            self.assertEqual(str(caught.exception),'INPUT_MANIFEST_OVERLAP');self.assertTrue(caught.exception.cleanup_unknown)

    def test_interrupt_is_not_replaced_by_close_exception(self):
        primary=KeyboardInterrupt('synthetic')
        with patch.object(M.os,'close',side_effect=OSError('synthetic-close')) as close:
            with self.assertRaises(KeyboardInterrupt) as caught:
                with M.owned_fd(123):raise primary
        self.assertIs(caught.exception,primary);self.assertTrue(primary.cleanup_unknown);close.assert_called_once_with(123)

if __name__=='__main__':unittest.main()
