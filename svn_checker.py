import os
import sys
import re
import datetime
import subprocess
import openpyxl
import difflib
from pathlib import Path


g_stop_on_copy = 0
g_log_limit    = 0
g_kazoe_path   = ""
g_revision1    = ""
g_revision2    = ""
g_path1        = ""
g_path2        = ""
g_path_logs    = []
g_repo_info    = None

re_log_line    = re.compile(r"^r([0-9]+)\s\|\s([^\|]+)\s\|\s([0-9]+)-([0-9]+)-([0-9]+)\s([0-9]+):([0-9]+):([0-9]+)\s[^\|]+\s\|\s([0-9]+)\sline")
re_change_line = re.compile(r"^\s+([MAD])\s(.+)")
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
        return

class cRepoInfo:
    def __init__(self):
        self.path      = ""
        self.url       = ""
        self.relative  = ""
        self.root      = ""
        self.node_kind = ""
        return


def cmd_execute(cmd_text):
    result = subprocess.run(cmd_text, capture_output=True, text=True)
#   print(result.stdout)
    return result.stdout


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
        elif (option == "k"):
            g_kazoe_path = arg
            option = ""
        elif (arg == "--stop-on-copy"):
            g_stop_on_copy = 1
        elif (arg == "-l") or (arg == "--limit"):
            option = "l"
        elif (arg == "-r") or (arg == "--revision"):
            option = "r"
        elif (arg == "-k") or (arg == "--kazoe"):
            option = "k"
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
    lines = cmd_execute(cmd_text).split("\n")

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
            elif (result := re_log_line.match(line)):
                if (commit_log != None):
                    path_log.logs.append(commit_log)

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
#               print("rev : " + result.group(1) + ", author : " + result.group(2) + ", line : " + result.group(9))
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
                commit_log.changes.append(changed)
                print("type : %s, file : %s, path : %s" % (changed.attribute, changed.file_name, changed.path))
            else:
                print("strange log in [%d] : %s" % (log_sequence, line))
        elif (log_sequence == 4):
            commit_log.comments.append(line)
            log_lines -= 1
            if (log_lines == 0):
                log_sequence = 0
            pass


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
    lines = cmd_execute("svn info " + g_path1).split("\n")
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
#/* メイン関数                                                                */
#/*****************************************************************************/
def main():
    check_command_line_option()
    check_repo_info()
    check_path_log()
    return


if __name__ == "__main__":
    main()
