import os
import subprocess
import warnings

# Define the environment variable name for disabling the check
DISABLE_COMMIT_CHECK_ENV_VAR = "FLOCK_DISABLE_COMMIT_CHECK"

def get_configured_remote_url(remote_name: str = "origin", repo_path: str = ".") -> str | None:
    """
    Retrieves the URL of the specified remote from the local Git configuration.

    Args:
        remote_name: The name of the remote (e.g., "origin"). Defaults to "origin".
        repo_path: The path to the local repository. Defaults to the current directory.

    Returns:
        The URL of the remote as a string, or None if an error occurs.
    """
    try:
        remote_url = subprocess.check_output(
            ['git', 'remote', 'get-url', remote_name],
            cwd=repo_path,
            stderr=subprocess.PIPE
        ).strip().decode('utf-8')
        return remote_url.splitlines()[0]
    except subprocess.CalledProcessError as e:
        warnings.warn(f"Error getting URL for remote '{remote_name}': {e}. Ensure the remote exists and you are in a git repository.")
        return None
    except FileNotFoundError:
        warnings.warn("Git command not found. Ensure git is installed and in your PATH.")
        return None

def get_local_commit_hash(repo_path: str = ".") -> str | None:
    """
    Retrieves the current git commit hash of the local repository.

    Args:
        repo_path: The path to the local repository. Defaults to the current directory.

    Returns:
        The current commit hash as a string, or None if an error occurs (e.g., not a git repository).
    """
    try:
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_path,
            stderr=subprocess.PIPE
        ).strip().decode('utf-8')
        return commit_hash
    except subprocess.CalledProcessError as e:
        warnings.warn(f"Error getting local commit hash: {e}. Ensure you are in a git repository.")
        return None
    except FileNotFoundError:
        warnings.warn("Git command not found. Ensure git is installed and in your PATH.")
        return None

def get_remote_latest_commit_hash(repo_url: str) -> str | None:
    """
    Retrieves the latest commit hash from the HEAD of the specified remote repository.

    Args:
        repo_url: The URL of the remote git repository.

    Returns:
        The latest commit hash of the main/master branch as a string, or None if an error occurs.
    """
    try:
        # Fetches the HEAD reference (usually main or master)
        remote_output = subprocess.check_output(
            ['git', 'ls-remote', repo_url, 'HEAD'],
            stderr=subprocess.PIPE
        ).strip().decode('utf-8')
        if not remote_output:
            warnings.warn(f"No output from git ls-remote for {repo_url} HEAD. The repository might be empty or inaccessible.")
            return None
        commit_hash = remote_output.split('\t')[0]
        return commit_hash
    except subprocess.CalledProcessError as e:
        warnings.warn(f"Error getting remote commit hash for {repo_url}: {e}")
        return None
    except FileNotFoundError:
        warnings.warn("Git command not found. Ensure git is installed and in your PATH.")
        return None

def is_running_latest_commit(
    disable_check_env_var: str = DISABLE_COMMIT_CHECK_ENV_VAR,
    local_repo_path: str = ".",
    target_remote_name: str = "origin"
) -> bool:
    """
    Checks if the local repository is running the latest commit from its configured remote (default 'origin').
    This function compares the local HEAD commit with the remote repository's HEAD commit.
    The check can be disabled by setting the specified environment variable to 'true'.

    Args:
        disable_check_env_var: The name of the environment variable to disable this check.
                               If set to 'true' (case-insensitive), the check is skipped.
        local_repo_path: The file system path to the local git repository.
        target_remote_name: The name of the git remote to check against (e.g., "origin").

    Returns:
        True if the local commit is the latest, or if the check is disabled, or if remote URL cannot be determined.
        False if the local commit is not the latest.
        Prints warnings if git commands fail or if not in a git repository.
    """
    if os.environ.get(disable_check_env_var, 'false').lower() == 'true':
        print(f"Commit check disabled via environment variable {disable_check_env_var}.")
        return True

    local_commit = get_local_commit_hash(local_repo_path)
    if local_commit is None:
        warnings.warn("Could not determine local commit hash. Skipping version check.")
        return True

    configured_remote_url = get_configured_remote_url(remote_name=target_remote_name, repo_path=local_repo_path)
    if configured_remote_url is None:
        warnings.warn(f"Could not determine URL for remote '{target_remote_name}'. Skipping version check.")
        return True
    
    print(f"Checking against remote URL: {configured_remote_url}")
    remote_commit = get_remote_latest_commit_hash(configured_remote_url)
    if remote_commit is None:
        warnings.warn(f"Could not determine remote commit hash from {configured_remote_url}. Skipping version check.")
        return True

    if local_commit == remote_commit:
        print("Local repository is up to date with the remote.")
        return True
    else:
        print(f"Local commit {local_commit} does not match remote commit {remote_commit}.")
        return False

if __name__ == '__main__':

    print("Performing commit check...")
    latest = is_running_latest_commit(local_repo_path=".") # Assuming script is run from repo root
    if not latest:
        print("Warning: You are not running the latest commit from the Flock-subnet repository.")
    else:
        print("Commit check passed or was skipped.")