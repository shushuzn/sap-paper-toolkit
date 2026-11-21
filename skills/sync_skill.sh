#!/bin/sh
# sync_skill.sh  把仓库内的 skill 镜像到 WorkBuddy 安装目录
#
# 仓库是唯一源：skill 的正文、参考文件与核验脚本都改在 skills/<name>/ 下，
# 安装目录只作为部署结果存在，不直接编辑。
#
# 用法：
#   sh skills/sync_skill.sh install     仓库 → 安装位置（默认动作，镜像，多余的删除）
#   sh skills/sync_skill.sh check       只比对，有漂移退出 1；未安装时退出 0
#   sh skills/sync_skill.sh diff        列出差异文件，不做写入
#   sh skills/sync_skill.sh pull --yes  安装位置 → 仓库（安装处临时改过时回收）
#
# 选项：
#   --dry-run               只报告，不写入
#   --no-prune              install 时不删除安装位置里的多余文件
#   --skills-home <dir>     覆盖安装根目录
#   --yes                   pull 的确认开关
#
# 环境变量：
#   WORKBUDDY_SKILLS_HOME  安装根目录，默认 ~/.workbuddy/skills
#
# 退出码：0 成功或无漂移；1 有漂移或操作失败；2 用法错误

set -u

SKILL_NAME=academic-paper-improvement
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SRC=$SCRIPT_DIR/$SKILL_NAME
SKILLS_HOME=${WORKBUDDY_SKILLS_HOME:-$HOME/.workbuddy/skills}
DST=$SKILLS_HOME/$SKILL_NAME

cmd=
dry_run=0
prune=1
confirmed=0

die() { printf '[sync] %s\n' "$1" >&2 ; exit 2 ; }

# ---------- 参数 ----------
while [ $# -gt 0 ]; do
    case "$1" in
        install|check|diff|pull) cmd=$1 ;;
        --dry-run)   dry_run=1 ;;
        --no-prune)  prune=0 ;;
        --yes)       confirmed=1 ;;
        --skills-home)
            [ $# -ge 2 ] || die "--skills-home 需要一个目录参数"
            SKILLS_HOME=$2
            DST=$SKILLS_HOME/$SKILL_NAME
            shift ;;
        -h|--help)
            sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) die "未知参数：$1（用 --help 看用法）" ;;
    esac
    shift
done
[ -n "$cmd" ] || cmd=install

[ -d "$SRC" ] || die "仓库内找不到 skill 目录：$SRC"

tmp=$(mktemp -d 2>/dev/null) || die "无法创建临时目录"
trap 'rm -rf "$tmp"' EXIT INT TERM

# ---------- 文件枚举 ----------
# 排除项与 .gitignore 保持一致：草稿备份、缓存、系统残留一律不参与同步
list_files() {
    root=$1
    [ -d "$root" ] || return 0
    find "$root" -type f \
        ! -name '*.bak' ! -name '*.bak_*' ! -name '*.bak-*' \
        ! -name '*.orig' ! -name '*~' ! -name '*.tmp' \
        ! -name '*.pyc' ! -name '.DS_Store' \
        ! -path '*/__pycache__/*' \
    | while IFS= read -r f; do printf '%s\n' "${f#"$root"/}" ; done | LC_ALL=C sort
}

# cksum 输出 crc 与字节数，两者相同才认为同内容
file_sum() { cksum "$1" 2>/dev/null | awk '{print $1 "-" $2}' ; }

skill_version() {
    awk -F': *' '/^version:/ {gsub(/"/, "", $2); print $2; exit}' "$SRC/SKILL.md" 2>/dev/null
}

list_files "$SRC" > "$tmp/src"
ver=$(skill_version)
printf '[sync] 源：%s（版本 %s，%s 个文件）\n' "$SKILL_NAME" "${ver:-未知}" "$(wc -l < "$tmp/src" | tr -d ' ')"
printf '[sync] 目标：%s\n' "$DST"

