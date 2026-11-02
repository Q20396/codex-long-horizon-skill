"""Read one explicitly selected bounded report; never start an observer or task."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import PurePosixPath
import stat
import sys

MAX_BYTES = 16384
MAX_EVENTS = 32
MAX_TASK_BYTES = 32768


class InvalidReport(Exception):
    pass


def need(ok, code):
    if not ok:
        raise InvalidReport(code)


def integer(value):
    return type(value) is int and -(1 << 63) <= value < (1 << 63)


def unique_object(items):
    result = {}
    for key, value in items:
        need(key not in result, 'DUPLICATE_FIELD')
        result[key] = value
    return result


def reject_constant(_):
    raise InvalidReport('NONFINITE_NUMBER')


def load_report(path):
    """Bounded one-file read; no directory traversal or monitor import."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode), 'NOT_REGULAR')
        need(0 < before.st_size <= MAX_TASK_BYTES, 'REPORT_SIZE')
        raw = os.read(fd, before.st_size + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(before, f) == getattr(after, f) for f in fields), 'REPORT_CHANGED')
        need(len(raw) == before.st_size, 'SHORT_OR_CHANGED_READ')
    finally:
        os.close(fd)
    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                         parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidReport('REPORT_JSON') from None
    if type(obj) is dict and obj.get('source') != 'LINUX_COUNT_BYTES_TASK_V1':
        need(len(raw) <= MAX_BYTES, 'LEGACY_REPORT_SIZE')
    return obj


def quoted(value):
    # Escape terminal control codes and non-ASCII path text; never interpret markup.
    return json.dumps(value, ensure_ascii=True)


def utc_time(ns):
    seconds, fraction = divmod(ns, 1_000_000_000)
    return datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%d %H:%M:%S') + '.%09d UTC' % fraction


