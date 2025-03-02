import os
import sys
import re
import datetime
import subprocess
import errno
import time
import datetime
import shutil
from pathlib  import Path


g_target_path        = ""
g_revision1          = ""
g_revision2          = ""
g_diff_mode          = 0
g_left_label         = ""
g_right_label        = ""
g_left_path          = ""
g_right_path         = ""
g_temp_cmd_name      = "_svn_diff_ex.bat"
g_opt_ts             = 1
g_out_timestamp      = ""
g_out_path           = ""
g_right_only         = 0
g_report_by_winmerge = 0                       #/* WinMergeによる差分レポートの生成（exeにPATHを通しておくこと！） */
g_opt_force          = 1

re_nonexistent  = re.compile(r"^(.+)\s+\(nonexistent\)$")
re_working_copy = re.compile(r"^(.+)\s+\(working copy\)$")
re_revision     = re.compile(r"^(.+)\s+\(revision\s+([0-9]+)\)$")


WIN_MERGE_CMD   = 'WinMergeU.exe -noninteractive -minimize /u -or \"'


class cLabelInfo:
    def __init__(self, file_name, revision):
        self.file_name = file_name
        self.revision  = revision
        return


#/*****************************************************************************/
#/* コマンドライン引数処理                                                    */
#/*****************************************************************************/
def check_command_line_option():
    global g_target_path
    global g_revision1
    global g_revision2
    global g_diff_mode
    global g_left_label
    global g_right_label
    global g_left_path
    global g_right_path
    global g_out_timestamp
    global g_out_path
    global g_right_only
    global g_opt_ts
    global g_report_by_winmerge
    global g_opt_force

    argc = len(sys.argv)
    option = ""

    sys.argv.pop(0)
    count = 0
    for arg in sys.argv:
        if (option == "r"):
            if (result := re.match(r"([0-9]+):([0-9]+)", arg)):
                g_revision1 = int(result.group(1))
                g_revision2 = int(result.group(2))
            elif (result := re.match(r"([0-9]+)", arg)):
                g_revision2 = int(result.group(1))
                g_revision1 = g_revision2 - 1
            else:
                print("svn_diff_ex.py : invalid revision!")
                exit(-1)
            option = ""
        elif (option == "o"):
            g_out_path = arg
            option = ""
        elif (arg == "-t") or (arg == "--timestamp"):
            g_opt_ts = 1
        elif (arg == "-nt") or (arg == "--no_timestamp"):
            g_opt_ts = 0
        elif (arg == "-r") or (arg == "--revision"):
            option = "r"
        elif (arg == "-o") or (arg == "--outpath"):
            option = "o"
        elif (arg == "-nf") or (arg == "--no_force"):
            g_opt_force = 0
        elif (arg == "-wmr") or (arg == "--report_by_winmerge"):
            g_report_by_winmerge = 1
            count += 1
        elif (arg == "-ro") or (arg == "--rightonly"):
            count += 1
            g_right_only = 1
        elif (arg == "-svn"):
            count += 1
            g_diff_mode = 1
#           print("svn_diff_ex.py : svn mode! os.getcwd():%s" % (os.getcwd()))
#           print("sys.argv[1] : %s" % sys.argv[1])
#           print("sys.argv[2] : %s" % sys.argv[2])
#           print("sys.argv[3] : %s" % sys.argv[3])
#           print("sys.argv[4] : %s" % sys.argv[4])
#           print("sys.argv[5] : %s" % sys.argv[5])
            g_out_path    = sys.argv.pop(count)
            g_target_path = sys.argv.pop(count)
            g_left_label  = sys.argv.pop(count)
            g_right_label = sys.argv.pop(count)
            g_left_path   = sys.argv.pop(count)
            g_right_path  = sys.argv.pop(count)
            return
        elif (g_target_path == ""):
            g_target_path = arg
        else:
            print("svn_diff_ex.py : Too many paths!")
            exit(-1)

    if (g_target_path == ""):
