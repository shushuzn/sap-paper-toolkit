# sap-paper-toolkit

把中文学术论文的写作约束拆成两半：能写成规则的进 skill，能机械验证的写成脚本。用于在交付前把"看上去没问题"变成"逐项核过"。

仓库只有这一套文件。规则集与脚本都改在这里，安装位置由 `skills/sync_skill.sh` 镜像生成，不作为第二份源维护。

## 不含什么

本仓库不含任何具体论文的正文、成稿、机构格式文件、作者与年份信息。规则文件里的参数是通用量级，实际使用须以任务方提供的原件核对；排版函数库只提供函数，不提供任何论文的题名、表格与公式内容。规范编号一律不写死，按领域向原文核对。

## 内容

| 路径 | 作用 |
|---|---|
| `docx_style.py` | python-docx 的中文科技论文排版函数库：字体组合、富文本上下标、三线表、OMML 公式、页脚页码 |
| `demo.py` | 上面函数库的最小示例，生成 `demo.docx` |
| `audit_doc.py` | 源文件结构检查：摘要与关键词、标题编号连续性、图表与公式引用、缩略语首次出现 |
| `audit_refs.py` | 文献表自查：键名重复、著录字段完整性、类型标识缺失 |
| `xcheck_refs.py` | 按题名向 Crossref 回查每条文献的元数据，逐字段比对，结果写 `xcheck_report.json` |
| `count_words.py` | 用 Word 自身的统计口径统计正文（引言至结论）的字数、字符数、页数 |
| `paper_data.example.py` | 数据层模板：文献表与表格数据，供上面几个脚本读取 |
| `skills/academic-paper-improvement/` | 写作与审校规则集：六条硬性禁令、证据四级、诊断流程、反编造核验、仓库卫生 |
| `skills/academic-paper-improvement/scripts/selftest.py` | 规则自检：禁令列举与检测器词表、正则是否仍然一致 |
| `skills/sync_skill.sh` | 把仓库里的 skill 镜像到本地安装位置，支持 install／check／diff／pull |
| `.githooks/pre-commit` | 提交拦截：草稿备份、临时渲染件、超 2 MB 文件、skill 与安装位置漂移、规则自检 |

## 依赖

```
pip install python-docx
```

`count_words.py` 另需 `pywin32`，且只能在装有 Microsoft Word 的 Windows 上运行。其余脚本只用标准库。

## 快速开始

```bash
cp paper_data.example.py paper_data.py    # 填入自己的文献表
python audit_refs.py                      # 文献表自查
python demo.py                            # 生成 demo.docx，看排版效果
python skills/academic-paper-improvement/scripts/audit_manuscript.py demo.docx
python skills/academic-paper-improvement/scripts/selftest.py   # 规则自检
```

`audit_manuscript.py` 的字数与文献下限由命令行给定，默认值只作演示，短示例会报 FAIL，属预期。

## 自己写稿件时怎么接

排版函数库不绑定任何输入格式，直接调用即可：

```python
from docx import Document
from docx_style import para, three_line_table, add_page_number_footer, HEI, KAI, SONG

doc = Document()
add_page_number_footer(doc.sections[0])
para(doc, "题名", HEI, size=16, bold=True)      # 字体、字号、加粗按需给
para(doc, "正文含上标 x^{2} 与下标 y_{0}")      # add_rich 自动解析
three_line_table(doc, data, "表 1　题名", [3.2, 5.4, 5.4])
doc.save("out.docx")
```

`audit_doc.py` 读 Markdown 源文件（默认 `manuscript.md`，可传路径），约定：一级标题 `# 1 引言`，二级 `## 2.1 …`，摘要段以 `## 摘要` 开头，关键词行以 `关键词` 开头，文献引用写 `[@键名]`。缩略语表与文献总条数由同目录 `paper_data.py` 的 `ABBR`、`REF_TOTAL` 提供，未提供则跳过。

## skill 怎么用

规则集是纯 Markdown，任何能读文件的助手都能用。若使用支持 skill 目录的工具，镜像一次即可：