def render_report(r):
    """Validate before any output. This is display validation, not acceptance."""
    need(type(r) is dict, 'REPORT_SHAPE')
    if r.get('source') == 'LINUX_COUNT_BYTES_TASK_V1':
        return render_task_report(r)
    need(r.get('source') == 'LINUX_PTRACE_OWNED_DIRECT_CHILD', 'SOURCE')
    need(r.get('scope') == 'SINGLE_THREAD_TWO_ABSOLUTE_SYNTHETIC_LEAVES', 'SCOPE')
    need(r.get('status') in ('NOT_PASS', 'PASS_SELECTED_OWNED_SYSCALL_MATRIX_WITH_LIMITS'), 'STATUS')
    need(r.get('time_semantics') == 'OBSERVER_ENTRY_EXIT_STOP_TIMES_NOT_ATOMIC_ACCESS_TIME', 'TIME_SEMANTICS')
    need(r.get('contents_collected') is False and r.get('all_descendants_or_all_files') is False, 'BOUNDARY')
    root = r.get('test_root')
    need(type(root) is str and 0 < len(root.encode()) <= 4096
         and PurePosixPath(root).is_absolute() and '..' not in root.split('/'), 'ROOT')
    paths = {root + '/synthetic.txt', root + '/absent.txt'}
    events = r.get('events')
    need(type(events) is list and len(events) <= MAX_EVENTS, 'EVENTS')
    identity = r.get('identity')
    if events:
        need(type(identity) is dict and all(integer(identity.get(k)) and identity[k] > 0
             for k in ('pid', 'start_ticks')), 'IDENTITY')
    rows = []
    previous = 0
    labels = {'open': '打开', 'read': '读取', 'write': '写入', 'close': '关闭'}
    for e in events:
        need(type(e) is dict and e.get('operation') in labels
             and e.get('phase') in ('ATTEMPT', 'RESULT'), 'EVENT_SHAPE')
        need(e.get('path') in paths, 'PATH_SCOPE')
        need(e.get('pid') == identity['pid'] and e.get('start_ticks') == identity['start_ticks'], 'EVENT_IDENTITY')
        need(integer(e.get('syscall_seq')) and e['syscall_seq'] > 0, 'SEQUENCE')
        mono, wall = e.get('observed_monotonic_ns'), e.get('observed_wall_ns')
        need(integer(mono) and mono >= previous and integer(wall) and 0 < wall <= 8_000_000_000_000_000_000, 'EVENT_TIME')
        previous = mono
        action = labels[e['operation']]
        if e['phase'] == 'ATTEMPT':
            outcome = '尝试（尚无成功结论）'
        else:
            retval = e.get('retval')
            need(integer(retval) and type(e.get('success')) is bool, 'RESULT_SHAPE')
            need(e['success'] == (retval >= 0), 'RESULT_CONFLICT')
            need(e.get('errno') is None if e['success'] else
                 integer(e.get('errno')) and e['errno'] == -retval, 'ERRNO_CONFLICT')
            expected = e['success'] and e['operation'] in ('read', 'write') and retval > 0
            need(type(e.get('confirmed_positive_bytes')) is bool
                 and e['confirmed_positive_bytes'] == expected, 'COUNT_CONFLICT')
            if e['operation'] in ('read', 'write'):
                requested = e.get('requested_bytes')
                need(integer(requested) and requested >= 0
                     and (not e['success'] or retval <= requested), 'BYTE_COUNT')
            outcome = ('成功；返回%d字节' % retval if e['operation'] in ('read', 'write')
                       else '成功；返回值%d' % retval) if e['success'] else '失败；errno=%d' % e['errno']
        rows.append('%s | PID %d | %s | %s | %s' %
                    (utc_time(wall), e['pid'], action, quoted(e['path']), outcome))
    complete = len(events) == 14
    if complete:
        for a, b in zip(events[::2], events[1::2]):
            complete = complete and a['phase'] == 'ATTEMPT' and b['phase'] == 'RESULT' and all(
                a[k] == b[k] for k in ('syscall_seq', 'path', 'operation'))
        complete = complete and [e['operation'] for e in events[::2]] == ['open','read','close','open','write','close','open']
    need(r['status'] == 'NOT_PASS' or complete, 'SUCCESS_WITH_MISSING_EVENTS')
    cleanup = r.get('cleanup')
    need(type(cleanup) is dict, 'CLEANUP')
    child = cleanup.get('returncode')
    need(child is None or integer(child), 'CLEANUP_RETURN')
    for key in ('pidfd', 'fixture_fd'):
        need(cleanup.get(key) in (None, 'CLOSED', 'CLOSE_UNKNOWN'), 'CLEANUP_FD')
    if r['status'].startswith('PASS_'):
        results = events[1::2]
        need(all(e['success'] for e in results[:-1])
             and results[1]['retval'] == results[4]['retval'] == 1
             and all(e['path'] == root + '/synthetic.txt' for e in events[:-2])
             and all(e['path'] == root + '/absent.txt' for e in events[-2:])
             and results[-1]['success'] is False and results[-1]['errno'] == 2,
             'SUCCESS_MATRIX_CONFLICT')
        need(child == 0 and cleanup.get('kill') is False
             and cleanup.get('pidfd') == cleanup.get('fixture_fd') == 'CLOSED',
             'SUCCESS_CLEANUP_CONFLICT')
    lines = ['Linux自有固定任务报告（只读展示，不重新验收）',
             '报告自述：' + ('选定矩阵通过' if r['status'].startswith('PASS_') else '未通过'),
             '事件：%d条；配对结构：%s' % (len(events), '完整' if complete else '缺失或不完整，保持UNKNOWN'),
             '时间为观察器停止点读数，不是访问瞬间的原子时间。', *rows,
             '清理：子进程退出=%s；pidfd=%s；夹具FD=%s' %
             (str(child) if child is not None else 'UNKNOWN', cleanup.get('pidfd') or 'UNKNOWN', cleanup.get('fixture_fd') or 'UNKNOWN'),
             '报告写入尾部：UNKNOWN；本工具不验证来源签名、历史哈希或当前进程状态。',
             '范围仅限固定自有任务和两条合成文件路径，不代表任意任务、macOS或全盘监控。']
    return '\n'.join(lines) + '\n'


