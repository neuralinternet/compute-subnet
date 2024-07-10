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
from packaging import version as packaging_version


def get_remote_version_to_number(pattern: str = "__version__"):
    latest_version = version2number(get_remote_version(pattern=pattern))
    if not latest_version:
        bt.logging.error("Github API call failed or version string is incorrect!")
    return latest_version


def version2number(version: str):
    try:
        if version and isinstance(version, str):
            version_parts = version.split(".")
            return (100 * int(version_parts[0])) + (10 * int(version_parts[1])) + (1 * int(version_parts[2]))
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
            bt.logging.error(f"Failed to get file content with status code: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        bt.logging.error("The request timed out after 30 seconds.")
        return None
    except requests.exceptions.RequestException as e:
        bt.logging.error(f"There was an error while handling the request: {e}")
        return None


def get_local_version():
    try:
        here = path.abspath(path.dirname(__file__))
        parent = here.rsplit("/", 1)[0]
        init_file_path = os.path.join(parent, "__init__.py")
        
        with codecs.open(init_file_path, encoding="utf-8") as init_file:
            content = init_file.read()
            version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", content, re.M)
            version_string = version_match.group(1)
        return version_string
    except Exception as e:
        bt.logging.error(f"Error getting local version: {e}")
        return ""


def check_version_updated():
    remote_version = get_remote_version()
    local_version = get_local_version()
    bt.logging.info(f"Version check - remote_version: {remote_version}, local_version: {local_version}")

    if packaging_version.parse(local_version) < packaging_version.parse(remote_version):
        bt.logging.info("👩‍👦Update to the latest version is required")
        return True
    else:
        return False


def update_repo():
    try:
        repo = git.Repo(search_parent_directories=True)
        origin = repo.remotes.origin

        bt.logging.info(f"Current repository path: {repo.working_dir}")

        # Check for detached HEAD state
        if repo.head.is_detached:
            bt.logging.info("Repository is in a detached HEAD state. Switching to the main branch.")
            repo.git.checkout('main')

        bt.logging.info(f"Current branch: {repo.active_branch.name}")

        stashed = False
        if repo.is_dirty(untracked_files=True):
            bt.logging.info("Stashing uncommitted changes")
            repo.git.stash('push', '-m', 'Auto stash before updating')
            stashed = True

        try:
            bt.logging.info("Try pulling remote repository")
            origin.pull(rebase=True)
            bt.logging.info("Pulling success")

            if stashed:
                bt.logging.info("Applying stashed changes")
                repo.git.stash('apply', '--index')
                
                # Restore the specific file from remote to ensure it is not overwritten by stash
                repo.git.checkout('origin/main', '--', 'compute/__init__.py')

            return True
        except git.exc.GitCommandError as e:
            bt.logging.info(f"Update: Merge conflict detected: {e}. Recommend you manually commit changes and update")
            if stashed:
                repo.git.stash('pop')
            return handle_merge_conflict(repo)
    except Exception as e:
        bt.logging.error(f"Update failed: {e}. Recommend you manually commit changes and update")
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
        bt.logging.info("Merge conflicts resolved, repository updated to remote state.")
        bt.logging.info("✅ Repo update success")
        return True
    except git.GitCommandError as e:
        bt.logging.error(f"Update failed: {e}. Recommend you manually commit changes and update")
        return False


def restart_app():
    bt.logging.info("👩‍🦱App restarted due to the update")

    python = sys.executable
    os.execl(python, python, *sys.argv)


def try_update_packages(force=False):
    bt.logging.info("Try updating packages...")

    try:
        repo = git.Repo(search_parent_directories=True)
        repo_path = repo.working_tree_dir

        requirements_path = os.path.join(repo_path, "requirements.txt")

        if not os.path.exists(requirements_path):
            bt.logging.error("Requirements file does not exist.")
            return

        python_executable = sys.executable

        if force:
            subprocess.check_call([
                python_executable, "-m", "pip", "install", "--force-reinstall", "--ignore-installed", "--no-deps", "-r", requirements_path
            ])
            subprocess.check_call([
                python_executable, "-m", "pip", "install", "--force-reinstall", "--ignore-installed", "--no-deps", "-e", repo_path
            ])
        else:
            subprocess.check_call([python_executable, "-m", "pip", "install", "-r", requirements_path])
            subprocess.check_call([python_executable, "-m", "pip", "install", "-e", repo_path])

        bt.logging.info("📦Updating packages finished.")
    except subprocess.CalledProcessError as e:
        bt.logging.error(f"Updating packages failed: {e}")
        if not force:
            try_update_packages(force=True)


def try_update():
    try:
        if check_version_updated():
            bt.logging.info("Found the latest version in the repo. Try ♻️update...")
            if update_repo():
                try_update_packages()
                # Check if the update was successful by comparing the version again
                if not check_version_updated():
                    bt.logging.info("Update process completed successfully.")
                    # Restart the app only if necessary (for example, after all processes are done)
                    restart_app()
                else:
                    bt.logging.info("Update process failed to update the version.")
    except Exception as e:
        bt.logging.error(f"Try updating failed: {e}")


def check_hashcat_version(hashcat_path: str = "hashcat"):
    try:
        process = subprocess.run([hashcat_path, "--version"], capture_output=True, check=True)
        if process and process.stdout:
            bt.logging.info(f"Version of hashcat found: {process.stdout.decode().strip()}")
        return True
    except subprocess.CalledProcessError:
        bt.logging.error(
            "Hashcat is not available nor installed on the machine. Please make sure hashcat is available in your PATH or give the explicit location using the following argument: --miner.hashcat.path"
        )
        exit()