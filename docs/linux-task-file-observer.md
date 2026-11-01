# 客户非敏感文件：字节统计任务入口（准备候选，原生未运行）

## 实际支持与不支持

这次新增入口启动系统 `/usr/bin/wc` 处理客户明确选择的一个普通非敏感文件，不生成固定输入、不把旧synthetic.txt演示改名。客户任务只限字节统计，不接受任意命令、shell、PID、目录树或已运行程序，不支持后代／线程／数据写入。观察器不复制文件读写缓冲区，不扫描用户目录。

为避免 `wc -c` 在普通文件上只用大小／seek而不读取，固定参数是 **`wc -l -c`**，LC_ALL=C。行数只是强制完整处理的内部辅助，输出严格为两列数字，丢弃行数，只展示第二列字节数；没有增加公开行数功能。官方coreutils `src/wc.c` 的byte-only快捷路径与wc_lines读取循环支持该选择，但不是当前Ubuntu二进制实测。即使任务自己报告计数，也必须与实际FD0 read返回累计和输入长度相等，并观察到EOF、正常关闭和退出，才可能通过。零字节文件明确不代表正字节读取。

本候选没有进行新原生运行、CI、安装、sudo或提交推送。旧run41190316333只验证旧固定helper；本候选不能继承该通过。

## 客户将来如何使用

运行尚需新的精确许可、符合条件的Linux环境以及已批准的runtime清单；当前不要运行。接口模板：

```text
python3 -I -S -B scripts/linux_task_file_observer.py \
  --task count-bytes --directory /明确授权的非敏感目录 --input 文件名 \
  --runtime-manifest /已核验/runtime.json --run-once 新批准后提供的标识
```

这不是可直接复制执行的本次许可。普通文件必须直接位于该绝对目录，leaf不能含斜杠、反斜杠、NUL或..；不跟符号链接，不递归。目录及父链需可信、不可被其他用户写入；文件属当前用户、不可被其他用户写入、≤64KiB。请勿选择秘密、个人或财务资料。父进程仅检查输入metadata，持有只读FD，将其绑定为唯一自有child的stdin；输入内容只供客户授权任务读取，不由观察器保存。

通过／失败均返回报告位置（若报告写入本身失败则固定报错并保留UNKNOWN）；报告独占写入项目examples/count-bytes-*新目录，不覆盖已有材料。可用现有查看入口读取这一份报告：

```text
python3 -I -S -B scripts/show_linux_owned_report.py --report /本次返回的路径/result.json
```

展示读取不等于真实性／签名验证或独立验收。新报告schema_version=1/source=LINUX_COUNT_BYTES_TASK_V1，旧格式继续分开处理。未知、缺失事件和清理异常不改写为PASS；输出计数只作为任务自述，不能替代实际访问证据。

## runtime清单与尚缺的真实材料

新任务会exec系统程序，并涉及内核加载的动态解释器和loader打开的库／缓存。必须在启动前提供一个只读、≤8KiB的显式清单，不能从看到的路径动态学习或自动批准，也不能豁免整个/lib、/etc。结构：

```json
{"version":1,"executable":"/usr/bin/wc","objects":[
  {"path":"/usr/bin/wc","resolved_path":"/usr/bin/wc","device":0,"inode":0,"size":0,"sha256":"替换为实际64位小写摘要"}
],"absent_paths":["/etc/ld.so.preload"]}
```

上面只是**无效占位结构**，不得作为真实清单。最多8个精确普通runtime对象，总正文校验≤32MiB，另最多8条明确预先批准的缺失路径。每项含准确path／canonical resolved_path、device／inode／size／SHA256；alias先核实际解析对应，随后同FD初末metadata和摘要核验。先只检查输入metadata，清单文件本身或任何runtime项与输入dev/inode相同（包括硬链接）都在读取正文之前拒绝；父进程只允许对已列明runtime对象校验正文，不得把输入当runtime读。

exec事件还核/proc原child/exe及有界maps，将内核加载的解释器映射与已钉对象对应。runtime open只读、FD对象精确绑定；file-backed mmap仅限已绑定runtimeFD，禁止dataFD0映射／seek／write／dup等旁路。明确缺失对象只有预先列明且实际ENOENT才接受；新路径、路径变更或不支持syscall失败关闭。

**当前缺少目标Linux域这一份真实对象／alias／缺失路径清单和来源绑定。** 本轮没有创建假pin，也没有执行Linux探针获取它；不能据文档猜测完整依赖闭包或把新清单当历史可信身份。准备真实运行前应在同一已授权Linux域仅对事先固定的具体runtime路径做有限资格采集，形成可审阅清单；若需发现新路径，不自动扩大范围。

## 身份、生命周期与证据

