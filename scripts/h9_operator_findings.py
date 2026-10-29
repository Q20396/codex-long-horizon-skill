"""Repository-only inert presentation; caller supplies the existing core module.

No CLI, collection, persistence or authority. Normal Python module loading is
not an isolation boundary. Use only safe, synthetic opaque references.
"""
import json
from html import escape

from cross_layer_verification import VerificationFinding

__all__ = ('render_findings', 'render_findings_zh')
_FIELDS = ('action_id', 'layer_a', 'layer_b', 'result', 'effect_class',
           'effect_ref', 'reason', 'evidence_refs', 'coverage_status',
           'compared_effect_ref')
_OPTIONAL = ('effect_class', 'effect_ref', 'compared_effect_ref')
_HEADER = '''READ_ONLY_PRESENTATION
SOURCE_TRUST_NOT_ESTABLISHED
NOT_EXECUTION_OR_RETRY_AUTHORITY
MATCH is scoped agreement, not all-effects proof.
MISSING is expected evidence absent under the verifier's scoped coverage.
EXTRA is unexpected evidence under the verifier's scoped coverage.
DIVERGED is the verifier's unique material difference, not intent or causality.
UNKNOWN is missing or ambiguous evidence, not success.
NOT_OBSERVED is partial observation, not proof of no effect.
SCOPED_COMPLETE is scoped supplied coverage, not universal completeness.
PARTIAL and UNKNOWN coverage retain their original limits.
References are supplied opaque identifiers, not authenticated sources or freshness.
'''


def _reject():
    raise ValueError('H9_PRESENTATION_INPUT_INVALID') from None


def _row(finding):
    if type(finding) is not VerificationFinding:
        _reject()
    try:
        row = {name: object.__getattribute__(finding, name) for name in _FIELDS}
    except AttributeError:
        _reject()
    # Check exact primitive types BEFORE calling the existing core validator;
    # it must never compare, iterate, stringify or sort caller-defined objects.
    for name, value in row.items():
        if name == 'evidence_refs':
            if type(value) is not tuple or len(value) > 32:
                _reject()
            if any(type(ref) is not str or len(ref) > 132 for ref in value):
                _reject()
        elif value is None and name in _OPTIONAL:
            continue
        elif type(value) is not str or len(value) > 132:
            _reject()
    try:
        checked = VerificationFinding(**row)
    except (ValueError, TypeError):
        _reject()
    # Existing findings have canonical refs. Reject tampered/noncanonical values
    # rather than silently sorting/deduplicating or losing caller information.
    if checked.evidence_refs != row['evidence_refs']:
        _reject()
    return row


def render_findings(findings) -> str:
    """Return all ten fields in escaped JSON text rows, or one fixed error.

    One action; at most1024 rows and1MiB UTF-8. No partial output is returned.
    Input order and repeated findings are retained. No inference is added.
    """
    if (type(findings) is not list and type(findings) is not tuple) or len(findings) > 1024:
        _reject()
    parts = [_HEADER]
    size = len(_HEADER.encode('utf-8'))
    action = None
    for finding in findings:
        row = _row(finding)
        if action is not None and row['action_id'] != action:
            _reject()
        action = row['action_id']
        line = 'FINDING ' + json.dumps(row, ensure_ascii=True, separators=(',', ':')) + '\n'
        size += len(line.encode('utf-8'))
        if size > 1024 * 1024:
            _reject()
        parts.append(line)
    if not findings:
        parts.append('NO_FINDINGS_SUPPLIED\n')
    return ''.join(parts)


_ZH_RESULTS = {
    'MATCH': ('范围内相符', '本次提供的范围内，两层记录相符。',
              '不代表全部效果已验证，也不证明操作成功、文件内容正确或程序全部安全。'),
    'DIVERGED': ('记录有差异', '提供的两层记录存在具体差异。',
                 '不能据此认定恶意、攻击、未经授权或因果关系。'),
    'UNKNOWN': ('尚无法判断', '证据不足，效果可能已经发生。',
                '目前不能判定成功、失败或安全；未知不等于没有发生。'),
    'NOT_OBSERVED': ('未能观察到', '在本次提供的覆盖范围内，未能观察到对应效果。',
                     '未观察到不代表没有发生效果。'),
    'MISSING': ('预期证据缺失', '在本次比较范围内，预期的效果证据缺失。',
                '这是记录之间的比较，不证明实际操作未发生或可以重做。'),
    'EXTRA': ('存在额外证据', '在本次比较范围内，存在另一层未对应的效果证据。',
              '额外证据不自行证明未经授权、攻击或恶意。'),
}
_ZH_LAYERS = {'DECLARED': '声明记录', 'AUTHORIZED': '授权记录',
              'ADAPTER_OBSERVED': '适配器记录', 'HOST_OBSERVED': '主机观察记录',
              'TARGET_REALITY': '目标事实记录'}
