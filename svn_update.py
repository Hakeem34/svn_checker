import subprocess
import os
import shutil
import sys
import datetime
import re

g_log_file = None

RE_SVN_DIR = re.compile(r'(\\)*\.svn(\\)*')


#--------------------------------------------------------------------------------------------------
# ログ出力（標準出力＋ログファイル）
#--------------------------------------------------------------------------------------------------
def print_log(text):
    print(text)
    print(text, file=g_log_file)


#--------------------------------------------------------------------------------------------------
# ログ出力（ログファイル）
#--------------------------------------------------------------------------------------------------
def print_log_only(text):
    print(text, file=g_log_file)


#--------------------------------------------------------------------------------------------------
# 入力の受け取り（ロギング）
#--------------------------------------------------------------------------------------------------
def input_answer(text):
    print_log(text)
    input_key = input(f'')
    print_log_only(input_key)
    return input_key


#--------------------------------------------------------------------------------------------------
# SVNコマンドを実行し、結果を取得する
#--------------------------------------------------------------------------------------------------
def execute_svn_command(command, cwd=None, stop_on_error=True, do_print=True):
    try:
        if do_print:
#           print(f"subprocess.run({command}, cwd={cwd}, capture_output=True, text=True, check=True)")
            print_log(f'    {' '.join(command)}')

        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True, shell=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if stop_on_error:
            print_log(f"エラー: コマンド実行失敗 -> {e.stderr}")
            sys.exit(1)

    return "エラー"


#--------------------------------------------------------------------------------------------------
# ローカルフォルダからリポジトリのURLを確認する
#--------------------------------------------------------------------------------------------------
def check_remote_url(target_dir, is_local_path=True):
    if is_local_path:
        print_log(f"▶ SVNリポジトリURLを確認中...  : {target_dir}")
        info_output = execute_svn_command(["svn", "info"], cwd=target_dir).split('\n')
    else:
        info_output = execute_svn_command(["svn", "info", target_dir], stop_on_error=False).split('\n')

#   print_log(info_output)
    for line in info_output:
#       print_log(line)
        if (result := re.match(r'^URL: (.+)$', line)):
            if is_local_path:
                print_log(f'    OK, URL : {result.group(1)}')
            return result.group(1)

    return ''


#--------------------------------------------------------------------------------------------------
# SVNの変更状態をチェックし、未コミットの変更があれば処理を中止
#--------------------------------------------------------------------------------------------------
def check_svn_status(target_dir):
    print_log(f"▶ SVNステータスを確認中...     : {target_dir}")
    status_output = execute_svn_command(["svn", "status"], cwd=target_dir)

    if status_output:
        print_log("⚠ エラー: 未コミットの変更が検出されました。以下のファイルが影響を受けています:")
        print_log(status_output)
        print_log("処理を中止します。変更をコミットまたはリバートしてください。")
        sys.exit(1)

    print_log(f"    OK")


#--------------------------------------------------------------------------------------------------
# タグの有無、URLの妥当性、すでに存在しているかどうかをチェックしてプロンプトで確認する
#--------------------------------------------------------------------------------------------------
def check_svn_tag_exists(tag_url):
    if (tag_url):
        print_log(f"▶ tag指定の確認中...           : {tag_url}")
        tag_url_get = check_remote_url(tag_url, False)
        if (tag_url_get == tag_url):
            print_log(f"▶ tagはすでに存在しています。処理を中止します。")
            sys.exit(1)

        print_log(f"    OK")
        if (is_include_key_folder(tag_url, 'tags')):
            tag_parent = os.path.split(tag_url)
            tag_parent_get = check_remote_url(tag_parent[0], False)
            if (tag_parent_get != tag_parent[0]):
                input_key = input_answer(f'▶ tagを作成するフォルダが存在していません。続行しますか？ (Yes / No)')
                if (input_key.upper() == 'Y') or (input_key.upper() == 'YES'):
                    pass
                else:
                    print_log("処理を中止します。tag指定を修正してください。")
                    sys.exit(1)
            else:
                print_log(f"    OK")

        else:
            input_key = input_answer(f'▶ tagのUARLにtagsが含まれていません。続行しますか？ (Yes / No)')
            if (input_key.upper() == 'Y') or (input_key.upper() == 'YES'):
                pass
            else:
                print_log("処理を中止します。tag指定を修正してください。")
                sys.exit(1)

    else:
        print_log("▶ tag指定なし")


