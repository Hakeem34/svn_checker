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


g_target_path   = ""
g_revision1     = ""
g_revision2     = ""
g_diff_mode     = 0
g_left_label    = ""
g_right_label   = ""
g_left_path     = ""
g_right_path    = ""
g_temp_cmd_name = "_svn_diff_ex.bat"
g_out_timestamp = ""
g_out_path      = ""
g_right_only    = 0

re_nonexistent  = re.compile(r"^(.+)\s+\(nonexistent\)$")
re_working_copy = re.compile(r"^(.+)\s+\(working copy\)$")
re_revision     = re.compile(r"^(.+)\s+\(revision\s+([0-9]+)\)$")



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
            now = datetime.datetime.now()
            g_out_timestamp = now.strftime("%Y%m%d_%H%M%S")
        elif (arg == "-r") or (arg == "--revision"):
            option = "r"
        elif (arg == "-o") or (arg == "--outpath"):
            option = "o"
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
        print("export working copy diff!")
    else:
        if ((g_revision1 == "") or (g_revision2 == "")):
            print("svn_diff_ex.py : no target revisions!")
            exit(-1)

        print("export diff between r%s:r%s from %s" % (g_revision1, g_revision2, g_target_path))

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
def create_temp_cmd_file(out_path):
    global g_temp_cmd_name
    global g_right_only

    if (g_right_only):
        this_path = "python " + os.getcwd() + "\\" + "svn_diff_ex.py -ro -svn \"" + out_path + "\" %3 %5 %6 %7"
    else:
        this_path = "python " + os.getcwd() + "\\" + "svn_diff_ex.py -svn \"" + out_path + "\" %3 %5 %6 %7"
    
    with open(g_temp_cmd_name, "w") as outfile:
        print(r"echo OFF", file = outfile)
#       print(r"echo %1", file = outfile)
#       print(r"echo %2", file = outfile)
#       print(r"echo %3", file = outfile)
#       print(r"echo %4", file = outfile)
#       print(r"echo %5", file = outfile)
#       print(r"echo %6", file = outfile)
#       print(r"echo %7", file = outfile)
        print(this_path, file = outfile)
        outfile.close

    return this_path


#/*****************************************************************************/
#/* 差分取得処理                                                              */
#/*****************************************************************************/
def get_diff_mode():
    global g_left_label
    global g_right_label
    global g_left_path
    global g_right_path
    global g_out_path

    print("Left  Label : %s" % g_left_label)
    print("Right Label : %s" % g_right_label)
    print("Left  Path  : %s" % g_left_path)
    print("Rigth Path  : %s" % g_right_path)
    print("Out   Path  : %s" % g_out_path)

    left_label_info  = get_attribute(g_left_label)
    right_label_info = get_attribute(g_right_label)

    left_out_path = g_out_path + "\\01_before\\" + os.path.dirname(left_label_info.file_name)

    if (g_right_only == 0):
        right_out_path = g_out_path + "\\02_after\\" + os.path.dirname(left_label_info.file_name)
    else:
        right_out_path = g_out_path + "\\" + os.path.dirname(left_label_info.file_name)

#   print("Left  Out Path  : %s" % left_out_path)
#   print("Right Out Path  : %s" % right_out_path)
    if (g_right_only == 0):
        make_directory(left_out_path)
        if (left_label_info.revision != -1):
            shutil.copy2(g_left_path,  left_out_path  + "\\" + os.path.basename(left_label_info.file_name))

    make_directory(right_out_path)
    if (right_label_info.revision != -1):
        shutil.copy2(g_right_path, right_out_path + "\\" + os.path.basename(right_label_info.file_name))

    return


#/*****************************************************************************/
#/* ラベル情報からファイル名とRevision情報を取得                              */
#/*****************************************************************************/
def get_attribute(label):
    file_name = ""
    revision  = 0

    print("get attribute from : " + label)
    if (result := re_nonexistent.match(label)):
        print("nonexistent  : %s" % result.group(1))
        file_name = result.group(1)
        revision  = -1
    elif (result := re_working_copy.match(label)):
        print("working copy : %s" % result.group(1))
        file_name = result.group(1)
        revision  = 0
    elif (result := re_revision.match(label)):
        print("revision %s : %s" % (result.group(2), result.group(1)))
        file_name = result.group(1)
        revision  = int(result.group(2))

    label_info = cLabelInfo(file_name, revision)
    return label_info


#/*****************************************************************************/
#/* 出力先パス決定                                                            */
#/*****************************************************************************/
def set_output_path(target_path):
    global g_out_path

    if (g_out_path != ""):
        if (g_out_timestamp != ""):
            out_path = g_out_path + '_' + g_out_timestamp
        else:
            out_path = g_out_path
    else:
        this_path = os.getcwd()

        if (g_out_timestamp != ""):
            out_path = this_path + '\\' + g_out_path + '_' + g_out_timestamp
        else:
            out_path = this_path + '\\' + g_out_path

        #/* WorkingCopyの差分抽出の場合、.svnフォルダを探索する */
        if (target_path == ""):
            while(this_path != ""):
                if (os.path.isdir(this_path + '\.svn')):
                    if (g_out_timestamp != ""):
                        out_path = os.path.dirname(this_path) + '\\' + g_out_path + '_' + g_out_timestamp
                    else:
                        out_path = os.path.dirname(this_path) + '\\' + g_out_path

                    print("found .svn in %s to %s" % (this_path, out_path))
                    break

                print("not found .svn in %s" % this_path)
                if (this_path == os.path.dirname(this_path)):
                    break

                this_path = os.path.dirname(this_path)

    print("out path %s" % out_path)
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

    check_command_line_option()
    if (g_diff_mode):
        #/* --diff-cmdとして呼ばれた際の動作 */
        get_diff_mode()
    else:
        out_path = set_output_path(g_target_path)
        temp_cmd = create_temp_cmd_file(out_path)

        if (g_target_path == ""):
            cmd_text = 'svn diff --diff-cmd ' + g_temp_cmd_name
        else:
            cmd_text = 'svn diff --diff-cmd ' + g_temp_cmd_name + ' -r ' + str(g_revision1) + ':' + str(g_revision2) + ' ' + g_target_path

        print(cmd_text)
        lines = cmd_execute(cmd_text, "", "")
        print(lines)

        #/* 一時ファイルを削除 */
        os.remove(g_temp_cmd_name)

    return


if __name__ == "__main__":
    main()
