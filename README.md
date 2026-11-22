# sap-paper-toolkit

把中文学术论文的写作约束拆成两半：能写成规则的进 skill，能机械验证的写成脚本。用于在交付前把"看上去没问题"变成"逐项核过"。

仓库只有这一套文件。规则集与脚本都改在这里，安装位置由 `skills/sync_skill.sh` 镜像生成，不作为第二份源维护。

## 不含什么

本仓库不含任何具体论文的正文、成稿、机构格式文件、作者与年份信息。规则文件里的参数是通用量级，实际使用须以任务方提供的原件核对；排版函数库只提供函数，不提供任何论文的题名、表格与公式内容。规范编号一律不写死，按领域向原文核对。

这条约束不只靠自觉。`pre-commit` 第 8 项做两项通用检查：四位年份（豁免 XML 命名空间与 URI 这类标准标识）、规范代号实体（代号紧跟序号）。机构名、院系名、人员名、产品型号、校内项目编号无法通用判定，写进根目录的 `.publish-deny`，一行一个正则，由钩子逐条拦截。该文件本身已被 `.gitignore` 排除：为了拦截而把敏感词写进公开仓库，是这类约束最常见的自毁方式。

## 内容

| 路径 | 作用 |
|---|---|
| `docx_style.py` | python-docx 的中文科技论文排版函数库：字体组合、富文本上下标、三线表、OMML 公式、页脚页码 |
| `demo.py` | 上面函数库的最小示例，生成 `demo.docx` |
| `manuscript_io.py` | 各核验脚本共用的定位与解析层：稿件与数据层的查找、章节切分、文献条目拆分 |
| `audit_doc.py` | 结构检查：源文件查摘要与关键词、标题层级、引文键名；成稿查图表与公式编号、引文编号 |
| `audit_refs.py` | 文献条目审计：类型标识、作者段、卷期页、标点、编号连续性，条目可取自数据层或稿件文献段 |
| `xcheck_refs.py` | 按题名向 Crossref 回查每条文献的元数据，逐字段比对，结果写 `xcheck_report.json` |
| `count_words.py` | 正文篇幅统计，两条通道：直接解析文本，或调用本机文字处理软件的统计口径 |
| `paper_data.example.py` | 数据层模板：文献表与表格数据，供上面几个脚本读取 |
| `skills/academic-paper-improvement/` | 写作与审校规则集：六条硬性禁令、证据四级、诊断流程、反编造核验、仓库卫生 |
| `skills/academic-paper-improvement/scripts/selftest.py` | 规则自检：禁令列举与检测器词表、正则是否仍然一致 |
| `skills/sync_skill.sh` | 把仓库里的 skill 镜像到本地安装位置，支持 install／check／diff／pull，skill 名自动识别 |
| `.publish-deny.example` | 本地禁用词表模板：机构名、人员名这类无法通用判定的词，复制为 `.publish-deny` 后由钩子拦截 |
| `.githooks/pre-commit` | 提交拦截：草稿备份、临时渲染件、超 2 MB 文件、skill 与安装位置漂移、规则自检、公开版禁用内容 |

## 依赖

```
pip install python-docx
```

`count_words.py` 的 word 通道另需 `pywin32`，且只能在装有 Microsoft Word 的 Windows 上运行；plain 通道只用标准库，跨平台可用。其余脚本只用标准库。

## 快速开始

```bash
cp paper_data.example.py paper_data.py    # 填入自己的文献表
python audit_refs.py                      # 文献条目审计
python audit_doc.py manuscript.md         # 源文件结构检查
python count_words.py --engine plain      # 篇幅统计（不依赖 Word）
python demo.py                            # 生成 demo.docx，看排版效果
python skills/academic-paper-improvement/scripts/audit_manuscript.py demo.docx
python skills/academic-paper-improvement/scripts/selftest.py   # 规则自检
```

`audit_manuscript.py` 的字数与文献下限由命令行给定，默认值只作演示，短示例会报 FAIL，属预期。

## 排版函数库怎么用

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

## 核验脚本怎么接稿件

四个核验脚本共用 `manuscript_io.py`，位置与结构都不写死：

