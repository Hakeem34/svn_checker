#!/usr/bin/env python3
import datetime
import errno
import os
import shutil
import subprocess
import sys
from pathlib import Path


g_target_path = ""
g_revision1 = ""
g_revision2 = ""
g_out_timestamp = ""
g_out_path = ""
g_right_only = 0
g_report_by_winmerge = 0
g_opt_ts = 1
g_cached = 0


def print_usage():
    print("Usage:")
    print("  python git_diff_ex.py [target_path] [-b rev1:rev2 | -b rev2] [--cached] [-o outpath] [--no_timestamp] [--rightonly]")
    print("")
    print("Examples:")
    print("  python git_diff_ex.py . -b HEAD~1:HEAD -o out")
    print("  python git_diff_ex.py src -b main:feature -o diff_export")
    print("  python git_diff_ex.py . --cached -o staged")


def check_command_line_option():
    global g_target_path
    global g_revision1
    global g_revision2
    global g_out_timestamp
    global g_out_path
    global g_right_only
    global g_report_by_winmerge
    global g_opt_ts
    global g_cached

    argv = sys.argv[1:]
    option = ""

    for arg in argv:
        if option == "b":
            if ":" in arg:
                rev1, rev2 = arg.split(":", 1)
                g_revision1 = rev1
                g_revision2 = rev2
            else:
                g_revision2 = arg
                g_revision1 = ""
            option = ""
        elif option == "o":
            g_out_path = arg
            option = ""
        elif arg in ("-t", "--timestamp"):
            g_opt_ts = 1
        elif arg in ("-nt", "--no_timestamp"):
            g_opt_ts = 0
        elif arg in ("-b", "--base", "-r", "--revision"):
            option = "b"
        elif arg in ("-o", "--outpath"):
            option = "o"
        elif arg in ("-ro", "--rightonly"):
            g_right_only = 1
        elif arg in ("-wmr", "--report_by_winmerge"):
            g_report_by_winmerge = 1
        elif arg in ("--cached", "--staged"):
            g_cached = 1
        elif arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif g_target_path == "":
            g_target_path = arg
        else:
            print("git_diff_ex.py : Too many paths!")
            sys.exit(-1)

    if g_opt_ts:
        now = datetime.datetime.now()
        g_out_timestamp = now.strftime("%Y%m%d_%H%M%S")