_ZH_STYLE = '''
*{box-sizing:border-box}body{margin:0;background:#f5f7f8;color:#23363f;
font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
main{max-width:880px;margin:auto;padding:32px 20px}h1{font-size:26px}
.boundary,.card{background:white;border:1px solid #dae3e5;border-radius:12px;
padding:22px;margin:18px 0}.boundary{border-left:5px solid #486b80}
h2{margin:0;font-size:22px}h3{font-size:17px;margin:18px 0 4px}
p{margin:6px 0}.scope{background:#fff6df;padding:14px;border-radius:7px}
.next{background:#edf3f7;padding:14px;border-radius:7px}
details{border-top:1px solid #dae3e5;margin-top:20px;padding-top:12px}
summary{cursor:pointer}summary:focus-visible{outline:3px solid #486b80}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7f8;
padding:14px;font-size:13px}.meta{font-size:14px;color:#526771}
@media(max-width:600px){main{padding:16px 12px}.card,.boundary{padding:16px}}
'''


def render_findings_zh(findings) -> str:
    """Return inert standalone Chinese HTML for the same bounded synthetic input.

    No collection, execution, evidence authentication or retry authority. Native
    details elements hide technical fields by default; there is no script or IO.
    Both the original text contract and the final 1MiB HTML limit apply.
    """
    # Reuse the complete existing input validation, including canonical refs,
    # exact inert types, one action, order/duplicates and the original text cap.
    plain = render_findings(findings)
    rows = [json.loads(line[8:]) for line in plain.splitlines()
            if line.startswith('FINDING ')]
    parts = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
             'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
             '<title>只读检查报告</title><style>', _ZH_STYLE,
             '</style></head><body><main><h1>只读检查报告</h1>',
             '<aside class="boundary"><p>本页转述已提供的比较结论，不重新判定安全。</p>'
             '<p>不授予执行、重试或对账权限。证据来源与新鲜度未验证。</p>'
             '<p class="meta">不把引用标识解释为文件路径或文件内容；'
             '效果类型不证明操作已经发生。仅接受获准的非秘密合成输入。</p></aside>']
    for index, row in enumerate(rows, 1):
        title, event, limit = _ZH_RESULTS[row['result']]
        layers = _ZH_LAYERS[row['layer_a']] + ' → ' + _ZH_LAYERS[row['layer_b']]
        coverage = ('仅限本次已提供的覆盖范围，不是全局或全过程确认。'
                    if row['coverage_status'] == 'SCOPED_COMPLETE' else
                    '覆盖不足或未知，不能从缺少记录推断没有效果。')
        next_step = ('勿自动重试。请由已有权限的负责人核查原始记录与实际结果。'
                     if row['result'] in ('UNKNOWN', 'NOT_OBSERVED', 'MISSING') else
                     '如需判断实际结果或更大范围，请由已有权限的负责人核查原始证据。'
                     '不要据此自动修复或重试。')
        parts.extend(['<article class="card"><h2>记录 ', str(index), '：', title,
                      '</h2><h3>发生什么</h3><p>', event, '</p><p class="meta">比较层：',
                      escape(layers), '</p><h3>确认到哪里</h3><div class="scope"><p>',
                      limit, '</p><p>', coverage, '</p></div><h3>建议行动</h3>',
                      '<p class="next">', next_step, '</p>',
                      '<details><summary>技术详情与证据引用</summary>',
                      '<p>以下十个字段保持输入原义；引用不是已核实的证据原件。</p>',
                      '<pre class="raw">', escape(json.dumps(row, ensure_ascii=False, indent=2)),
                      '</pre></details></article>'])
    if not rows:
        parts.append('<section class="card"><h2>未提供检查结果</h2>'
                     '<p>不代表没有发生效果，也不代表成功或安全。</p></section>')
    parts.append('</main></body></html>')
    page = ''.join(parts)
    if len(page.encode('utf-8')) > 1024 * 1024:
        _reject()
    return page
