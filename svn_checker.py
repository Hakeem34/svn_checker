import os
import sys
import re
import datetime
import subprocess
import openpyxl
import difflib
import errno
import time
import datetime
import shutil
from pathlib  import Path
from operator import itemgetter
from operator import attrgetter


g_stop_on_copy      = 0
g_full_path         = 0
g_log_limit         = 0
g_kazoe_path        = ""
g_revision1         = ""
g_revision2         = ""
g_path1             = ""
g_path2             = ""
g_path_logs         = []
g_repo_info         = None
g_out_path          = "out"
g_target_paths      = []
g_log_file_name     = ""
g_default_log       = 1

re_log_line    = re.compile(r"^r([0-9]+)\s\|\s([^\|]+)\s\|\s([0-9]+)-([0-9]+)-([0-9]+)\s([0-9]+):([0-9]+):([0-9]+)\s[^\|]+\s\|\s([0-9]+)\sline")
re_change_line = re.compile(r"^\s+([MADR])\s(.+)")
re_change_file = re.compile(r"\/([^\/]+)$")

class cChangeFile:
    def __init__(self):
        self.attribute = ""
        self.path      = ""
        self.file_name = ""
        self.external  = 0
        return

class cCommitLog:
    def __init__(self):
        self.revision = 0
        self.author   = ""
        self.year     = 0
        self.month    = 0
        self.day      = 0
        self.hour     = 0
        self.minute   = 0
        self.second   = 0
        self.line     = 0
        self.refs     = []
        self.comments = []
        self.changes  = []
        return

class cPathLog:
    def __init__(self):
        self.path     = ""
        self.option   = ""
        self.logs     = []
        self.targets  = []
        return

class cRepoInfo:
    def __init__(self):
        self.path      = ""
        self.url       = ""
        self.relative  = ""
        self.root      = ""
        self.node_kind = ""
        return


#/*****************************************************************************/
#/* ログファイル設定                                                          */
#/*****************************************************************************/
def log_settings():
    global g_log_file_name
    global g_out_path
    global g_default_log


    make_directory(g_out_path)
    log_path = ""

#   print("log_settings")
    if (g_log_file_name != ""):
        log_path = g_out_path + "\\" + g_log_file_name
    elif (g_default_log == 1):
        now = datetime.datetime.now()
        formatted_time = now.strftime("%Y%m%d_%H%M%S")
        log_path = g_out_path + "\\svn_checker_" + formatted_time + ".log";

    print ("log_path : %s" % log_path)

    if (log_path != ""):
       log_file = open(log_path, "a")
       sys.stdout = log_file

    now = datetime.datetime.now()
    print("start checking : " + str(now))

    return

#/*****************************************************************************/
#/* 外部コマンド実行                                                          */
#/*****************************************************************************/
def cmd_execute(cmd_text, out_file, in_file):
    if (out_file == ""):
        if (in_file == ""):
            result = subprocess.run(cmd_text, capture_output=True, text=True)
        else:
            with open(in_file, "r") as infile:
                result = subprocess.run(cmd_text, capture_output=True, text=True, stdin=infile)
    else:
        if (in_file == ""):
            with open(out_file, "w") as outfile:
                result = subprocess.run(cmd_text, stdout=outfile)
        else:
            with open(out_file, "w") as outfile:
                with open(in_file, "r") as infile:
                    result = subprocess.run(cmd_text, stdout=outfile, stdin=infile)

#   print(result.stdout)
    return result.stdout


