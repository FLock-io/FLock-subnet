import pytest
import bittensor as bt
from flockoff.utils.git import (
    get_current_branch,
    is_up_to_date_with_main,
    check_latest_code,
)
from flockoff.utils.chain import read_chain_commitment
import pytest

# SUBNET_OWNER_KEY = "5DFcEniKrQRbCakLFGY3UqPL3ZbNnTQHp8LTvLfipWhE2Yfr"
# SUBNET_OWNER_KEY = "5FZGwrY9Ycz8m6fq5rpZCgoSrQWddb7SnZCr3rFU61auctG2"
SUBNET_OWNER_KEY = "5Cex1UGEN6GZBcSBkWXtrerQ6Zb7h8eD7oSe9eDyZmj4doWu"


@pytest.fixture
def node():
    """Create a subtensor with test network connection"""
    return bt.subtensor("test")


def test_read_chain_commitment(node):
    """Test reading commitment data from another neuron on the chain"""
    subnet_uid = 257
    key = SUBNET_OWNER_KEY

    comp = read_chain_commitment(key, node, subnet_uid)

    print(comp)

    assert comp is not None, "Should return a valid commitment"

    assert isinstance(comp.id, str), f"ID should be a string, got {type(comp.id)}"
    assert isinstance(comp.repo, str), f"Repo should be a string, got {type(comp.repo)}"
    assert isinstance(
        comp.bench, float
    ), f"Bench should be a float, got {type(comp.bench)}"
    assert isinstance(comp.rows, int), f"Rows should be an int, got {type(comp.rows)}"
    assert isinstance(comp.pow, int), f"Pow should be an int, got {type(comp.pow)}"
    for attr in ("minb", "maxb", "bheight"):
        assert isinstance(getattr(comp, attr), float), f"{attr} should be a float"

    assert comp.id, "ID should not be empty"
    assert comp.repo, "Repo should not be empty"
    assert comp.bench > 0, f"Bench should be positive, got {comp.bench}"
    assert comp.rows > 0, f"Rows should be positive, got {comp.rows}"
    assert comp.pow >= 0, f"Pow should be non-negative, got {comp.pow}"
    assert comp.minb >= 0, f"Minb should be non-negative, got {comp.minb}"
    assert comp.maxb >= 0, f"Maxb should be non-negative, got {comp.maxb}"
    assert comp.bheight >= 0, f"Bheight should be non-negative, got {comp.bheight}"
    assert (
        comp.minb <= comp.maxb
    ), f"Minb should be less than or equal to maxb, got {comp.minb} > {comp.maxb}"
    assert (
        comp.bheight <= comp.maxb
    ), f"Bheight should be less than or equal to maxb, got {comp.bheight} > {comp.maxb}"
    assert (
        comp.bheight >= comp.minb
    ), f"Bheight should be greater than or equal to minb, got {comp.bheight} < {comp.minb}"

    bt.logging.info(
        f"Commitment values: id={comp.id}, repo={comp.repo}, bench={comp.bench}, rows={comp.rows}, pow={comp.pow}"
    )


def test_git_functions():
    """
    Test the git utility functions.

    This test doesn't use mocks and interacts with the actual git repository.
    It verifies that the functions work but doesn't fail the test if not up to date.
    """
    # Get current branch
    branch = get_current_branch()
    assert branch is not None, "Should be able to get current branch name"

    # Check if up to date
    is_current = is_up_to_date_with_main()
    # This is just informational, not a failure condition
    print(f"\nCurrent branch: {branch}, Up to date with main: {is_current}")

    # Test check_latest_code function by checking if it raises an exception
    try:
        check_latest_code()
        print("\nRepository is up to date with main")
    except RuntimeError as e:
        # Don't fail the test, just print the message
        print(f"\nRepository is not up to date with main: {e}")
        # We're logging this as a warning since it's not a test failure
        bt.logging.warning(f"Repository not up to date with main: {e}")

    # Always pass this test
    assert True, "Git functions test completed"
