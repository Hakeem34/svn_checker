import argparse
import os
import subprocess
import sys


def open_folder_and_cmd(target_path):
    # 絶対パスに変換
    abs_path = os.path.abspath(target_path)

    # フォルダが存在するかチェック
    if not os.path.exists(abs_path):
        print(f"エラー: 指定されたパスが存在しません -> {abs_path}")
        sys.exit(1)

    if not os.path.isdir(abs_path):
        print(f"エラー: 指定されたパスはフォルダではありません -> {abs_path}")
        sys.exit(1)

    print(f"対象フォルダ: {abs_path}")

    try:
        # 1. Windowsエクスプローラーで開く
        subprocess.Popen(["explorer", abs_path])
        print("-> エクスプローラーを開きました")

        # 2. コマンドプロンプトを開く (修正ポイント)
        # コマンド全体を1つの文字列にし、shell=True で Windows のシェル経由で安全に実行します
        cmd_command = f'start cmd /K "cd /D {abs_path}"'
        subprocess.Popen(cmd_command, shell=True)
        print("-> コマンドプロンプトを開きました")

    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="指定されたフォルダをエクスプローラーとコマンドプロンプトで開きます。"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="開きたいフォルダのパス (省略時はカレントディレクトリ)",
    )

    args = parser.parse_args()
    open_folder_and_cmd(args.path)