同一原Popen子进程，从bootstrap TRACEME/SIGSTOP、固定一次exec至退出；PID/start_ticks、pidfd、单线程和同mount namespace持续核验。启动前Python导入阶段不在声明覆盖内。exec后的事件与输入FD0、路径／device／inode及syscall entry/result关联，记录停止点monotonic／UTC观察时间，不是访问瞬间的原子证明。

仅在正常EOF、输入未变、业务数字=实际read累计=输入长度、无未关闭追踪FD且原进程正常退出时可形成选定通过。任务失败或证据不足保留NOT_PASS／UNKNOWN。普通read短读可累计，失败read停止；runtime读取与data读取分域，不能计入客户文件读取。输入不写入、不删除或覆盖。

clone／fork／线程／exec第二次／namespace／共享FD及未知syscall拒绝，不自动跟踪或杀后代。合作文件系统、无并发输入修改／mount变化和唯一waiter／无外部reaper是边界；停止不自动证明原子身份或敌对宿主安全。

程序软件目标30秒、观察≤8秒、预留5秒清理；受阻I/O／最终落盘不保证硬抢占。失败最多对已绑定pidfd或未回收原Popen一次kill，剩余预算内最多2秒wait；逐项关闭输入FD、pidfd与stdout，异常保留UNKNOWN，首异常／中断不被收尾替换。不操作任意数字PID或进程组。

最多32个data read结果，最多96条必要事件、结果≤32KiB、数字stdout≤128B；超限NOT_PASS，不裁剪成成功，无法完整落盘时证据不完整。输入文件不hash、不读正文；输出stdout只严格解析数字、不保存原文，stderr丢弃。运行时路径仅显示固定分类，未知路径不回显。

## 固定准备验收与未来最小运行请求

准备验证包括：真实任务argv与参数、普通／零字节、短读累计与自述计数不匹配、路径／链接／大小／对象／runtime硬链接重叠、未知FD／mmap／seek／write／clone／syscall、exec身份与重复事件、EOF／close／退出／清理、超额与失败显示、新旧报告隔离。合成测试只用自有临时夹具和mock，不启动任务、ptrace或监控。

本轮五文件范围内实现／合成／静态／独立复核允许；原观察器和workflow不改。真正启动前仍须：最终候选哈希、实际独立审阅、准确runtime清单及Linux权限／成本／来源条件，并另批一次运行。不得复用旧许可。

最小未来验证设计：一个标准Ubuntu24.04 x64 job≤5分钟，无安装／提权／artifact/cache，费用上限0；新单次批次最多3案（自有非敏感普通输入、零字节边界、前置拒绝），每案观察≤8秒／程序目标30秒，累计含留证≤120秒，任一失败即停止后续、不重试。计数任务仍是真实系统程序，但这些自建输入只验证机制，不能冒称客户真实文件任务验收。

目前不能给出可执行真实命令：runtime清单尚未取得，且本轮无CI控制变更／提交推送授权。下一项必要追加范围是一个专用CI控制文件（本轮五文件外），用于固定路径资格采集和三案单次验证；应先冻结该控制文件及资格路径／alias清单并独立审阅，再申请对应签名提交、首次推送及一次job。不是请求泛泛继续研究，不先启动或自动发现路径。若用户已有获准Linux域，可直接提供非秘密runtime清单及其来源，不索密码或token。


## Bounded compatibility batch diagnostic (2026-11-01)

Unknown calls remain rejected. The report may include only the rejected syscall number, verified Linux x86_64 ABI, ENTRY stage, and fixed UNKNOWN FD-domain. No raw syscall arguments, pointers, buffer values or file content are copied. Until official semantics of the actual number are known, an argument cannot be interpreted as a file descriptor. This diagnostic is not successful access evidence. The batch ledger remains bounded to three new CI runs; old permissions are not restored.


## R2 runtime pread64 compatibility (2026-11-02)

Batch R1 captured syscall17 with verified Linux x86_64 ABI. Linux v7.0 syscall_64.tbl names this pread64; Linux man-pages pread(2) states that it reads from an explicit offset without changing file position, and returns actual bytes (possibly short). This does not prove the rejected call used a runtime FD: R1 did not capture arguments. R2 therefore conditionally supports only already tracked, identity-revalidated, pinned read-only runtime FDs, with the requested extent wholly inside the pinned runtime object. Input FD0, stdout/stderr, unknown FDs and outside extents remain rejected. No syscall is added to SAFE, no path is learned and no buffer contents or raw offset are emitted. Result events are marked POSITIONAL_RUNTIME; their bytes never count as input reads/EOF. The unchanged sequential-input read/count/EOF/close/exit/cleanup acceptance still applies.

Primary references: https://raw.githubusercontent.com/torvalds/linux/v7.0/arch/x86/entry/syscalls/syscall_64.tbl ; https://man7.org/linux/man-pages/man2/pread.2.html . These establish interface semantics, not installed-library provenance or a successful R2 run.
