import os
from huggingface_hub import HfApi


def upload_data(repo_name: str, local_file_path: str) -> str:
    api = HfApi(token=os.environ["HF_TOKEN"])
    try:
        api.create_repo(
            repo_name,
            exist_ok=False,
            repo_type="dataset",
        )
    except Exception:
        print(
            f"Repo {repo_name} already exists. Will commit the new version."
        )

    commit_message = api.upload_file(
        path_or_fileobj=local_file_path,
        path_in_repo="data.jsonl",
        repo_id=repo_name,
        repo_type="dataset",
    )
    # get commit hash
    commit_hash = commit_message.oid
    print(f"Commit hash: {commit_hash}")
    print(f"Repo name: {repo_name}")
    return commit_hash
