"""
The MIT License (MIT)
Copyright © 2023 demon

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the “Software”), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import codecs
import os
import re
import subprocess
from os import path

import bittensor as bt
import git
import requests
import sys


def get_remote_version_to_number(pattern: str = "__version__"):
    latest_version = version2number(get_remote_version(pattern=pattern))
    if not latest_version:
        bt.logging.error(f"Github API call failed or version string is incorrect!")
    return latest_version


def version2number(version: str):
    try:
        if version and type(version) is str:
            version = version.split(".")
            return (100 * int(version[0])) + (10 * int(version[1])) + (1 * int(version[2]))
    except Exception as _:
        pass
    return None


def get_remote_version(pattern: str = "__version__"):
    url = "https://raw.githubusercontent.com/neuralinternet/compute-subnet/main/compute/__init__.py"
    try:
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            lines = response.text.split("\n")
            for line in lines:
                if line.startswith(pattern):
                    version_info = line.split("=")[1].strip(" \"'").replace('"', "")
                    return version_info
        else:
            print("Failed to get file content with status code:", response.status_code)
            return None
    except requests.exceptions.Timeout:
        print("The request timed out after 30 seconds.")
        return None
    except requests.exceptions.RequestException as e:
        print("There was an error while handling the request:", e)
        return None


def get_local_version():
    try:
        # loading version from __init__.py
        here = path.abspath(path.dirname(__file__))
        parent = here.rsplit("/", 1)[0]
        with codecs.open(os.path.join(parent, "__init__.py"), encoding="utf-8") as init_file:
            version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", init_file.read(), re.M)
            version_string = version_match.group(1)
        return version_string
    except Exception as e:
        bt.logging.error(f"Error getting local version. : {e}")
        return ""


def check_version_updated():
    remote_version = get_remote_version()
    local_version = get_local_version()
    bt.logging.info(f"Version check - remote_version: {remote_version}, local_version: {local_version}")

    if version2number(local_version) < version2number(remote_version):
        bt.logging.info(f"👩‍👦Update to the latest version is required")
        return True
    else:
        return False


def update_repo():
    try:
        repo = git.Repo(search_parent_directories=True)

        origin = repo.remotes.origin

        if repo.is_dirty(untracked_files=True):
            bt.logging.error("Update failed: Uncommited changes detected. Please commit changes or run `git stash`")
            return False
        try:
            bt.logging.info("Try pulling remote repository")
            origin.pull()
            bt.logging.info("pulling success")
            return True
        except git.exc.GitCommandError as e:
            bt.logging.info(f"update : Merge conflict detected: {e} Recommend you manually commit changes and update")
            return handle_merge_conflict(repo)

    except Exception as e:
        bt.logging.error(f"update failed: {e} Recommend you manually commit changes and update")

    return False


def handle_merge_conflict(repo):
    try:
        repo.git.reset("--merge")
        origin = repo.remotes.origin
        current_branch = repo.active_branch
        origin.pull(current_branch.name)

        for item in repo.index.diff(None):
            file_path = item.a_path
            bt.logging.info(f"Resolving conflict in file: {file_path}")
            repo.git.checkout("--theirs", file_path)
        repo.index.commit("Resolved merge conflicts automatically")
        bt.logging.info(f"Merge conflicts resolved, repository updated to remote state.")
        bt.logging.info(f"✅ Repo update success")
        return True
    except git.GitCommandError as e:
        bt.logging.error(f"update failed: {e} Recommend you manually commit changes and update")
        return False


def restart_app():
    bt.logging.info("👩‍🦱app restarted due to the update")

    python = sys.executable
    os.execl(python, python, *sys.argv)


def try_update_packages():
    bt.logging.info("Try updating packages...")

    try:
        repo = git.Repo(search_parent_directories=True)
        repo_path = repo.working_tree_dir

        requirements_path = os.path.join(repo_path, "requirements.txt")

        python_executable = sys.executable
        subprocess.check_call([python_executable], "-m", "pip", "install", "-r", requirements_path)
        subprocess.check_call([python_executable], "-m", "pip", "install", "-e", ".")
        bt.logging.info("📦Updating packages finished.")

    except Exception as e:
        bt.logging.info(f"Updating packages failed {e}")


def try_update():
    try:
        if check_version_updated() is True:
            bt.logging.info("found the latest version in the repo. try ♻️update...")
            if update_repo() is True:
                try_update_packages()
                restart_app()
    except Exception as e:
        bt.logging.info(f"Try updating failed {e}")


def check_hashcat_version(hashcat_path: str = "hashcat"):
    try:
        process = subprocess.run([hashcat_path, "--version"], capture_output=True, check=True)
        if process and process.stdout:
            bt.logging.info(f"Version of hashcat found: {process.stdout.decode()}".strip('\n'))
        return True
    except subprocess.CalledProcessError:
        bt.logging.error(
            f"Hashcat is not available nor installed on the machine. Please make sure hashcat is available in your PATH or give the explicit location using the following argument: --miner.hashcat.path"
        )
        exit()
