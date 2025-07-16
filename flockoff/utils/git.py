import os
import subprocess
import sys
import configparser
import bittensor as bt
from flockoff import constants
from flockoff.validator.database import ScoreDB

def run_git_command(command, check=True, capture_output=False):
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            check=check,
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        bt.logging.error(f"Git command failed: {' '.join(command)}\n{e}")
        return None


def get_current_branch():
    return run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True)


def has_uncommitted_changes():
    return bool(run_git_command(["git", "status", "--porcelain"], capture_output=True))


def is_up_to_date_with_main():

    bt.logging.info("Fetching latest commits from origin/main")
    run_git_command(["git", "fetch", "origin", "main"], check=True)

    main_commit = run_git_command(["git", "rev-parse", "origin/main"], capture_output=True)
    current_commit = run_git_command(["git", "rev-parse", "HEAD"], capture_output=True)

    if main_commit and current_commit and main_commit == current_commit:
        bt.logging.info("Current branch is up to date with origin/main")
        return True
    bt.logging.error("Current branch is not up to date with origin/main")
    return False


def update_to_latest():

    current_branch = get_current_branch()
    if not current_branch:
        bt.logging.error("Failed to determine current git branch. Is this a git repository?")
        sys.exit(1)

    bt.logging.info(f"Current git branch: {current_branch}")

    if is_up_to_date_with_main():
        bt.logging.info("Repository is already up to date with the latest code from main")
        return True

    bt.logging.info("Repository is not up to date. Starting update process...")

    if current_branch != "main":
        bt.logging.info(f"Switching from '{current_branch}' to 'main' branch...")
        run_git_command(["git", "checkout", "main"])

    bt.logging.info("Pulling latest changes from origin/main...")
    run_git_command(["git", "pull", "origin", "main"])

    if is_up_to_date_with_main():
        bt.logging.info("Successfully updated to latest code from main")
        purge = configparser.ConfigParser()
        purge.read('flockoff/validator/config.ini')
        if purge.getboolean('settings', 'score_db_purge', fallback=False):
            bt.logging.info("removing scores.db")
            os.remove("scores.db")
        python = sys.executable
        # restart the project.
        bt.logging.info("Restart the project.")
        os.execv(python, [python] + sys.argv)
    bt.logging.error("Failed to update repository. Exiting...")
    sys.exit(1)


def check_and_update_code():
    bt.logging.info("Starting automatic code update process...")
    return update_to_latest()