def make_directory(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def set_time_stamp(out_path):
    global g_out_timestamp
    if g_out_timestamp != "":
        return out_path + "_" + g_out_timestamp
    return out_path


def set_output_path(target_path):
    global g_out_path

    if g_out_path != "":
        return set_time_stamp(g_out_path)

    if target_path != "":
        if os.path.isdir(target_path):
            return set_time_stamp(os.path.join(os.path.dirname(target_path), "diff_export"))
        return set_time_stamp(os.path.join(os.getcwd(), "diff_export"))

    return set_time_stamp(os.path.join(os.getcwd(), "diff_export"))


def run_git_command(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=False)
    return result


def find_repo_root(start_path):
    current = os.path.abspath(start_path or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    result = run_git_command(["git", "rev-parse", "--show-toplevel"], cwd=start_path or os.getcwd())
    if result.returncode == 0:
        return result.stdout.decode("utf-8", "replace").strip()

    raise RuntimeError("git repository was not found")


def normalize_rel_path(path, repo_root):
    rel_path = os.path.relpath(path, repo_root)
    return rel_path.replace("\\", "/")


def resolve_revision(revision, repo_root):
    if revision == "":
        return ""
    result = run_git_command(["git", "rev-parse", "--verify", revision], cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(f"failed to resolve revision: {revision}")
    return result.stdout.decode("utf-8", "replace").strip()


def collect_changed_files(repo_root, target_path, revision1, revision2):
    global g_cached

    args = ["git", "diff", "--name-status", "--find-renames"]
    if g_cached:
        args.append("--cached")
    if revision1 != "" and revision2 != "":
        args.append(revision1)
        args.append(revision2)

    if target_path != "":
        rel_target = normalize_rel_path(target_path, repo_root)
        if rel_target == ".":
            rel_target = ""
        if rel_target:
            args.extend(["--", rel_target])

    result = run_git_command(args, cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())

    entries = []
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") or status.startswith("C"):
            if len(parts) >= 3:
                entries.append((status, parts[1], parts[2]))
        else:
            if len(parts) >= 2:
                entries.append((status, parts[1], parts[1]))
    return entries


def export_git_path(repo_root, revision, rel_path, out_file):
    result = run_git_command(["git", "show", f"{revision}:{rel_path}"], cwd=repo_root)
    if result.returncode != 0:
        return False

    with open(out_file, "wb") as handle:
        handle.write(result.stdout)
    return True


def export_index_path(repo_root, rel_path, out_file):
    result = run_git_command(["git", "show", f":{rel_path}"], cwd=repo_root)
    if result.returncode != 0:
        return False

    with open(out_file, "wb") as handle:
        handle.write(result.stdout)
    return True


def export_worktree_path(repo_root, rel_path, out_file):
    src_path = os.path.join(repo_root, rel_path)
    if os.path.isfile(src_path):
        shutil.copy2(src_path, out_file)
        return True

    with open(out_file, "w", encoding="utf-8") as handle:
        handle.write(f"File not present in working tree: {rel_path}\n")
    return False


def export_diff(repo_root, entries, out_root, right_only):
    global g_cached

    for status, before_path, after_path in entries:
        before_rel = before_path.replace("\\", "/")
        after_rel = after_path.replace("\\", "/")

        if right_only:
            out_dir = os.path.join(out_root, os.path.dirname(after_rel))
            make_directory(out_dir)
            out_file = os.path.join(out_dir, os.path.basename(after_rel))
            if g_revision1 != "" and g_revision2 != "":
                export_git_path(repo_root, g_revision2, after_rel, out_file)
            elif g_cached:
                export_index_path(repo_root, after_rel, out_file)
            else:
                export_worktree_path(repo_root, after_rel, out_file)
        else:
            before_dir = os.path.join(out_root, "01_before", os.path.dirname(before_rel))
            make_directory(before_dir)
            before_file = os.path.join(before_dir, os.path.basename(before_rel))
            after_dir = os.path.join(out_root, "02_after", os.path.dirname(after_rel))
            make_directory(after_dir)
            after_file = os.path.join(after_dir, os.path.basename(after_rel))

            if g_revision1 != "" and g_revision2 != "":
                export_git_path(repo_root, g_revision1, before_rel, before_file)
                export_git_path(repo_root, g_revision2, after_rel, after_file)
            elif g_cached:
                export_git_path(repo_root, "HEAD", before_rel, before_file)
                export_index_path(repo_root, after_rel, after_file)
            else:
                export_index_path(repo_root, before_rel, before_file)
                export_worktree_path(repo_root, after_rel, after_file)


def main():
    global g_revision1
    global g_revision2
    global g_cached

    check_command_line_option()

    if g_revision1 == "" and g_revision2 != "" and not g_cached:
        g_revision1 = g_revision2 + "^"

    target_path = g_target_path
    if target_path != "" and not os.path.exists(target_path):
        print(f"git_diff_ex.py : target path does not exist: {target_path}")
        sys.exit(-1)

    out_path = set_output_path(target_path)
    make_directory(out_path)

    repo_root = find_repo_root(target_path or os.getcwd())
    repo_root = os.path.abspath(repo_root)

    g_revision1 = resolve_revision(g_revision1, repo_root) if g_revision1 != "" else ""
    g_revision2 = resolve_revision(g_revision2, repo_root) if g_revision2 != "" else ""

    print("Repository Root : %s" % repo_root)
    print("Left  Revision  : %s" % g_revision1)
    print("Right Revision  : %s" % g_revision2)
    print("Output Path     : %s" % out_path)

    entries = collect_changed_files(repo_root, target_path, g_revision1, g_revision2)
    if not entries:
        print("No changed files were found.")
        return

    export_diff(repo_root, entries, out_path, g_right_only)

    if g_report_by_winmerge:
        print("Report by WinMerge: requested but not implemented in this Git version.")


if __name__ == "__main__":
    main()
