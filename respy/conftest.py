import numpy as np
import pandas as pd
import pytest

from development.testing.regression.run_regression import load_regression_tests
from respy.solve import create_state_space
from respy.solve import StateSpace


@pytest.fixture(autouse=True)
def make_imports_available_in_doctest_namespaces(doctest_namespace):
    """Make imports available in doctest namespaces.

    As a suggestion, we should only include imports which are very common.

    """
    doctest_namespace["pd"] = pd
    doctest_namespace["pyth_create_state_space"] = create_state_space
    doctest_namespace["StateSpace"] = StateSpace


@pytest.fixture(scope="function", autouse=True)
def set_seed():
    """Each test is executed with the same random seed."""
    np.random.seed(1423)


@pytest.fixture(scope="function", autouse=True)
def fresh_directory(tmpdir):
    """Each test is executed in a fresh directory."""
    tmpdir.chdir()


@pytest.fixture(scope="session")
def regression_vault():
    """Make regression vault available to tests."""
    return load_regression_tests()
