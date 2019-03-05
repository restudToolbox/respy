import sys
import os

import statsmodels.api as sm
from scipy.stats import norm
import numpy as np
import pytest
import scipy

from respy.python.shared.shared_auxiliary import get_conditional_probabilities
from respy.python.solve.solve_auxiliary import (
    pyth_calculate_rewards_systematic,
)
from respy.python.record.record_estimation import _spectral_condition_number
from respy.python.shared.shared_auxiliary import replace_missing_values
from respy.python.shared.shared_auxiliary import transform_disturbances
from respy.python.solve.solve_auxiliary import StateSpace
from respy.python.solve.solve_auxiliary import pyth_backward_induction
from respy.python.solve.solve_auxiliary import get_simulated_indicator
from respy.python.solve.solve_auxiliary import get_exogenous_variables
from respy.python.shared.shared_auxiliary import dist_class_attributes
from respy.python.solve.solve_auxiliary import get_endogenous_variable
from respy.python.shared.shared_constants import TEST_RESOURCES_BUILD
from respy.python.evaluate.evaluate_python import pyth_contributions
from respy.python.simulate.simulate_auxiliary import sort_type_info
from respy.python.simulate.simulate_auxiliary import sort_edu_spec
from respy.python.shared.shared_auxiliary import get_num_obs_agent
from respy.python.shared.shared_auxiliary import extract_cholesky
from respy.python.shared.shared_auxiliary import get_optim_paras
from respy.python.estimate.estimate_python import pyth_criterion
from respy.python.simulate.simulate_python import pyth_simulate
from respy.python.solve.solve_auxiliary import get_predictions
from respy.python.solve.solve_risk import construct_emax_risk
from respy.python.shared.shared_auxiliary import create_draws
from respy.python.shared.shared_auxiliary import read_draws
from respy.python.shared.shared_constants import IS_F2PY
from respy.python.interface import get_scales_magnitudes
from respy.pre_processing.data_processing import process_dataset
from respy.python.solve.solve_python import pyth_solve
from respy.fortran.interface import resfort_interface
from respy.tests.codes.auxiliary import write_interpolation_grid
from respy.tests.codes.auxiliary import write_lagged_start
from respy.tests.codes.auxiliary import simulate_observed
from respy.tests.codes.random_init import generate_init
from respy.tests.codes.auxiliary import write_edu_start
from respy.tests.codes.auxiliary import write_draws
from respy.tests.codes.auxiliary import write_types
from functools import partial
from numpy.testing import (
    assert_equal,
    assert_array_equal,
    assert_array_almost_equal,
)
from respy import RespyCls

from respy.python.shared.shared_constants import DECIMALS, TOL

assert_allclose = partial(np.testing.assert_allclose, rtol=TOL, atol=TOL)
assert_almost_equal = partial(np.testing.assert_almost_equal, decimal=DECIMALS)

if IS_F2PY:
    sys.path.insert(0, TEST_RESOURCES_BUILD)
    import f2py_interface as fort_debug