#/*****************************************************************************/
#/* ディレクトリ作成                                                          */
#/*****************************************************************************/
def make_directory(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return

#/*****************************************************************************/
#/* ディレクトリ作成                                                          */
#/*****************************************************************************/
def force_copy_directory(src_path, dst_path):
    if os.path.exists(dst_path):
        shutil.rmtree(dst_path)

    try:
        shutil.copytree(src_path, dst_path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return


#/*****************************************************************************/
#/* ターゲットパス判定                                                        */
#/*****************************************************************************/
def is_path_in_target(path):
    global g_target_paths

    #/* ターゲットパス指定が空の場合は、trueを返す */
    if not g_target_paths:
        return True

    for target in g_target_paths:
        if (re.search(target, path)):
            return True

    return False


#/*****************************************************************************/
#/* コマンドライン引数処理                                                    */
#/*****************************************************************************/
def check_command_line_option():
    global g_stop_on_copy
    global g_log_limit
    global g_kazoe_path
    global g_revision1
    global g_revision2
    global g_path1
    global g_path2
    global g_out_path
    global g_full_path

    argc = len(sys.argv)
    option = ""

    if (argc == 1):
        print("usage ; svn_checker.py")
        exit(-1)

    sys.argv.pop(0)
    for arg in sys.argv:
        if (option == "r"):
            if (g_revision1 == ""):
                g_revision1 = arg
            elif (g_revision2 == ""):
                g_revision2 = arg
            else:
                print("svn_checker.py : Too many revisions!")
                exit(-1)
            option = ""
        elif (option == "l"):
            g_log_limit = int(arg)
#           print("log limit %s" % g_log_limit)
            option = ""
        elif (option == "o"):
            g_out_path = arg
            option = ""
        elif (option == "k"):
            g_kazoe_path = arg
            option = ""
        elif (arg == "--stop-on-copy"):
            g_stop_on_copy = 1
        elif (arg == "-f") or (arg == "--fullpath"):
            g_full_path = 1
        elif (arg == "-l") or (arg == "--limit"):
            option = "l"
        elif (arg == "-r") or (arg == "--revision"):
            option = "r"
        elif (arg == "-k") or (arg == "--kazoe"):
            option = "k"
        elif (arg == "-o"):
            option = "o"
        elif (g_path1 == ""):
            if (result := re.search(r"\/$", arg)):
#               print("end by /")
                g_path1 = arg[:-1]
            else:
                g_path1 = arg
        elif (g_path2 == ""):
            g_path2 = arg
        else:
            print("svn_checker.py : Too many paths!")
            exit(-1)


    if (g_path1 == ""):
        print("svn_checker.py : no target path!")
        exit(-1)

    return



#/*****************************************************************************/
#/* svnログ取得                                                               */
#/*****************************************************************************/
def check_log(target_path, revision, limit):
    global g_path_logs
    global g_repo_info

    cmd_text = r"svn log -v "
    option   = ""

    if (revision != ""):
        option += r"-r " + revision + " "

    if (limit != 0):
        option += r"-l " + str(limit) + " "

    cmd_text += option + target_path
    path_log        = cPathLog()
    path_log.path   = target_path
    path_log.option = option

    print(cmd_text)
    lines = cmd_execute(cmd_text, "", "").split("\n")

    commit_log = None
    log_sequence = 0
    log_lines = 0
    for line in lines:
#       print("line : " + line)
        if (log_sequence == 0) or (log_sequence == 1):
            if (line == "------------------------------------------------------------------------"):
                log_sequence = 1
                if (commit_log != None):
                    path_log.logs.append(commit_log)
                    commit_log = None
            elif (result := re_log_line.match(line)):
                if (commit_log != None):
                    path_log.logs.append(commit_log)
                    commit_log = None

                commit_log = cCommitLog()
                commit_log.revision = int(result.group(1))
                commit_log.author   = result.group(2)
                commit_log.year     = int(result.group(3))
                commit_log.month    = int(result.group(4))
                commit_log.day      = int(result.group(5))
                commit_log.hour     = int(result.group(6))
                commit_log.minute   = int(result.group(7))
                commit_log.second   = int(result.group(8))
                commit_log.line     = int(result.group(9))
                print("rev : " + result.group(1) + ", author : " + result.group(2) + ", line : " + result.group(9))
#               print("datetime : %04d/%02d/%02d %02d:%02d:%02d" % (commit_log.year, commit_log.month, commit_log.day, commit_log.hour, commit_log.minute, commit_log.second))
                log_sequence = 2
                log_lines    = commit_log.line
            elif (line == ""):
                pass
            else:
                print("strange log in [%d] : %s" % (log_sequence, line))
        elif (log_sequence == 2):
            if (line == "Changed paths:"):
                log_sequence = 3
            else:
                print("strange log in [%d] : %s" % (log_sequence, line))
        elif (log_sequence == 3):
            if (line == ""):
                log_sequence = 4
            elif (result := re_change_line.match(line)):
                changed = cChangeFile()
                changed.attribute = result.group(1)
                changed.path      = result.group(2)
                
                if (result := re_change_file.search(changed.path)):
                    changed.file_name = result.group(1)
                else:
                    changed.file_name = ""
                if (re.match(g_repo_info.relative, changed.path) ):
                    #/* 指定されたリポジトリパスの範囲内のファイル */
                    print("in type : %s, file : %s, path : %s" % (changed.attribute, changed.file_name, changed.path))
                    changed.external = 0
                    path_log.targets.append(changed.path)
                else:
                    #/* 指定されたリポジトリパスの範囲外のファイル */
#                   print("ex type : %s, file : %s, path : %s" % (changed.attribute, changed.file_name, changed.path))
                    changed.external = 1
                commit_log.changes.append(changed)
            else:
                print("strange log in [%d] : %s" % (log_sequence, line))
        elif (log_sequence == 4):
            commit_log.comments.append(line)
            log_lines -= 1
            if (log_lines == 0):
                log_sequence = 0
            pass

    #/* 最後にターゲットpathの重複を削除して、ログをRevisionの昇順でソートして登録する */
    path_log.targets = set(path_log.targets)
    path_log.logs.sort(key=attrgetter('revision'))
    g_path_logs.append(path_log)
    return





#/*****************************************************************************/
#/* パスのログ確認                                                            */
#/*****************************************************************************/
def check_path_log():
    global g_path1
    global g_path2
    global g_log_limit
    global g_revision1
    global g_revision2

    if (g_path2 == ""):
        check_log(g_path1, g_revision1, g_log_limit)
    else:
        check_log(g_path1)

    return


#/*****************************************************************************/
#/* リポジトリ情報の確認                                                      */
#/*****************************************************************************/
def check_repo_info():
    global g_path1
    global g_repo_info

    g_repo_info = cRepoInfo()
    lines = cmd_execute("svn info " + g_path1, "", "").split("\n")
    for line in lines:
#       print(line)
        if (result := re.match(r"Path: ([^\s]+)", line)):
            g_repo_info.path = result.group(1)
        elif (result := re.match(r"URL: ([^\s]+)", line)):
            g_repo_info.url = result.group(1)
        elif (result := re.match(r"Relative URL: \^([^\s]+)", line)):
            g_repo_info.relative = result.group(1)
        elif (result := re.match(r"Repository Root: ([^\s]+)", line)):
            g_repo_info.root = result.group(1)
        elif (result := re.match(r"Node Kind: ([^\s]+)", line)):
            g_repo_info.node_kind = result.group(1)

    if (g_path1 != g_repo_info.url):
        print("strange svn info. URL unmatch! [%s] - [%s]" % (g_path1, g_repo_info.url))
        exit(-1)

    print("Path : %s, URL : %s, Root : %s, Relative : %s, Kind : %s" % (g_repo_info.path, g_repo_info.url, g_repo_info.root, g_repo_info.relative, g_repo_info.node_kind))
    return



#/*****************************************************************************/
#/* ログ内のターゲットファイル出力                                            */
#/*****************************************************************************/
def output_log_text(target_path, commit_log):
    file_path = target_path + "/commit_log.txt"
    with open(file_path, "w") as outfile:
        print("Revision : " + str(commit_log.revision),  file = outfile)
        print("Author   : " + commit_log.author,         file = outfile)
        print("Date     : %04d/%02d/%02d" % (commit_log.year, commit_log.month, commit_log.day),     file = outfile)
        print("Time     : %02d:%02d:%02d" % (commit_log.hour, commit_log.minute, commit_log.second), file = outfile)
        print("", file = outfile)
        for comment in commit_log.comments:
            print("Comment  : " + comment, file = outfile)

        print("", file = outfile)

        for change in commit_log.changes:
            print("Files    : %s   %s" % (change.attribute, change.path), file = outfile)

        print("", file = outfile)

    return



#/*****************************************************************************/
#/* ログ内のターゲットファイル出力                                            */
#/*****************************************************************************/
def output_log_files(path_log, commit_log, pre_revision):
    global g_repo_info
    global g_full_path
    global g_out_path

    rev_path = g_out_path + "/rev_" + str(commit_log.revision)
    print("output_log_files for rev:%d, pre_rev: %d" % (commit_log.revision, pre_revision))

    out_path = rev_path
    if (pre_revision == 0):
        cmd_base = "svn export -r " + str(commit_log.revision) + " "
        make_directory(rev_path)
        for target in path_log.targets:
            if (is_path_in_target(target)):
#               print("out for %d : %s" % (commit_log.revision, target))
                if (g_full_path):
                    out_path = rev_path + os.path.dirname(target)
                    export_cmd = cmd_base + g_repo_info.root + target + " " + out_path
                else:
                    out_path = rev_path + os.path.dirname(target).replace(g_repo_info.relative, "")
                    export_cmd = cmd_base + g_repo_info.root + target + " " + out_path
#               print("create path : %s" % (out_path))
                make_directory(out_path)
#               print("export : %s" % (export_cmd))
                lines = cmd_execute(export_cmd, "", "")
    else:
        #/* 2回目以降のRevisionに対しては、svn diffによるPatchを取得して、Patchを当てていくことで高速化する */
        pre_path = g_out_path + "/rev_" + str(pre_revision)
        force_copy_directory(pre_path, out_path)
        out_diff = out_path + "/diff_from_r" + str(pre_revision) + ".diff"
        diff_cmd = "svn diff -r " + str(pre_revision) + ":" + str(commit_log.revision) + " " + g_repo_info.url
        print(diff_cmd)
        lines = cmd_execute(diff_cmd, out_diff, "")
        print(lines)
        if (g_full_path):
            patch_cmd = "patch -d " + out_path + g_repo_info.relative + " -p0"
        else:
            patch_cmd = "patch -d " + out_path + " -p0"
        print(patch_cmd)
        lines = cmd_execute(patch_cmd, "", out_diff)
        os.remove(out_diff)

    output_log_text(rev_path, commit_log)
    return


#/*****************************************************************************/
#/* パス内のファイル履歴出力                                                  */
#/*****************************************************************************/
def output_path_files():
    global g_repo_info
    global g_path_logs
    global g_out_path
    global g_full_path

    pre_revision = 0
    make_directory(g_out_path)
    for path_log in g_path_logs:
        for target in path_log.targets:
            print("target : %s" % target)

        for log in path_log.logs:
#           print("log for rev : %d" % log.revision)
            for changed in log.changes:
                if (changed.external == 0):
#                   print("hit on rev %d" % log.revision)
                    if (is_path_in_target(changed.path)):
                        output_log_files(path_log, log, pre_revision)
                        pre_revision = log.revision
                        break

    return


#/*****************************************************************************/
#/* メイン関数                                                                */
#/*****************************************************************************/
def main():
    start_time = time.perf_counter()

    check_command_line_option()
    log_settings()
    check_repo_info()
    check_path_log()
    output_path_files()

    end_time = time.perf_counter()
    now = datetime.datetime.now()
    print("end checking : " + str(now))
    second = int(end_time - start_time)
    minute = second / 60
    second = second % 60
    print("  %dmin %dsec" % (minute, second))
    return


if __name__ == "__main__":
    main()