def render_task_report(r):
    need(type(r.get('schema_version')) is int and r['schema_version'] == 1 and r.get('task') == 'count-bytes'
         and r.get('scope') == 'ONE_INPUT_DIRECT_CHILD_NO_DESCENDANTS', 'TASK_VERSION_SCOPE')
    need(r.get('status') in ('NOT_PASS','PASS_SELECTED_COUNT_BYTES_TASK_WITH_LIMITS'), 'TASK_STATUS')
    need(r.get('contents_collected') is False and r.get('all_descendants_or_all_files') is False
         and r.get('time_semantics') == 'OBSERVER_ENTRY_EXIT_STOP_TIMES_NOT_ATOMIC_ACCESS_TIME', 'TASK_BOUNDARY')
    path = r.get('input_path')
    need(type(path) is str and PurePosixPath(path).is_absolute() and '..' not in path.split('/')
         and 0 < len(path.encode()) <= 4096, 'TASK_PATH')
    events = r.get('events');need(type(events) is list and len(events) <= 96,'TASK_EVENTS')
    ident = r.get('identity',{})
    need(type(ident) is dict, 'TASK_IDENTITY')
    if events:
        need(all(integer(ident.get(k)) and ident[k] > 0 for k in ('pid','start_ticks')), 'TASK_IDENTITY')
    labels={'exec':'启动任务','open':'打开','read':'读取','close':'关闭','access':'访问检查','seek':'移动位置'}
    rows=[];previous=0;reads=0;eof=False
    for e in events:
        need(type(e) is dict and e.get('operation') in labels and e.get('phase') in ('ATTEMPT','RESULT')
             and e.get('domain') in ('data','runtime'), 'TASK_EVENT_SHAPE')
        domain=e['domain'];op=e['operation']
        need(e.get('path') == (path if domain=='data' else 'APPROVED_RUNTIME_OBJECT'), 'TASK_EVENT_PATH')
        need(e.get('pid')==ident['pid'] and e.get('start_ticks')==ident['start_ticks'], 'TASK_EVENT_IDENTITY')
        mono,wall=e.get('observed_monotonic_ns'),e.get('observed_wall_ns')
        need(integer(mono) and mono>=previous and integer(wall) and 0<wall<=8_000_000_000_000_000_000
             and integer(e.get('syscall_seq')) and e['syscall_seq']>0, 'TASK_EVENT_TIME')
        previous=mono
        if domain=='data':need(op in ('read','close') and e.get('fd')==0,'TASK_DATA_OPERATION')
        outcome='尝试（尚无成功结论）'
        if e['phase']=='RESULT':
            ret=e.get('retval');ok=e.get('success')
            need(integer(ret) and type(ok) is bool and ok==(ret>=0), 'TASK_RESULT')
            need(type(e.get('confirmed_positive_bytes')) is bool
                 and e['confirmed_positive_bytes']==(ok and op=='read' and ret>0),'TASK_POSITIVE_COUNT')
            if op=='read':
                need(integer(e.get('requested_bytes')) and e['requested_bytes']>=0
                     and (not ok or ret<=e['requested_bytes']), 'TASK_READ_COUNT')
                if domain=='data':
                    need(not eof and ok,'TASK_DATA_READ_CONFLICT');reads+=ret;eof=ret==0
            outcome=('成功；返回%d字节'%ret if op=='read' else '成功；返回值%d'%ret) if ok else '失败；返回值%d'%ret
        rows.append('%s | PID %d | %s | %s | %s'%(utc_time(wall),e['pid'],labels[op],quoted(e['path']),outcome))
    complete=bool(events) and len(events)%2==0
    if complete:
        for a,b in zip(events[::2],events[1::2]):
            complete=complete and a['phase']=='ATTEMPT' and b['phase']=='RESULT' and all(
                a[k]==b[k] for k in ('syscall_seq','path','operation','domain'))
    cleanup=r.get('cleanup');need(type(cleanup) is dict,'TASK_CLEANUP')
    observed=r.get('observed_read_bytes')
    need(observed is None or integer(observed) and observed>=0,'TASK_OBSERVED_COUNT')
    if r['status'].startswith('PASS_'):
        size,count=r.get('input_size'),r.get('task_reported_bytes')
        need(complete and r.get('exec_identity_verified') is True
             and integer(size) and integer(count) and 0<=size<=65536
             and reads==observed==count==size and eof,'TASK_SUCCESS_CONFLICT')
        result_events=events[1::2]
        need(len([e for e in result_events if e['operation']=='exec' and e['retval']==0])==1
             and any(e['domain']=='data' and e['operation']=='close' and e['retval']==0 for e in result_events), 'TASK_EXEC_CLOSE_MISSING')
        need(cleanup.get('returncode')==0 and type(cleanup.get('returncode')) is int
             and cleanup.get('kill') is False
             and all(cleanup.get(k)=='CLOSED' for k in ('pidfd','input_fd','stdout')), 'TASK_SUCCESS_CLEANUP')
    lines=['Linux客户文件字节统计报告（只读展示，不重新验收）',
           '报告自述：'+('选定任务通过' if r['status'].startswith('PASS_') else '未通过'),
           '输入文件：'+quoted(path),
           '事件：%d条；配对结构：%s'%(len(events),'完整' if complete else '缺失或不完整，保持UNKNOWN'),
           '观察到的读取返回字节：'+(str(observed) if observed is not None else 'UNKNOWN'),*rows,
           '清理：子进程退出=%s；输入FD=%s；pidfd=%s；输出管道=%s'%(cleanup.get('returncode','UNKNOWN'),cleanup.get('input_fd','UNKNOWN'),cleanup.get('pidfd','UNKNOWN'),cleanup.get('stdout','UNKNOWN')),
           '时间仅为停止点观察；写入尾部UNKNOWN；未重新验证来源、签名或当前进程。',
           '仅count-bytes自有单子进程和授权文件；不是任意命令、macOS或全盘监控。']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='只读展示一份Linux自有固定任务JSON报告；不启动监控。')
    parser.add_argument('--report', required=True, help='明确指定的一份result.json；不扫描目录')
    args = parser.parse_args(argv)
    try:
        output = render_report(load_report(args.report))
    except (InvalidReport, OSError, ValueError, TypeError, KeyError, OverflowError):
        print('报告读取或校验失败；未展示内容，状态保持UNKNOWN。', file=sys.stderr)
        return 1
    print(output, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