- **稿件位置**：位置参数 → 环境变量 `PAPER_SRC` → 当前目录唯一的 `.md`/`.docx`。多个候选时脚本会报错并列出，不替你猜。
- **数据层位置**：`--data` → 环境变量 `PAPER_DATA` → 当前目录的 `paper_data.py`。找不到就跳过依赖数据层的检查，不填默认值。
- **两种模式**：稿件带 Markdown 标题标记时走结构模式，检查摘要、关键词、标题层级，引文按键名比对文献表；没有标记（如 `.docx` 成稿）时走成稿模式，跳过需要标题的检查，改查图表与公式编号、引文编号是否连续与越界。两种模式都不预设编号数量，按正文实际提及统计。
- **章节叫法**：默认名是体裁通用叫法。稿件用别的叫法时，在数据层写 `SECTIONS` 覆盖，不必改脚本：

```python
SECTIONS = {
    "abstract_cn": ("提要",),          # 默认 ("摘要",)
    "keywords_cn": ("关键字",),        # 默认 ("关键词",)
    "abstract_en": ("Summary",),       # 默认 ("Abstract",)
    "keywords_en": ("Index Terms",),   # 默认 ("Key words", "Keywords")
    "references": ("引用文献",),        # 默认 ("参考文献", "References")
}
```

数据层还可选给 `ABBR`（缩略语清单，查首次出现）、`REF_TOTAL`（文献总条数，查缺号与越界）。不给这两项时对应检查跳过，其余照常。

成稿模式的正文分界按"参考文献"字样定位。若成稿里没有这个字样，整篇都按正文统计，脚本会提示该情形下编号检查偏松。

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

表外还有几组不属于禁令、但可机械判定的检查：`W1` 风险表述（应试语、第一人称、无出处断言、绝对化）、`W2` 元话语（交代写作安排、宣告写作决策、代替读者判断、模糊回指）、`A1–A5` 摘要体裁（免责声明、来源交代、引注标记、图表指引、英文免责）、`B1–B3` 规范状态与证据等级。

`A` 组只扫摘要区，起于「摘要」或「Abstract」，止于关键词行或任一标题行，正文里的同一句不报。这一组的由来：摘要长期只被检查「在不在」，从没被检查「写什么」；写进一句「未开展实验」「数据均取自文献」，前面各组检查一声不响，而这类句子恰是把文献综合稿说成实验报告、或反过来把实验稿说成二手材料最直接的一处。同组还查摘要带引注与图表编号，属于同类位置错误。

```bash
python skills/academic-paper-improvement/scripts/audit_manuscript.py 稿件.docx --brief
# 稿名：FAIL 0／WARN 1｜汉字 8807｜S2
```

`--brief` 只打一行，供逐处改稿时复用：局部改写最容易引入旧稿里没有的违规，改一句跑一次，成本低于最后集中排错。

```bash
python skills/academic-paper-improvement/scripts/selftest.py           # 逐条打印
python skills/academic-paper-improvement/scripts/selftest.py --quiet   # 只打印失败项
```

改动规则集时，先改列举再改检测器，最后跑自检。反过来的顺序会让自检在中间状态下失败，属预期。

## 已知限制

- `count_words.py` 两条通道口径不同，不可混用。plain 通道统计的是字符类别，不是文字处理软件报出的"字数"；word 通道只在 Windows + Word 可用。源文件若不含表格文字（表格由数据层单独提供），plain 通道不计这部分，与成稿的差值通常来自此，需计表格时以成稿为准。
- 成稿模式靠"参考文献"字样切正文，靠正文里的"表/图/式"字样统计编号。标题若是手工排版（没有套用 Heading 样式），脚本不会把它识别成标题，因此成稿只做文字层检查；结构检查请在源文件上做。
- `xcheck_refs.py` 依赖 Crossref 的题名匹配。规范类条目、中文题名条目、其他非期刊条目直接跳过并在汇总里计数，**这些条目未做回查，不得计入通过**。它的 User-Agent 带联系邮箱可获得更宽松的速率限制，用环境变量设置：`CROSSREF_MAILTO=you@example.com python xcheck_refs.py`。
- python-docx 每次生成的 .docx 字节级不一致（文档属性里带生成时间），比较内容请比字数与结构，不要比 md5。
- 正则检测只能拦住列举过的形态。新出现的表述要补规则；补完跑 `selftest.py`，正样本必须命中、负样本必须不命中，两份都过了才算补上。这条是实测教训：首版正则漏掉一种形态，它既不被相邻形态匹配，也不被主形态匹配，读一遍正则看不出问题。

## 许可

MIT，见 `LICENSE`。
