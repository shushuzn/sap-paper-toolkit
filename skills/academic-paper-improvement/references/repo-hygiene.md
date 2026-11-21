# 仓库卫生（禁令 5 的机制）

删除垃圾文件不等于解决问题。在同一个地方反复清理、又反复复发，原因只有一个：只清当次，不改机制，而提交动作仍是全量暂存。

以下三件配套，缺一件就会漏：`.gitignore` 负责"不显示"，`pre-commit` 负责"不让进"，`.gitattributes` 负责"钩子能跑"。

本文件不含任何具体仓库、提交号与文件名。示例路径按用途命名，实际使用时替换。

---

## 1　什么该入库，什么不该

| 入库 | 理由 |
|---|---|
| 正文源（如 `manuscript.md`） | 稿件唯一来源，改稿只改这里 |
| 构建脚本（如 `build_docx.py`） | 文献表、表体数据在这里，属源的一部分 |
| 交付件（`.docx`） | 与正文同步提交，便于回退到某一版的成品 |
| 审校/改进记录 | 改动依据与逐处对照，属交付物 |
| 格式依据文件 | 只参照排版参数使用 |

| 不入库 | 理由 |
|---|---|
| 目检用渲染件（页面 PDF、整页截图） | 随用随生成，体积大，无历史价值 |
| `*.bak_*`、`*.orig`、`*~` | 版本历史已由 git 承担，`.bak` 是重复且会分叉 |
| 教学材料（课件、讲义 PDF） | 按禁令 4，不得为稿件提供数据与引用，也不该进论文仓库 |
| 生成的分析结果（核验 JSON、比对缓存） | 可由脚本重跑，入库只会过期 |
| `~$*`、`*.tmp` | Office 锁文件与临时文件 |

**草稿备份的正确做法**：不存 `.bak`。要留快照就提交一次，回退用 `git show <提交>:<文件> > <文件>` 或 `git checkout <提交> -- <文件>`。删掉 `.bak` 之前先抽验一次历史里确实取得到，再删。

---

## 2　`.gitignore` 模板

按四类分组，别只写 `__pycache__`。

```gitignore
# 临时校验产物
/chk*.pdf
/chk*.png
/_*.pdf
/_*.png
/tmp/
.tmpcmp/

# 草稿备份：版本历史由 git 负责
*.bak
*.bak_*
*.bak-*
*.orig
*~

# Office 临时与锁文件
~$*
*.tmp

# 教学材料：按禁令 4 不入论文仓库
/lecture*/
/teaching*/
/slides*/

# 数据层与生成物
paper_data.py
audit_refs.json
xcheck_report.json
xcheck_cache.json
__pycache__/
*.pyc
*.docx
```

最后一组按项目实际增删：数据层含具体论文的文献与表格，随论文变化，不入库；生成的 `.docx` 是否入库取决于是否需要回退成品，两种做法都要写进 README 说明。

---

## 3　`pre-commit` 拦截

放在仓库内 `.githooks/pre-commit`，用 `git config core.hooksPath .githooks` 启用。放仓库内、不用 `.git/hooks/`，是为了随版本走，换机器也不失效。

```sh
#!/bin/sh
[ "$GIT_SKIP_REPO_GUARD" = "1" ] && exit 0
fail=0
staged=$(git diff --cached --name-only --diff-filter=ACMR)
report() { printf '  ✗ %-46s %s\n' "$1" "$2"; fail=1; }
echo "[repo-guard] 检查暂存区..."
for f in $staged; do
    case "$f" in
        *.bak|*.bak_*|*.bak-*|*.orig|*~) report "$f" "草稿备份，不应入库"; continue ;;
    esac
    case "$f" in
        chk*.pdf|chk*.png|_*.pdf|_*.png|tmp/*|.tmpcmp/*)
            report "$f" "临时渲染/截图产物"; continue ;;
    esac
    case "$f" in
        lecture*/*|teaching*/*|slides*/*) report "$f" "教学材料，按禁令不得入库"; continue ;;
    esac
    case "$f" in
        '~$'*|*.tmp) report "$f" "Office 临时文件"; continue ;;
    esac
    if [ -f "$f" ]; then
        size=$(wc -c < "$f" | tr -d ' ')
        [ "$size" -gt 2097152 ] && report "$f" "超过 2 MB（$((size/1024)) KB）"
    fi
done
[ "$fail" -ne 0 ] && { echo "[repo-guard] 提交已阻止"; exit 1; }
echo "[repo-guard] 通过"
exit 0
```

体积上限取 2 MB：交付 docx 通常数十至数百 KB，参考文献原件一般也不到 1 MB，超过多半是渲染件误入。

---

## 4　`.gitattributes` 必须给脚本指定 LF

`* text=auto` 会在检出时把文本转成本地行尾。Windows 下钩子文件因此带上 `\r`：

- `#!/bin/sh\r` 使 sh 报 `bad interpreter`，钩子静默失效；
- 更隐蔽的是 `git rm -- "$f"` 收到带 `\r` 的路径，报 `pathspec did not match any files`，看起来像文件不存在，实际是行尾问题。

```gitattributes
*.docx binary
*.pdf binary
*.png binary

.gitattributes text eol=lf
.gitignore text eol=lf
.githooks/** text eol=lf
*.py text eol=lf
*.sh text eol=lf

* text=auto
```

行尾规则要在**第一次提交钩子之前**写好，否则钩子可能已在工作区被转成 CRLF。

---

## 5　清理流程（照此顺序，不要跳步）

```bash
# 1 先看清单，不要直接动手
git ls-files

# 2 分类后逐项确认，打印出来人工过一遍，数量与体积都要对

# 3 分类处理：临时产物与备份，索引与磁盘同删
git rm -f -- <路径>

# 4 该保留在磁盘但不入库的（如教学材料），只取消跟踪
git rm -r --cached -- <路径>

# 5 提交前确认：本体文件未被误伤
git log --oneline <上一提交>..HEAD -- <正文源>   # 应无输出
git diff --stat <上一提交> HEAD -- <正文源>      # 应为空

# 6 复核机制生效
git status --ignored --short        # 该忽略的显示为 !!
```

**两个易错点**：

- 用脚本生成待删清单时，若文件用文本模式写入，行尾是 CRLF，读回时每行带 `\r`，`git rm` 会报 pathspec 不匹配。读入后须 `f=${f%$'\r'}`，或写文件时指定 `newline='\n'`。
- `while read` 循环读不到末行（文件末尾无换行）。清单末尾补一个换行，或用 `|| [ -n "$f" ]` 兜底。

---

## 6　历史瘦身要不要做

删掉文件不会缩小 `.git`，blob 仍在历史里。要缩小只能重写历史（`git filter-repo`，或 `git filter-branch --index-filter`），代价是**全部提交 hash 改变**。

做之前先算两笔账：

1. 体积账：`git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)'` 按路径过滤，看垃圾 blob 占多少。
2. 引用账：审校记录、交付说明里若引用了提交 hash，重写后全部失效，须逐处改为新值。`v1.0` 这类标签也要重指。

**纯本地仓库、无外部协作者、记录里未引用 hash** 三条同时成立，才可以重写。否则保留历史，接受 `.git` 偏大：它不影响交付，也不影响论文。