#       print("export working copy diff!")
        pass
    elif (os.path.isdir(g_target_path)):
#       print("export working copy diff! from [%s]" % g_target_path)
        pass
    else:
        if ((g_revision1 == "") or (g_revision2 == "")):
            print("svn_diff_ex.py : no target revisions!")
            exit(-1)

#       print("export diff between r%s:r%s from %s" % (g_revision1, g_revision2, g_target_path))

    if (g_opt_ts):
        now = datetime.datetime.now()
        g_out_timestamp = now.strftime("%Y%m%d_%H%M%S")

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
#/* svnのdiff_cmdから呼び出される実行ファイルの生成                           */
#/*****************************************************************************/
def create_temp_cmd_file(out_path, target_path):
    global g_temp_cmd_name
    global g_right_only
    global g_report_by_winmerge

    cmd_option_list = []
    if (g_right_only):
        cmd_option_list.append("-ro")

    if (g_report_by_winmerge):
        cmd_option_list.append("-wmr")

    this_path = "python " + os.getcwd() + "\\" + "svn_diff_ex.py %s -svn \"" % (" ".join(cmd_option_list)) + out_path + "\" \"" + target_path + "\" %3 %5 %6 %7"
#   print(this_path)
    with open(g_temp_cmd_name, "w") as outfile:
        print(r"echo OFF", file = outfile)
#       print(r"echo [1]%1", file = outfile)
#       print(r"echo [2]%2", file = outfile)
#       print(r"echo [3]%3", file = outfile)
#       print(r"echo [4]%4", file = outfile)
#       print(r"echo [5]%5", file = outfile)
#       print(r"echo [6]%6", file = outfile)
#       print(r"echo [7]%7", file = outfile)
#       print(r"echo ON", file = outfile)
        print(this_path, file = outfile)
        outfile.close

    return


#/*****************************************************************************/
#/* 差分取得処理                                                              */
#/*****************************************************************************/
def get_diff_mode():
    global g_left_label
    global g_right_label
    global g_left_path
    global g_right_path
    global g_out_path
    global g_target_path
    global g_report_by_winmerge

    print("Left   Label   : %s" % g_left_label)
    print("Right  Label   : %s" % g_right_label)
    print("Left   Path    : %s" % g_left_path)
    print("Rigth  Path    : %s" % g_right_path)
    print("Out    Path    : %s" % g_out_path)

    g_target_path = g_target_path.replace('\\', '/')
    print("Target Path    : %s" % g_target_path)

    left_label_info  = get_attribute(g_left_label, g_target_path)
    right_label_info = get_attribute(g_right_label, g_target_path)

    left_out_path = g_out_path + "\\01_before\\" + os.path.dirname(left_label_info.file_name)

    if (g_right_only == 0):
        right_out_path = g_out_path + "\\02_after\\" + os.path.dirname(left_label_info.file_name)
    else:
        right_out_path = g_out_path + "\\" + os.path.dirname(left_label_info.file_name)

    print("Left  Out Path : %s" % left_out_path)
    print("Right Out Path : %s" % right_out_path)

    left_file  = left_out_path  + "\\" + os.path.basename(left_label_info.file_name)
    right_file = right_out_path + "\\" + os.path.basename(right_label_info.file_name)
    if (g_right_only == 0):
        make_directory(left_out_path)
        if (left_label_info.revision != -1):
            shutil.copy2(g_left_path,  left_file)

    make_directory(right_out_path)
    if (right_label_info.revision != -1):
        shutil.copy2(g_right_path, right_file)

    if (g_right_only == 0) and (g_report_by_winmerge):
        print("Report by WM   : Yes")
        report_name = g_out_path + "\\" + os.path.basename(left_label_info.file_name) + ".htm"
#       cmd_text = WIN_MERGE_CMD
        cmd_text = WIN_MERGE_CMD + report_name + "\" \"" + left_file + "\" \"" + right_file + "\""
#       print(cmd_text)
        lines = cmd_execute(cmd_text, "", "")
#       print(lines)

    return


