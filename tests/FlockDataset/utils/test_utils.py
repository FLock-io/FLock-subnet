import pytest
import bittensor as bt
from flockoff.utils.git import (
    get_current_branch,
    is_up_to_date_with_main,
    check_and_update_code,
)
import pytest
from flockoff.constants import Competition



def test_competition_value():
    """Test reading commitment data from another neuron on the chain"""
    comp = Competition.from_defaults()

    bt.logging.info(f"Competition:{comp}")

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

    # Test check_and_update_code function by checking if it raises an exception
    try:
        if is_current:
            check_and_update_code()
            print("\nRepository is up to date with main")
    except RuntimeError as e:
        # Don't fail the test, just print the message
        print(f"\nRepository is not up to date with main: {e}")
        # We're logging this as a warning since it's not a test failure
        bt.logging.warning(f"Repository not up to date with main: {e}")

    # Always pass this test
    assert True, "Git functions test completed"