#--------------------------------------------------------------------------------------------------
# SVN update を実行し、リポジトリの最新状態に更新
#--------------------------------------------------------------------------------------------------
def update_svn_to_latest(target_dir):
    print_log("▶ SVNリポジトリを最新状態に更新中...")
    update_output = execute_svn_command(["svn", "update"], cwd=target_dir).split('\n')
#   print_log(update_output)
    if (len(update_output) == 2):
        print_log(f"    OK, {update_output[1]}")
    else:
        print_log(f"    OK")



#--------------------------------------------------------------------------------------------------
# パスに.svnが含まれているかをチェック
#--------------------------------------------------------------------------------------------------
def is_include_key_folder(path, key):
    while(True):
        paths = os.path.split(path)
        if (paths[1] == key):
            return True

        path  = paths[0]
#       print_log(paths)
        if (len(paths) == 1) or (paths[1] == ''):
            break

    return False


#--------------------------------------------------------------------------------------------------
# ファイル・ディレクトリを再帰的にコピー（既存ファイルは上書き）
#--------------------------------------------------------------------------------------------------
def copy_files(src, dest):
    if not os.path.exists(src):
        print_log(f"エラー: 更新用のディレクトリが存在しません -> {src}")
        sys.exit(1)

    print_log(f"▶ ファイルをコピー中: {src} → {dest}")
    for root, dirs, files in os.walk(src):
        if (is_include_key_folder(root, '.svn')):
#           print_log(f'skip .svn dir! {root}')
            continue

        rel_path = os.path.relpath(root, src)
        dest_path = os.path.join(dest, rel_path)

        os.makedirs(dest_path, exist_ok=True)

        for file in files:
            shutil.copy2(os.path.join(root, file), os.path.join(dest_path, file))


#--------------------------------------------------------------------------------------------------
# update_path に存在しないファイルを SVN から削除する
#--------------------------------------------------------------------------------------------------
def delete_removed_files(target_dir, update_path):
    print_log("▶ 削除すべきファイルを確認中...")
    target_files = set()
    target_dirs  = set()
    update_files = set()
    update_dirs  = set()

    # 更新される側フォルダにあるファイル、フォルダをリストアップ
    for root, dirs, files in os.walk(target_dir):
        if (is_include_key_folder(root, '.svn')):
            continue

        for file in files:
            if (file != '.svn'):
                target_files.add(os.path.relpath(os.path.join(root, file), target_dir))

        for dir in dirs:
            if (dir != '.svn'):
                target_dirs.add(os.path.relpath(os.path.join(root, dir), target_dir))

    # 更新する側フォルダにあるファイル、フォルダをリストアップ
    for root, dirs, files in os.walk(update_path):
        if (is_include_key_folder(root, '.svn')):
            continue

        for file in files:
            if (file != '.svn'):
                update_files.add(os.path.relpath(os.path.join(root, file), update_path))

        for dir in dirs:
            if (dir != '.svn'):
                update_dirs.add(os.path.relpath(os.path.join(root, dir), update_path))

    # 更新される側 にあって、更新する側に無いファイル、フォルダを削除対象とする
    files_to_delete = target_files - update_files
    dirs_to_delete  = target_dirs  - update_dirs

    if files_to_delete:
        print_log("🗑 削除予定のファイル:")
        for file in files_to_delete:
#           print_log(f"  - {file}")
            execute_svn_command(["svn", "delete", "--force", file], cwd=target_dir)
    else:
        print_log("🔹 削除するファイルはありません。")

    if dirs_to_delete:
        print_log("🗑 削除予定のフォルダ:")
        for dir in dirs_to_delete:
#           print_log(f"  - {dir}")
            execute_svn_command(["svn", "delete", "--force", dir], cwd=target_dir)
    else:
        print_log("🔹 削除するフォルダはありません。")


#--------------------------------------------------------------------------------------------------
# 追加ファイルをaddする
#--------------------------------------------------------------------------------------------------
def add_new_files(target_dir):
    print_log("▶ SVNの変更を追加")
    execute_svn_command(["svn", "add", "--force", "."], cwd=target_dir)


