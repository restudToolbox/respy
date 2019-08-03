"""Create, run or investigate regression checks."""
import functools
import pickle
import socket
from multiprocessing import Pool

import click
import numpy as np

import respy as rp
from development.testing.notifications import send_notification
from respy.config import TEST_RESOURCES_DIR
from respy.config import TOL
from respy.tests.random_model import generate_random_model
from respy.tests.random_model import simulate_truncated_data


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _prepare_message(idx_failures):
    hostname = socket.gethostname()
    subject = " respy: Regression Testing"
    if idx_failures:
        message = (
            f"Failure during regression testing @{hostname} for test(s): "
            f"{idx_failures}."
        )
    else:
        message = f"Regression testing is completed on @{hostname}."

    return subject, message


def calc_crit_val(params, options):
    df = simulate_truncated_data(params, options)

    crit_func = rp.get_crit_func(params, options, df)
    crit_val = crit_func(params)

    return crit_val


def run_regression_tests(n_tests, n_processes, strict, notification):
    """Run regression tests.

    Parameters
    ----------
    n_tests : int
        Number of tests to run. If None, all are run.
    tests : list
        List of regression tests. If None, tests are loaded from disk.
    n_processes : int
        Number of processes. Default 1.

    """
    tests = load_regression_tests()
    tests = tests[:n_tests]

    check_single_ = functools.partial(check_single, strict=strict)
    with Pool(n_processes) as p:
        ret = p.map(check_single_, tests)

    idx_failures = [i for i, x in enumerate(ret) if not x]

    if idx_failures:
        click.secho(f"Failures: {idx_failures}", fg="red")
    else:
        click.secho(f"Tests succeeded.", fg="green")

    subject, message = _prepare_message(idx_failures)

    if notification:
        send_notification(subject, message)


def create_regression_tests(n_tests, n_processes, save):
    """Create a regression vault.

    Parameters
    ----------
    n_tests : int
        How many tests are in the vault.
    n_processes : int, default 1
        Number of processes.

    """
    with Pool(n_processes) as p:
        tests = p.map(create_single, range(n_tests))

    if save:
        with open(TEST_RESOURCES_DIR / "regression_vault.pickle", "wb") as p:
            pickle.dump(tests, p)


def load_regression_tests():
    """Load regression tests from disk."""
    with open(TEST_RESOURCES_DIR / "regression_vault.pickle", "rb") as p:
        tests = pickle.load(p)

    return tests


def investigate_regression_test(idx):
    """Investigate regression tests."""
    tests = load_regression_tests()
    params, options, exp_val = tests[idx]

    crit_val = calc_crit_val(params, options)

    assert np.isclose(crit_val, exp_val, rtol=TOL, atol=TOL)


def check_single(test, strict):
    """Check a single test."""
    params, options, exp_val = test

    crit_val = calc_crit_val(params, options)

    is_success = np.isclose(crit_val, exp_val, rtol=TOL, atol=TOL)

    if strict is True:
        assert is_success, "Failed regression test."

    return is_success


def create_single(idx):
    """Create a single test."""
    np.random.seed(idx)

    params, options = generate_random_model()

    crit_val = calc_crit_val(params, options)

    if not isinstance(crit_val, float):
        raise AssertionError(" ... value of criterion function too large.")

    return params, options, crit_val


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """CLI manager for regression tests."""
    pass


@cli.command()
@click.argument("number_of_tests", type=int)
@click.option("--strict", is_flag=True, help="Immediate termination on failure.")
@click.option("--notification/--no-notification", default=True, help="Send report.")
@click.option("-p", "--processes", default=1, type=int, help="Number of processes.")
def run(number_of_tests, strict, processes, notification):
    """Run a number of regression tests."""
    run_regression_tests(
        n_tests=number_of_tests,
        strict=strict,
        n_processes=processes,
        notification=notification,
    )


@cli.command()
@click.argument("number_of_test", type=int)
def investigate(number_of_test):
    """Investigate a single regression test."""
    investigate_regression_test(number_of_test)


@cli.command()
@click.argument("number_of_tests", type=int)
@click.option("-p", "--processes", default=1, type=int, help="Number of processes.")
@click.option("--save/--no-save", default=True, help="Saves new tests on disk.")
def create(number_of_tests, processes, save):
    """Create a new collection of regression tests."""
    create_regression_tests(n_tests=number_of_tests, n_processes=processes, save=save)


if __name__ == "__main__":
    cli()