```bash
sh skills/sync_skill.sh install              # 镜像到 ~/.workbuddy/skills/
sh skills/sync_skill.sh check                # 检查安装位置是否与仓库一致
sh skills/sync_skill.sh install --dry-run    # 只报告，不写入
sh skills/sync_skill.sh pull --yes           # 把安装位置的临时改动收回仓库
```

镜像语义保证双向一致：安装位置多余的文件会被删除，避免长期残留已从仓库移除的旧文件。改了安装位置却没回写仓库时，`check` 返回 1，`pre-commit` 会阻止提交。启用钩子：

```bash
git config core.hooksPath .githooks
```

规则集的核心是六条硬性禁令（禁教学口吻称谓、禁破折号、禁脚本批量替换正文、禁以教学材料作数据与引用来源、禁全量暂存提交、禁对偶否定句式），以及证据四级：逐字、量级、可复算、定性。摘要与结论只能取全文最弱的那条证据，论断强度不得超过证据强度。

## 规则怎么落地

规则写在 Markdown 里，只有一部分能机械判断。下表把每条禁令对应的执行点写清楚，包括没有检查手段的那两条：分不清「已检查」与「只是写了」，是这类规则集最常见的失效方式。

| 禁令 | 机械检查 | 执行点 |
|---|---|---|
| 1 教学场景类称谓 | 有，FAIL | `check_prohibited()`，代号 F5，逐词扫描正文、题注、注释 |
| 2 破折号「——」 | 有，FAIL | `check_prohibited()`，代号 F6；单字连接号「—」不触发 |
| 3 禁脚本批量替换正文 | 无 | 改稿过程本身无法检测。可查的只有结果：审校记录须给出原文与改后的逐处对照 |
| 4 教学材料作数据或引用来源 | 部分 | `check_teaching_refs()`，代号 R7，扫文献表；钩子第 3 项挡住教学材料目录入库 |
| 5 禁 `git add -A` | 无 | 钩子运行时暂存已完成，判不出用什么命令暂存。只能拦结果：草稿备份、临时件、超限体积、目录违规 |
| 6 对偶否定句式 | 有，FAIL | `check_pairwise()`，代号 F7，九条正则对应九种形态 |

`selftest.py` 针对这张表做自检，三类断言：

- **正样本**：词表里每个禁词、九种形态各一句，必须命中。
- **负样本**：改写后的干净句子、单个连接号「—」、正常文献条目，必须不命中。
- **文档对齐**：禁令条数与节标题一致、形态数与 `PAIRWISE` 长度一致、形态名双向同集、词表每个词都在禁令 1 的列举里。

第三类来自一次实际教训：列举补到九种，计数仍写旧数，几处同时写错，而当时的全部核验都是通过的。现在这类漂移会在 `selftest.py` 与 `pre-commit` 第 7 项同时报出。

```bash
python skills/academic-paper-improvement/scripts/selftest.py           # 逐条打印
python skills/academic-paper-improvement/scripts/selftest.py --quiet   # 只打印失败项
```

改动规则集时，先改列举再改检测器，最后跑自检。反过来的顺序会让自检在中间状态下失败，属预期。

## 已知限制

- `count_words.py` 只能在 Windows + Word 环境运行；其他平台可跳过，改用 `audit_manuscript.py` 的汉字统计。
- `xcheck_refs.py` 依赖 Crossref 的题名匹配，中文文献与规范类文件通常查不到，会报"未匹配"，属预期行为。它的 User-Agent 带联系邮箱可获得更宽松的速率限制，用环境变量设置：`CROSSREF_MAILTO=you@example.com python xcheck_refs.py`。
- python-docx 每次生成的 .docx 字节级不一致（文档属性里带生成时间），比较内容请比字数与结构，不要比 md5。
- 正则检测只能拦住列举过的形态。新出现的表述要补规则；补完跑 `selftest.py`，正样本必须命中、负样本必须不命中，两份都过了才算补上。这条是实测教训：首版正则漏掉一种形态，它既不被相邻形态匹配，也不被主形态匹配，读一遍正则看不出问题。

## 许可

MIT，见 `LICENSE`。