#/*****************************************************************************/
#/* ラベル情報からファイル名とRevision情報を取得                              */
#/*****************************************************************************/
def get_attribute(label, base_path):
    file_name = ""
    revision  = 0

#   print("get attribute from : " + label)
    if (result := re_nonexistent.match(label)):
#       print("nonexistent    : %s" % result.group(1))
        file_name = result.group(1)
        revision  = -1
    elif (result := re_working_copy.match(label)):
#       print("working copy   : %s" % result.group(1))
        file_name = result.group(1)
        revision  = 0
    elif (result := re_revision.match(label)):
#       print("revision       : %s,  %s" % (result.group(2), result.group(1)))
        file_name = result.group(1)
        revision  = int(result.group(2))

    file_name = file_name.replace(base_path, '').removeprefix('/')
    
    label_info = cLabelInfo(file_name, revision)
    return label_info


#/*****************************************************************************/
#/* タイムスタンプオプション処理                                              */
#/*****************************************************************************/
def set_time_stamp(out_path):
    global g_out_timestamp

    if (g_out_timestamp != ""):
        out_path = out_path + '_' + g_out_timestamp
    else:
        out_path = out_path

    return out_path


#/*****************************************************************************/
#/* 出力先パス決定                                                            */
#/*****************************************************************************/
def set_output_path(target_path):
    global g_out_path

    if (g_out_path != ""):
#       out_path = set_time_stamp(g_out_path)
        out_path = g_out_path
    elif (os.path.isdir(target_path)):
        #/* パス指定された場合は、同一階層に出力する */
        out_path = set_time_stamp(os.path.dirname(target_path) + '\\diff_export')
    else:
        g_out_path = 'diff_export'
        this_path = os.getcwd()

        out_path = set_time_stamp(this_path + '\\' + g_out_path)

        #/* WorkingCopyの差分抽出の場合、.svnフォルダを探索する */
        if (target_path == ""):
            while(this_path != ""):
                if (os.path.isdir(this_path + r'\.svn')):
                    out_path = set_time_stamp(os.path.dirname(this_path) + '\\' + g_out_path)

#                   print("found .svn in %s to %s" % (this_path, out_path))
                    break

                print("not found .svn in %s" % this_path)
                if (this_path == os.path.dirname(this_path)):
                    break

                this_path = os.path.dirname(this_path)

#   print("out path %s" % out_path)
    return out_path


#/*****************************************************************************/
#/* メイン関数                                                                */
#/*****************************************************************************/
def main():
    global g_target_path
    global g_revision1
    global g_revision2
    global g_diff_mode
    global g_temp_cmd_name
    global g_opt_force

    check_command_line_option()
    if (g_diff_mode):
        #/* --diff-cmdとして呼ばれた際の動作 */
        get_diff_mode()
    else:
        #/* 通常の呼び出し */
        out_path = set_output_path(g_target_path)

        if (g_opt_force == 0):
            cmd_text = 'svn diff --diff-cmd '
        else:
            cmd_text = 'svn diff --force --diff-cmd '

        if (g_target_path == ""):
            create_temp_cmd_file(out_path, '')
            cmd_text = cmd_text + g_temp_cmd_name
        elif (os.path.isdir(g_target_path)):
            create_temp_cmd_file(out_path, g_target_path)
            cmd_text = cmd_text + g_temp_cmd_name + ' ' + g_target_path
        else:
            create_temp_cmd_file(out_path, '')
            cmd_text = cmd_text + g_temp_cmd_name + ' -r ' + str(g_revision1) + ':' + str(g_revision2) + ' ' + g_target_path


        #/* svn diffコマンドを実行し、svn側からg_temp_cmd_nameに作成したbatファイルを実行してもらう */
#       print(cmd_text)
        lines = cmd_execute(cmd_text, "", "")
        print(lines)

        #/* 一時ファイルを削除 */
        os.remove(g_temp_cmd_name)
#       input('Hit Enter!')

    return


if __name__ == "__main__":
    main()