@pytest.mark.skipif(not IS_F2PY, reason="No F2PY available")
class TestClass(object):
    """ This class groups together some tests.
    """

    def test_1(self):
        """ Compare the evaluation of the criterion function for the ambiguity
        optimization and the simulated expected future value between the FORTRAN and
        PYTHON implementations. These tests are set up a separate test case due to the
        large setup cost to construct the ingredients for the interface.
        """
        # Generate constraint periods
        constr = dict()
        constr["version"] = "PYTHON"

        # Generate random initialization file
        generate_init(constr)

        # Perform toolbox actions
        respy_obj = RespyCls("test.respy.ini")

        respy_obj = simulate_observed(respy_obj)

        # Extract class attributes
        (
            state_space,
            states_all,
            mapping_state_idx,
            periods_rewards_systematic,
            periods_emax,
            num_periods,
            num_draws_emax,
            edu_spec,
            optim_paras,
            num_types,
        ) = dist_class_attributes(
            respy_obj,
            "state_space",
            "states_all",
            "mapping_state_idx",
            "periods_rewards_systematic",
            "periods_emax",
            "num_periods",
            "num_draws_emax",
            "edu_spec",
            "optim_paras",
            "num_types",
        )

        # Sample draws
        draws_emax_standard = np.random.multivariate_normal(
            np.zeros(4), np.identity(4), num_draws_emax
        )
        draws_emax_risk = transform_disturbances(
            draws_emax_standard, np.zeros(4), optim_paras["shocks_cholesky"]
        )

        # Sampling of random period and admissible state index
        period = np.random.choice(range(num_periods))
        k = np.random.choice(range(state_space.states_per_period[period]))

        # Select systematic rewards
        rewards_systematic = periods_rewards_systematic[period, k, :]

        # Evaluation of simulated expected future values
        py = construct_emax_risk(
            state_space.states.loc[state_space.states.period.eq(period)],
            draws_emax_risk,
            optim_paras,
        )

        f90 = fort_debug.wrapper_construct_emax_risk(
            num_periods,
            num_draws_emax,
            period,
            k,
            draws_emax_risk,
            rewards_systematic,
            periods_emax,
            states_all,
            mapping_state_idx,
            edu_spec["start"],
            edu_spec["max"],
            optim_paras["delta"],
            optim_paras["coeffs_common"],
            optim_paras["coeffs_a"],
            optim_paras["coeffs_b"],
            num_types,
        )

        assert_allclose(py, f90)

    def test_2(self):
        """ Compare results between FORTRAN and PYTHON of selected hand-crafted
        functions. In test_97() we test FORTRAN implementations against PYTHON intrinsic
        routines.
        """
        for _ in range(33):

            # Create grid of admissible state space values.
            num_edu_start = np.random.choice(range(1, 3))
            num_periods = np.random.randint(1, 15)
            num_types = np.random.randint(1, 3)

            edu_spec = dict()
            edu_spec["start"] = np.random.choice(
                range(1, 10), size=num_edu_start, replace=False
            ).tolist()
            edu_spec["max"] = max(edu_spec["start"]) + np.random.randint(1, 5)
            min_idx = edu_spec["max"] + 1

            # FORTRAN
            base_args = (num_periods, num_types)

            state_space = StateSpace(
                *base_args, edu_spec["start"], edu_spec["max"]
            )

            py_a, py_c, _, _ = state_space._get_fortran_counterparts()
            py_b = state_space.states_per_period
            py_d = py_b.max()

            fort_a, fort_b, fort_c, fort_d = fort_debug.wrapper_create_state_space(
                *base_args, edu_spec["start"], edu_spec["max"], min_idx
            )

            # Ensure equivalence
            rslts = [
                [fort_a, py_a],
                [fort_b, py_b],
                [fort_c, py_c],
                [fort_d, py_d],
            ]
            for obj in rslts:
                assert_allclose(obj[0], obj[1])

        for _ in range(100):

            # Draw random request for testing purposes
            num_covars = np.random.randint(2, 10)
            num_agents = np.random.randint(100, 1000)
            tiny = np.random.normal(size=num_agents)
            beta = np.random.normal(size=num_covars)

            # Generate sample
            exog = np.random.sample((num_agents, num_covars))
            exog[:, 0] = 1
            endog = np.dot(exog, beta) + tiny

            # Run statsmodels
            results = sm.OLS(endog, exog).fit()

            # Check parameters
            py = results.params
            f90 = fort_debug.wrapper_get_coefficients(
                endog, exog, num_covars, num_agents
            )
            assert_almost_equal(py, f90)

            # Check prediction
            py = results.predict(exog)
            f90 = fort_debug.wrapper_point_predictions(exog, f90, num_agents)
            assert_almost_equal(py, f90)

            # Check coefficient of determination and the standard errors.
            py = [results.rsquared, results.bse]
            f90 = fort_debug.wrapper_get_pred_info(
                endog, f90, exog, num_agents, num_covars
            )
            for i in range(2):
                assert_almost_equal(py[i], f90[i])

    def test_3(self):
        """ Compare results between FORTRAN and PYTHON of selected functions.
        """
        for _ in range(10):

            # Draw random requests for testing purposes.
            num_draws_emax = np.random.randint(2, 1000)
            dim = np.random.randint(1, 6)

            matrix = np.random.uniform(size=dim ** 2).reshape(dim, dim)
            cov = np.dot(matrix, matrix.T)

            # PDF of normal distribution
            args = np.random.normal(size=3)
            args[-1] **= 2

            f90 = fort_debug.wrapper_normal_pdf(*args)
            py = norm.pdf(*args)

            assert_almost_equal(py, f90)

            # Singular Value Decomposition
            py = scipy.linalg.svd(matrix)
            f90 = fort_debug.wrapper_svd(matrix, dim)

            for i in range(3):
                assert_allclose(py[i], f90[i])

            # Pseudo-Inverse
            py = np.linalg.pinv(matrix)
            f90 = fort_debug.wrapper_pinv(matrix, dim)

            assert_allclose(py, f90)

            # Inverse
            py = np.linalg.inv(cov)
            f90 = fort_debug.wrapper_inverse(cov, dim)
            assert_allclose(py, f90)

            # Determinant
            py = np.linalg.det(cov)
            f90 = fort_debug.wrapper_determinant(cov)

            assert_allclose(py, f90)

            # Trace
            py = np.trace(cov)
            f90 = fort_debug.wrapper_trace(cov)

            assert_allclose(py, f90)

            # Random normal deviates. This only tests the interface, requires
            # visual inspection in IPYTHON notebook as well.
            fort_debug.wrapper_standard_normal(num_draws_emax)

            # Clipping values below and above bounds.
            num_values = np.random.randint(1, 10000)
            lower_bound = np.random.randn()
            upper_bound = lower_bound + np.random.ranf()
            values = np.random.normal(size=num_values)

            f90 = fort_debug.wrapper_clip_value(
                values, lower_bound, upper_bound, num_values
            )
            py = np.clip(values, lower_bound, upper_bound)

            assert_almost_equal(py, f90)

            # Spectral condition number
            py = _spectral_condition_number(cov)
            fort = fort_debug.wrapper_spectral_condition_number(cov)
            assert_almost_equal(py, fort)

    def test_4(self):
        """ Testing the core functions of the solution step for the equality of results
        between the PYTHON and FORTRAN implementations.
        """

        # Generate random initialization file

        constr = dict()

        generate_init(constr)

        # Perform toolbox actions
        respy_obj = RespyCls("test.respy.ini")

        # Ensure that backward induction routines use the same grid for the
        # interpolation.
        write_interpolation_grid("test.respy.ini")

        # Extract class attributes
        (
            num_periods,
            edu_spec,
            optim_paras,
            num_draws_emax,
            seed_emax,
            is_debug,
            is_interpolated,
            num_points_interp,
            optimizer_options,
            file_sim,
            num_types,
        ) = dist_class_attributes(
            respy_obj,
            "num_periods",
            "edu_spec",
            "optim_paras",
            "num_draws_emax",
            "seed_emax",
            "is_debug",
            "is_interpolated",
            "num_points_interp",
            "optimizer_options",
            "file_sim",
            "num_types",
        )

        shocks_cholesky = optim_paras["shocks_cholesky"]
        coeffs_common = optim_paras["coeffs_common"]
        coeffs_home = optim_paras["coeffs_home"]
        coeffs_edu = optim_paras["coeffs_edu"]
        coeffs_a = optim_paras["coeffs_a"]
        coeffs_b = optim_paras["coeffs_b"]
        delta = optim_paras["delta"]

        type_spec_shifts = optim_paras["type_shifts"]
        type_spec_shares = optim_paras["type_shares"]

        min_idx = edu_spec["max"] + 1

        # Check the state space creation.
        base_args = (num_periods, num_types)
        args = base_args + (edu_spec["start"], edu_spec["max"])

        state_space = StateSpace(*args)

        (
            states_all,
            mapping_state_idx,
            periods_rewards_systematic,
            periods_emax,
        ) = state_space._get_fortran_counterparts()

        pyth = [
            states_all,
            state_space.states_per_period,
            mapping_state_idx,
            state_space.states_per_period.max(),
        ]

        args = base_args + (edu_spec["start"], edu_spec["max"], min_idx)
        f2py = fort_debug.wrapper_create_state_space(*args)
        for i in range(4):
            assert_allclose(pyth[i], f2py[i])

        # Check calculation of systematic components of rewards.
        state_space.states = pyth_calculate_rewards_systematic()
        _, _, pyth, _ = state_space._get_fortran_counterparts()

        args = (
            num_periods,
            state_space.states_per_period,
            states_all,
            state_space.states_per_period.max(),
            coeffs_common,
            coeffs_a,
            coeffs_b,
            coeffs_edu,
            coeffs_home,
            type_spec_shares,
            type_spec_shifts,
        )
        f2py = fort_debug.wrapper_calculate_rewards_systematic(*args)

        assert_allclose(pyth, f2py)

        # Carry some results from the systematic rewards calculation for future use and
        # create the required set of disturbances.
        periods_draws_emax = create_draws(
            num_periods, num_draws_emax, seed_emax, is_debug
        )

        # Check backward induction procedure.
        base_args = (
            num_periods,
            False,
            periods_draws_emax,
            num_draws_emax,
            state_space,
            is_debug,
            is_interpolated,
            num_points_interp,
        )

        args = base_args + (edu_spec, optim_paras, file_sim, False)
        state_space = pyth_backward_induction(*args)
        _, _, _, pyth = state_space._get_fortran_counterparts()

        args = base_args + (
            edu_spec["start"],
            edu_spec["max"],
            shocks_cholesky,
            delta,
            coeffs_common,
            coeffs_a,
            coeffs_b,
            file_sim,
            False,
        )
        f2py = fort_debug.wrapper_backward_induction(*args)

        assert_allclose(pyth, f2py)

    def test_5(self):
        """ This methods ensures that the core functions yield the same results across
        implementations.
        """
        # Generate random initialization file

        constr = dict()
        generate_init(constr)

        # Perform toolbox actions
        respy_obj = RespyCls("test.respy.ini")
        respy_obj = simulate_observed(respy_obj)

        # Ensure that backward induction routines use the same grid for the
        # interpolation.
        max_states_period = write_interpolation_grid("test.respy.ini")

        # Extract class attributes
        (
            num_periods,
            edu_spec,
            optim_paras,
            num_draws_emax,
            is_debug,
            is_interpolated,
            num_points_interp,
            is_myopic,
            num_agents_sim,
            num_draws_prob,
            tau,
            seed_sim,
            num_agents_est,
            optimizer_options,
            file_sim,
            num_types,
            num_paras,
        ) = dist_class_attributes(
            respy_obj,
            "num_periods",
            "edu_spec",
            "optim_paras",
            "num_draws_emax",
            "is_debug",
            "is_interpolated",
            "num_points_interp",
            "is_myopic",
            "num_agents_sim",
            "num_draws_prob",
            "tau",
            "seed_sim",
            "num_agents_est",
            "optimizer_options",
            "file_sim",
            "num_types",
            "num_paras",
        )

        data_array = process_dataset(respy_obj).values
        num_obs_agent = get_num_obs_agent(data_array, num_agents_est)
        min_idx = edu_spec["max"] + 1

        shocks_cholesky = optim_paras["shocks_cholesky"]
        coeffs_common = optim_paras["coeffs_common"]
        coeffs_home = optim_paras["coeffs_home"]
        coeffs_edu = optim_paras["coeffs_edu"]
        coeffs_a = optim_paras["coeffs_a"]
        coeffs_b = optim_paras["coeffs_b"]
        delta = optim_paras["delta"]

        type_spec_shares = optim_paras["type_shares"]
        type_spec_shifts = optim_paras["type_shifts"]

        # Write out random components and interpolation grid to align the three
        # implementations.
        max_draws = max(num_agents_sim, num_draws_emax, num_draws_prob)
        write_types(type_spec_shares, num_agents_sim)
        write_edu_start(edu_spec, num_agents_sim)
        write_draws(num_periods, max_draws)
        write_lagged_start(num_agents_sim)

        periods_draws_emax = read_draws(num_periods, num_draws_emax)
        periods_draws_prob = read_draws(num_periods, num_draws_prob)
        periods_draws_sims = read_draws(num_periods, num_agents_sim)

        # Check the full solution procedure
        base_args = (
            is_interpolated,
            num_points_interp,
            num_draws_emax,
            num_periods,
            is_myopic,
            is_debug,
            periods_draws_emax,
        )

        fort, _ = resfort_interface(respy_obj, "simulate")

        args = base_args + (
            edu_spec,
            optim_paras,
            file_sim,
            optimizer_options,
            num_types,
        )
        state_space = pyth_solve(*args)
        (
            states_all,
            mapping_state_idx,
            periods_rewards_systematic,
            periods_emax,
        ) = state_space._get_fortran_counterparts()

        py = (
            periods_rewards_systematic,
            state_space.states_per_period,
            mapping_state_idx,
            periods_emax,
            states_all,
        )

        args = base_args + (
            min_idx,
            edu_spec["start"],
            edu_spec["max"],
            coeffs_common,
            coeffs_a,
            coeffs_b,
            coeffs_edu,
            coeffs_home,
            shocks_cholesky,
            delta,
            file_sim,
            max_states_period,
            num_types,
            type_spec_shares,
            type_spec_shifts,
        )
        f2py = fort_debug.wrapper_solve(*args)

        assert_allclose(py[0], fort[0])
        assert_allclose(py[1], fort[1])
        assert_allclose(py[2], fort[2])
        assert_allclose(py[3], fort[3])
        assert_allclose(py[4], fort[4])

        assert_allclose(py[0], f2py[0])
        assert_allclose(py[1], f2py[1])
        assert_allclose(py[2], f2py[2])
        assert_allclose(py[3], f2py[3])
        assert_allclose(py[4], f2py[4])

        base_args = (
            num_periods,
            num_agents_sim,
            periods_draws_sims,
            seed_sim,
            file_sim,
        )

        py = pyth_simulate(
            state_space, *base_args, edu_spec, optim_paras, num_types, is_debug
        )

        f2py = fort_debug.wrapper_simulate(
            *base_args,
            edu_spec["start"],
            edu_spec["max"],
            edu_spec["share"],
            edu_spec["lagged"],
            optim_paras["coeffs_common"],
            optim_paras["coeffs_a"],
            optim_paras["coeffs_b"],
            shocks_cholesky,
            delta,
            num_types,
            type_spec_shares,
            type_spec_shifts,
            is_debug
        )
        assert_allclose(py, f2py)

        base_args = (
            py,
            periods_draws_prob,
            tau,
            num_periods,
            num_draws_prob,
            num_agents_est,
            num_obs_agent,
            num_types,
        )

        args = (state_space, py) + base_args + (edu_spec, optim_paras)
        py = pyth_contributions(*args)

        args = (
            (
                periods_rewards_systematic,
                mapping_state_idx,
                periods_emax,
                states_all,
            )
            + base_args
            + (
                edu_spec["start"],
                edu_spec["max"],
                shocks_cholesky,
                delta,
                type_spec_shares,
                type_spec_shifts,
            )
        )
        f2py = fort_debug.wrapper_contributions(*args)

        assert_allclose(py, f2py)

        # Evaluation of criterion function
        x0 = get_optim_paras(optim_paras, num_paras, "all", is_debug)

        base_args_1 = (
            is_interpolated,
            num_draws_emax,
            num_periods,
            num_points_interp,
            is_myopic,
            is_debug,
            data_array,
            num_draws_prob,
            tau,
            periods_draws_emax,
            periods_draws_prob,
        )
        base_args_2 = (num_agents_est, num_obs_agent, num_types)

        args = base_args_1 + (state_space,) + base_args_2 + (edu_spec,)
        py = pyth_criterion(x0, *args)

        args = (
            base_args_1
            + (
                states_all,
                state_space.states_per_period,
                mapping_state_idx,
                max_states_period,
            )
            + base_args_2
            + (edu_spec["start"], edu_spec["max"], edu_spec["share"])
        )
        args += (type_spec_shares, type_spec_shifts, num_paras)
        f2py = fort_debug.wrapper_criterion(x0, *args)

        assert_allclose(py, f2py)

    def test_6(self):
        """ Further tests for the interpolation routines.
        """
        # Generate random initialization file
        constr = dict()
        generate_init(constr)

        # Perform toolbox actions
        respy_obj = RespyCls("test.respy.ini")
        respy_obj = simulate_observed(respy_obj)

        # Extract class attributes
        (
            state_space,
            periods_rewards_systematic,
            mapping_state_idx,
            seed_prob,
            periods_emax,
            num_periods,
            states_all,
            num_points_interp,
            edu_spec,
            num_draws_emax,
            is_debug,
            optim_paras,
            optimizer_options,
            file_sim,
            num_types,
        ) = dist_class_attributes(
            respy_obj,
            "state_space",
            "periods_rewards_systematic",
            "mapping_state_idx",
            "seed_prob",
            "periods_emax",
            "num_periods",
            "states_all",
            "num_points_interp",
            "edu_spec",
            "num_draws_emax",
            "is_debug",
            "optim_paras",
            "optimizer_options",
            "file_sim",
            "num_types",
        )
        shocks_cov = np.matmul(
            optim_paras["shocks_cholesky"], optim_paras["shocks_cholesky"].T
        )

        shocks_cholesky = optim_paras["shocks_cholesky"]
        coeffs_common = optim_paras["coeffs_common"]
        coeffs_a = optim_paras["coeffs_a"]
        coeffs_b = optim_paras["coeffs_b"]
        delta = optim_paras["delta"]

        # Add some additional objects required for the interfaces to the functions.
        period = np.random.choice(range(num_periods))

        periods_draws_emax = create_draws(
            num_periods, num_draws_emax, seed_prob, is_debug
        )

        draws_emax_standard = periods_draws_emax[period, :, :]

        draws_emax_risk = transform_disturbances(
            draws_emax_standard, np.tile(0, 4), shocks_cholesky
        )

        num_states = state_space.states_per_period[period]

        shifts = np.random.randn(4)

        # Slight modification of request which assures that the interpolation code is
        # working.
        num_points_interp = min(num_points_interp, num_states)

        # Get the IS_SIMULATED indicator for the subset of points which are used for the
        # predication model.
        args = (num_points_interp, num_states, period, is_debug)
        is_simulated = get_simulated_indicator(*args)

        # Construct the exogenous variables for all points of the state space.
        args = (period, state_space.states, shifts, edu_spec, optim_paras)
        state_space.states = get_exogenous_variables(*args)

        # Align output between Python and Fortran version.
        num_states_in_period = state_space.states.period.eq(period).sum()
        exogenous = state_space.states.loc[
            state_space.states.period.eq(period),
            ["exogenous_a", "exogenous_b", "exogenous_edu", "exogenous_home"],
        ].values
        exogenous = np.hstack(
            (exogenous, np.sqrt(exogenous), np.ones(num_states_in_period))
        )
        py = (
            exogenous,
            state_space.states.loc[
                state_space.states.period.eq(period), "max_emax"
            ].values,
        )

        args = (
            period,
            num_periods,
            num_states,
            periods_rewards_systematic,
            shifts,
            mapping_state_idx,
            periods_emax,
            states_all,
            edu_spec["start"],
            edu_spec["max"],
            delta,
            coeffs_common,
            coeffs_a,
            coeffs_b,
            num_types,
        )
        f90 = fort_debug.wrapper_get_exogenous_variables(*args)

        assert_equal(py, f90)

        # Distribute validated results for further functions.
        exogenous, maxe = py

        # Construct endogenous variable so that the prediction model can be fitted.
        args = (
            period,
            state_space.states,
            is_simulated,
            num_draws_emax,
            draws_emax_risk,
            edu_spec,
            optim_paras,
        )
        state_space.states = get_endogenous_variable(*args)
        endog_variable = state_space.states.loc[
            state_space.states.period.eq(period), "endog_variable"
        ].values

        args = (
            period,
            num_periods,
            num_states,
            periods_rewards_systematic,
            mapping_state_idx,
            periods_emax,
            states_all,
            is_simulated,
            num_draws_emax,
            maxe,
            draws_emax_risk,
            edu_spec["start"],
            edu_spec["max"],
            shocks_cov,
            delta,
            coeffs_common,
            coeffs_a,
            coeffs_b,
        )
        f90 = fort_debug.wrapper_get_endogenous_variable(*args)
        assert_almost_equal(endog_variable, replace_missing_values(f90))

        args = (period, state_space.states, is_simulated, file_sim, False)
        py = get_predictions(*args)

        args = (
            endog_variable,
            exogenous,
            maxe,
            is_simulated,
            num_points_interp,
            num_states,
            file_sim,
            False,
        )
        f90 = fort_debug.wrapper_get_predictions(*args)

        # This assertion fails if a column is all zeros.
        if not exogenous.any(axis=0).any():
            assert_array_almost_equal(py, f90)

    def test_7(self):
        """ This is a special test for shared functions related to the interpolation setup.
        """
        # Impose constraints
        constr = dict()
        constr["periods"] = np.random.randint(2, 5)

        # Construct a random initialization file
        generate_init(constr)

        # Extract required information
        respy_obj = RespyCls("test.respy.ini")

        # Extract class attributes
        is_debug, num_periods = dist_class_attributes(
            respy_obj, "is_debug", "num_periods"
        )

        # Write out a grid for the interpolation
        max_states_period = write_interpolation_grid("test.respy.ini")

        # Draw random request for testing
        num_states = np.random.randint(1, max_states_period)
        candidates = list(range(num_states))

        period = np.random.randint(1, num_periods)
        num_points_interp = np.random.randint(1, num_states + 1)

        # Check function for random choice and make sure that there are no duplicates.
        args = (candidates, num_states, num_points_interp)
        f90 = fort_debug.wrapper_random_choice(*args)
        assert_equal(len(set(f90)), len(f90))
        assert_equal(len(f90), num_points_interp)

        # Check the standard cases of the function.
        args = (num_points_interp, num_states, period, is_debug, num_periods)
        f90 = fort_debug.wrapper_get_simulated_indicator(*args)

        assert_equal(len(f90), num_states)
        assert_equal(np.all(f90) in [0, 1], True)

        # Test the standardization across PYTHON, F2PY, and FORTRAN implementations.
        # This is possible as we write out an interpolation grid to disk which is used
        # for both functions.
        base_args = (num_points_interp, num_states, period, is_debug)
        args = base_args
        py = get_simulated_indicator(*args)
        args = base_args + (num_periods,)
        f90 = fort_debug.wrapper_get_simulated_indicator(*args)
        assert_array_equal(f90, 1 * py)
        os.unlink(".interpolation.respy.test")

        # Special case where number of interpolation points are same as the number of
        # candidates. In that case the returned indicator should be all TRUE.
        args = (num_states, num_states, period, True, num_periods)
        f90 = fort_debug.wrapper_get_simulated_indicator(*args)
        assert_equal(sum(f90), num_states)

    def test_8(self):
        """ We test the construction of the Cholesky decomposition against each other.
        """
        # Draw a random vector of parameters
        x = np.random.uniform(size=54)

        # Construct the Cholesky decompositions
        py = extract_cholesky(x, info=0)
        fort = fort_debug.wrapper_extract_cholesky(x)

        # Compare the results based on the two methods
        np.testing.assert_equal(fort, py)

    def test_9(self):
        """ Functions related to the scaling procedure.
        """
        for _ in range(1000):
            num_free = np.random.randint(1, 100)
            values = np.random.uniform(-1000.0, 1000.0, size=num_free)
            py = get_scales_magnitudes(values)
            f90 = fort_debug.wrapper_get_scales_magnitude(values, num_free)
            assert_almost_equal(py, f90)

    def test_10(self):
        """ Function that calculates the number of observations by individual.
        """
        for _ in range(2):

            generate_init()

            respy_obj = RespyCls("test.respy.ini")

            simulate_observed(respy_obj)

            num_agents_est = respy_obj.get_attr("num_agents_est")

            data_array = process_dataset(respy_obj).values

            py = get_num_obs_agent(data_array, num_agents_est)
            f90 = fort_debug.wrapper_get_num_obs_agent(
                data_array, num_agents_est
            )

            assert_almost_equal(py, f90)

    def test_11(self):
        """ Function that calculates the conditional type probabilites.
        """
        for _ in range(1000):

            num_types = np.random.randint(1, 10)
            edu_start = np.random.randint(10, 100)
            type_shares = np.random.normal(0, 1, size=num_types * 2)

            args = [type_shares, edu_start]

            py = get_conditional_probabilities(*args)
            fort = fort_debug.wrapper_get_conditional_probabilities(
                *args + [num_types]
            )

            assert_almost_equal(np.sum(py), 1.0)
            assert_almost_equal(py, fort)

    @pytest.mark.skip(
        reason="back_out_systematic_wages does not exist anymore."
    )
    def test_12(self):
        """ Function that backs out the systematic wages from the systematic rewards
        """
        for _ in range(1000):

            rewards_systematic = np.random.normal(0, 1, size=4)
            choice_lagged = np.random.randint(1, 4)
            exp_a = np.random.randint(1, 10)
            exp_b = np.random.randint(1, 10)
            edu = np.random.randint(1, 10)

            coeffs_common = np.random.normal(0, 1, size=2)
            coeffs_a = np.random.normal(0, 1, size=15)
            coeffs_b = np.random.normal(0, 1, size=15)

            optim_paras = dict()
            optim_paras["coeffs_common"] = coeffs_common
            optim_paras["coeffs_a"] = coeffs_a
            optim_paras["coeffs_b"] = coeffs_b

            args = [rewards_systematic, exp_a, exp_b, edu, choice_lagged]

            # py = back_out_systematic_wages(*args + [optim_paras])
            fort = fort_debug.wrapper_back_out_systematic_wages(
                *args + [coeffs_a, coeffs_b]
            )

            assert_almost_equal(py, fort)

    def test_13(self):
        """ Testing the functionality introduced to ensure that the simulation is independent of
        the order of initial conditions and types in the initialization file.
        """

        num_elements = np.random.random_integers(1, 10)

        input_array = np.random.normal(size=num_elements)

        # We first check the sorting implementation.
        py = sorted(input_array)
        f90 = fort_debug.wrapper_sorted(input_array, num_elements)
        assert_equal(py, f90)

        # We now turn to the more complicated testing of hand-crafted functions for this purpose.
        generate_init()
        respy_obj = RespyCls("test.respy.ini")

        edu_spec, optim_paras, num_types = dist_class_attributes(
            respy_obj, "edu_spec", "optim_paras", "num_types"
        )

        args = (edu_spec["start"], edu_spec["share"], edu_spec["max"])
        f90 = fort_debug.wrapper_sort_edu_spec(*args)
        py = sort_edu_spec(edu_spec)
        for i, label in enumerate(["start", "share", "max"]):
            assert_equal(py[label], f90[i])

        py = sort_type_info(optim_paras, num_types)
        f90 = fort_debug.wrapper_sort_type_info(
            optim_paras["type_shares"], num_types
        )
        for i, label in enumerate(["order", "shares"]):
            assert_equal(py[label], f90[i])