# ---------- check / diff ----------
run_compare() {
    mode=$1
    if [ ! -d "$DST" ]; then
        printf '[sync] 安装位置不存在，视为未安装，跳过比对。\n'
        return 0
    fi
    list_files "$DST" > "$tmp/dst"
    drift=0
    changed=0 ; missing=0 ; extra=0

    while IFS= read -r rel; do
        if [ ! -f "$DST/$rel" ]; then
            missing=$((missing + 1)) ; drift=1
            [ "$mode" = diff ] && printf '  缺少   %s\n' "$rel"
            continue
        fi
        if [ "$(file_sum "$SRC/$rel")" != "$(file_sum "$DST/$rel")" ]; then
            changed=$((changed + 1)) ; drift=1
            [ "$mode" = diff ] && printf '  不同   %s\n' "$rel"
        fi
    done < "$tmp/src"

    while IFS= read -r rel; do
        if [ ! -f "$SRC/$rel" ]; then
            extra=$((extra + 1)) ; drift=1
            [ "$mode" = diff ] && printf '  多余   %s\n' "$rel"
        fi
    done < "$tmp/dst"

    if [ "$drift" -eq 0 ]; then
        printf '[sync] 一致：安装位置与仓库逐文件相同。\n'
        return 0
    fi
    printf '[sync] 漂移：缺少 %d，内容不同 %d，多余 %d\n' "$missing" "$changed" "$extra"
    if [ "$mode" = check ]; then
        printf '[sync] 执行 sh skills/sync_skill.sh install 使安装位置与仓库一致。\n'
    fi
    return 1
}

# ---------- install ----------
run_install() {
    list_files "$DST" > "$tmp/dst" 2>/dev/null || : > "$tmp/dst"
    updated=0 ; added=0 ; removed=0

    while IFS= read -r rel; do
        dstf=$DST/$rel
        if [ -f "$dstf" ] && [ "$(file_sum "$SRC/$rel")" = "$(file_sum "$dstf")" ]; then
            continue
        fi
        if [ -f "$dstf" ]; then
            updated=$((updated + 1)) ; printf '  更新   %s\n' "$rel"
        else
            added=$((added + 1)) ; printf '  新增   %s\n' "$rel"
        fi
        [ "$dry_run" -eq 1 ] && continue
        mkdir -p "$(dirname "$dstf")" || die "无法创建目录：$(dirname "$dstf")"
        cp -p "$SRC/$rel" "$dstf" || die "复制失败：$rel"
    done < "$tmp/src"

    if [ "$prune" -eq 1 ] && [ -d "$DST" ]; then
        while IFS= read -r rel; do
            [ -f "$SRC/$rel" ] && continue
            removed=$((removed + 1)) ; printf '  删除   %s\n' "$rel"
            [ "$dry_run" -eq 1 ] && continue
            rm -f "$DST/$rel"
        done < "$tmp/dst"
        [ "$dry_run" -eq 1 ] || find "$DST" -type d -empty -delete 2>/dev/null
    fi

    if [ "$dry_run" -eq 1 ]; then
        printf '[sync] 预演：将新增 %d，更新 %d，删除 %d（未写入）\n' "$added" "$updated" "$removed"
    else
        printf '[sync] 完成：新增 %d，更新 %d，删除 %d。\n' "$added" "$updated" "$removed"
    fi
    return 0
}

# ---------- pull ----------
run_pull() {
    [ -d "$DST" ] || die "安装位置不存在，无可回收内容：$DST"
    if [ "$confirmed" -ne 1 ]; then
        printf '[sync] pull 会用安装位置的版本覆盖仓库文件，需加 --yes 确认。\n' >&2
        printf '[sync] 先跑 sh skills/sync_skill.sh diff 看差异。\n' >&2
        return 2
    fi
    list_files "$DST" > "$tmp/dst"
    back=0 ; fresh=0
    while IFS= read -r rel; do
        dstf=$DST/$rel ; srcf=$SRC/$rel
        if [ -f "$srcf" ] && [ "$(file_sum "$srcf")" = "$(file_sum "$dstf")" ]; then
            continue
        fi
        if [ -f "$srcf" ]; then
            back=$((back + 1)) ; printf '  覆盖   %s\n' "$rel"
        else
            fresh=$((fresh + 1)) ; printf '  拉入   %s\n' "$rel"
        fi
        [ "$dry_run" -eq 1 ] && continue
        mkdir -p "$(dirname "$srcf")"
        cp -p "$dstf" "$srcf"
    done < "$tmp/dst"

    list_files "$SRC" > "$tmp/src2"
    while IFS= read -r rel; do
        [ -f "$DST/$rel" ] || printf '  待清理 %s（仓库有、安装位置无，pull 不删除，需人工确认）\n' "$rel"
    done < "$tmp/src2"

    printf '[sync] 回收：覆盖 %d，拉入 %d。请用 git status --short 逐行核对后提交。\n' "$back" "$fresh"
    return 0
}

case "$cmd" in
    check)  run_compare check ;;
    diff)   run_compare diff ;;
    install) run_install ;;
    pull)   run_pull ;;
esac
