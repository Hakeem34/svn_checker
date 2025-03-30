import subprocess
import os
import shutil
import sys
import datetime
import re

def execute_svn_command(command, cwd=None):
    """ SVNコマンドを実行し、結果を取得する """
    try:
        print(f"subprocess.run({command}, cwd={cwd}, capture_output=True, text=True, check=True)")
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True, shell=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"エラー: コマンド実行失敗 -> {e.stderr}")
        sys.exit(1)

def check_remote_url(target_dir):
    print("▶ SVNリポジトリURLを確認中...")
    info_output = execute_svn_command(["svn", "info"], cwd=target_dir).split('\n')
#   print(info_output)
    for line in info_output:
#       print(line)
        if (result := re.match(r'^URL: (.+)$', line)):
            print(f'URL : {result.group(1)}')
            return result.group(1)

    return ''

def check_svn_status(target_dir):
    """ SVNの変更状態をチェックし、未コミットの変更があれば処理を中止 """
    print("▶ SVNステータスを確認中...")
    status_output = execute_svn_command(["svn", "status"], cwd=target_dir)

    if status_output:
        print("⚠ エラー: 未コミットの変更が検出されました。以下のファイルが影響を受けています:")
        print(status_output)
        print("処理を中止します。変更をコミットまたはリバートしてください。")
        sys.exit(1)

def update_svn_to_latest(target_dir):
    """ SVN update を実行し、リポジトリの最新状態に更新 """
    print("▶ SVNリポジトリを最新状態に更新中...")
    update_output = execute_svn_command(["svn", "update"], cwd=target_dir)
    print(update_output)

def copy_files(src, dest):
    """ ファイル・ディレクトリを再帰的にコピー（既存ファイルは上書き） """
    if not os.path.exists(src):
        print(f"エラー: 更新用のディレクトリが存在しません -> {src}")
        sys.exit(1)
    
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dest_path = os.path.join(dest, rel_path)

        os.makedirs(dest_path, exist_ok=True)

        for file in files:
            shutil.copy2(os.path.join(root, file), os.path.join(dest_path, file))

def delete_removed_files(target_dir, update_path):
    """ update_path に存在しないファイルを SVN から削除する """
    print("▶ 削除すべきファイルを確認中...")
    target_files = set()
    update_files = set()

    for root, _, files in os.walk(target_dir):
        for file in files:
            target_files.add(os.path.relpath(os.path.join(root, file), target_dir))

    for root, _, files in os.walk(update_path):
        for file in files:
            update_files.add(os.path.relpath(os.path.join(root, file), update_path))

    files_to_delete = target_files - update_files

    if files_to_delete:
        print("🗑 削除予定のファイル:")
        for file in files_to_delete:
            print(f"  - {file}")
            execute_svn_command(["svn", "delete", "--force", file], cwd=target_dir)
    else:
        print("🔹 削除するファイルはありません。")

def svn_update_and_commit(target_dir, update_path, tag_url=None, dryrun=False, quiet=False):
    """ SVNリポジトリを更新し、コミットしてタグを作成する """
    if not os.path.exists(target_dir):
        print(f"エラー: 指定されたリポジトリディレクトリが存在しません -> {target_dir}")
        sys.exit(1)

    # SVNステータスをチェック（変更があれば処理中止）
    check_svn_status(target_dir)

    # SVNリポジトリURLをチェック
    remote_url = check_remote_url(target_dir)

    # SVNリポジトリを最新状態に更新
    update_svn_to_latest(target_dir)

    print(f"▶ ファイルをコピー中: {update_path} → {target_dir}")
    copy_files(update_path, target_dir)

    # 更新ディレクトリにないファイルを削除
    delete_removed_files(target_dir, update_path)

    print("▶ SVNの変更を追加")
    execute_svn_command(["svn", "add", "--force", "."], cwd=target_dir)

    if dryrun:
        print("🔍 Dry-runモード: コミットおよびタグ作成はスキップします。")
        return

    commit_message = f"Auto-commit from {update_path}  at  {datetime.datetime.now()}"
    while (quiet == False):
        input_msg = input(f'コミットメッセージを入力してください : ')
        if (input_msg == ''):
            input_msg = commit_message

        if tag_url:
            input_key = input(f'{input_msg} のメッセージでコミットし、\n{tag_url} のTAGを作成します。\n宜しいですか？ (Yes / No / Cancel)')
        else:
            input_key = input(f'{input_msg} のメッセージでコミットして宜しいですか？ (Yes / No / Cancel)')

        if (input_key.upper() == 'C') or (input_key.upper() == 'CANCEL'): 
            print("コミットをキャンセルしました")
            return
        elif (input_key.upper() == 'Y') or (input_key.upper() == 'YES'): 
            commit_message = input_msg
            quiet = True

    print("▶ SVNの変更をコミット")

    execute_svn_command(["svn", "commit", "-m", commit_message], cwd=target_dir)

    if tag_url:
        print(f"▶ SVNのタグを作成: {tag_url}")
        execute_svn_command(["svn", "copy", remote_url, tag_url, "-m", commit_message])

    print("✅ SVNアップデート & コミット完了")
    return

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 6:
        print("使い方: svn_update.py [target(checkouted) directory] [update code path] [tag url (省略可)] [--dryrun (省略可)] [--quiet (省略可)]")
        sys.exit(1)

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