#--------------------------------------------------------------------------------------------------
# コミットとTAG作成の実行
#--------------------------------------------------------------------------------------------------
def execute_commit_and_tag(target_dir, remote_url, update_path, tag_url, quiet):
    auto_message = f"Auto-commit by svn_update.py\n  To   : {target_dir}\n  From : {update_path}\n  Tag  : {tag_url}\n"
    input_msg    = f""
    while (quiet == False):
        input_msg = input_answer(f'コミットメッセージを入力してください : ')
        if tag_url:
            input_key = input_answer(f'{input_msg} のメッセージでコミットし、\n{tag_url} のTAGを作成します。\n宜しいですか？ (Yes / No / Cancel)')
        else:
            input_key = input_answer(f'{input_msg} のメッセージでコミットして宜しいですか？ (Yes / No / Cancel)')

        if (input_key.upper() == 'C') or (input_key.upper() == 'CANCEL'): 
            print_log("コミットをキャンセルしました")
            return
        elif (input_key.upper() == 'Y') or (input_key.upper() == 'YES'): 
            quiet = True

    commit_message = input_msg + '\n\n' + auto_message

    # 複数行のコミットメッセージを残すために、テンポラリファイルを作る
    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y%m%d_%H%M%S")
    tmp_file = os.path.abspath("~svn_update_commit_" + formatted_time + ".txt")
    tmp_commit_message = open(tmp_file, "w", newline="\n")
    print(commit_message, file=tmp_commit_message)
    tmp_commit_message.close()

    print_log("▶ SVNの変更をコミット")
    execute_svn_command(["svn", "commit", "-F", tmp_file], cwd=target_dir, do_print=False)

    if tag_url:
        print_log(f"▶ SVNのタグを作成: {tag_url}")
        execute_svn_command(["svn", "copy", remote_url, tag_url, "-F", tmp_file], do_print=False)

    os.remove(tmp_file)
    print_log("✅ SVNアップデート & コミット完了")


#--------------------------------------------------------------------------------------------------
# SVNリポジトリを更新し、コミットしてタグを作成する
#--------------------------------------------------------------------------------------------------
def svn_update_and_commit(target_dir, update_path, tag_url=None, dryrun=False, quiet=False):
    if not os.path.exists(target_dir):
        print_log(f"エラー: 指定されたリポジトリディレクトリが存在しません -> {target_dir}")
        sys.exit(1)

    # SVNステータスをチェック（変更があれば処理中止）
    check_svn_status(target_dir)

    # tagの存在チェック（urlの不正、すでに存在している場合は確認する）
    check_svn_tag_exists(tag_url)

    # SVNリポジトリURLをチェック
    remote_url = check_remote_url(target_dir)

    # SVNリポジトリを最新状態に更新
    update_svn_to_latest(target_dir)

    # ファイルをコピー
    copy_files(update_path, target_dir)

    # 更新ディレクトリにないファイルを削除
    delete_removed_files(target_dir, update_path)

    # ファイルの追加
    add_new_files(target_dir)

    if dryrun:
        print_log("▶ Dry-runモード: コミットおよびタグ作成はスキップします。")
        return

    # コミットの実行
    execute_commit_and_tag(target_dir, remote_url, update_path, tag_url, quiet)
    return




#--------------------------------------------------------------------------------------------------
# ログファイル設定
#--------------------------------------------------------------------------------------------------
def log_settings():
    global g_log_file

    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y%m%d_%H%M%S")
    log_path = "svn_update_" + formatted_time + ".log";
    print("log_path : %s" % log_path)

    g_log_file = open(log_path, "a", encoding="utf-8")
    now = datetime.datetime.now()
    print_log("start update : " + str(now))
    return



if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 6:
        print("使い方: svn_update.py [target(checkouted) directory] [update code path] [tag url (省略可)] [--dryrun (省略可)] [--quiet (省略可)]")
        sys.exit(1)

    log_settings()

    target_directory = sys.argv[1]
    update_code_path = sys.argv[2]
    tag_svn_url = None
    dryrun = False
    quiet  = False

    # オプションの解析
    for arg in sys.argv[3:]:
        if arg.lower() == "--dryrun":
            dryrun = True
        elif arg.lower() == "--quiet":
            quiet = True
        else:
            tag_svn_url = arg  # --dryrun でなければ tag_url として扱う

    svn_update_and_commit(target_directory, update_code_path, tag_svn_url, dryrun, quiet)
    g_log_file.close()
