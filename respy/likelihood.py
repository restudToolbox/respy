from functools import partial

import numpy as np
from numba import guvectorize
from numba import vectorize

from respy.conditional_draws import create_draws_and_prob_wages
from respy.config import HUGE_FLOAT
from respy.pre_processing.data_checking import check_estimation_data
from respy.pre_processing.model_processing import process_options
from respy.pre_processing.model_processing import process_params
from respy.shared import _aggregate_keane_wolpin_utility
from respy.shared import create_base_draws
from respy.shared import get_conditional_probabilities
from respy.solve import solve_with_backward_induction
from respy.state_space import StateSpace


def get_crit_func(params, options, df):
    """Get the criterion function.

    The return value is the :func:`log_like` where all arguments except the
    parameter vector are fixed with ``functools.partial``. Thus, the function can be
    passed directly into any optimization algorithm.

    Parameters
    ----------
    params : pd.DataFrame
        DataFrame containing model parameters.
    options : dict
        Dictionary containing model options.
    df : pd.DataFrame
        The model is fit to this dataset.

    Returns
    -------
    criterion_function : func
        Criterion function where all arguments except the parameter vector are set.

    Raises
    ------
    AssertionError
        If data has not the expected format.

    """
    params, optim_paras = process_params(params)
    options = process_options(options)

    check_estimation_data(options, df)

    df = _process_estimation_data(df, options)

    state_space = StateSpace(params, options)

    # Collect arguments for estimation.
    base_draws_est = create_base_draws(
        (options["num_periods"], options["estimation_draws"], len(options["sectors"])),
        options["estimation_seed"],
    )

    criterion_function = partial(
        log_like,
        data=df,
        base_draws_est=base_draws_est,
        state_space=state_space,
        options=options,
    )
    return criterion_function


def log_like(params, data, base_draws_est, state_space, options):
    """Criterion function for the likelihood maximization.

    This function calculates the average likelihood contribution of the sample.

    Parameters
    ----------
    params : Series
        Parameter Series
    data : pd.DataFrame
        The log likelihood is calculated for this data.
    base_draws_est : np.ndarray
        Set of draws to calculate the probability of observed wages.
    state_space : class
        State space.
    options : dict
        Contains model options.

    """
    params, optim_paras = process_params(params)

    state_space.update_systematic_rewards(optim_paras, options)

    state_space = solve_with_backward_induction(state_space, optim_paras, options)

    contribs = log_like_obs(
        state_space, data, base_draws_est, options["estimation_tau"], optim_paras
    )

    crit_val = -np.mean(contribs)

    return crit_val


@vectorize("f8(f8, f8, f8)", nopython=True, target="cpu")
def clip(x, minimum=None, maximum=None):
    """Clip (limit) input value.

    Parameters
    ----------
    x : float
        Value to be clipped.
    minimum : float
        Lower limit.
    maximum : float
        Upper limit.

    Returns
    -------
    float
        Clipped value.

    """
    if minimum is not None and x < minimum:
        return minimum
    elif maximum is not None and x > maximum:
        return maximum
    else:
        return x


@guvectorize(
    ["f8[:], f8[:], f8[:], f8[:, :], f8, b1[:], i8, f8, f8[:]"],
    "(n_choices), (n_choices), (n_choices), (n_draws, n_choices), (), (n_choices), (), "
    "() -> ()",
    nopython=True,
    target="parallel",
)
def simulate_probability_of_individuals_observed_choice(
    wages,
    nonpec,
    continuation_values,
    draws,
    delta,
    is_inadmissible,
    choice,
    tau,
    prob_choice,
):
    """Simulate the probability of observing the agent's choice.

    The probability is simulated by iterating over a distribution of unobservables.
    First, the utility of each choice is computed. Then, the probability of observing
    the choice of the agent given the maximum utility from all choices is computed.

    Parameters
    ----------
    wages : np.ndarray
        Array with shape (n_choices,).
    nonpec : np.ndarray
        Array with shape (n_choices,).
    continuation_values : np.ndarray
        Array with shape (n_choices,)
    draws : np.ndarray
        Array with shape (n_draws, n_choices)
    delta : float
        Discount rate.
    is_inadmissible: np.ndarray
        Array with shape (n_choices,) containing an indicator for each choice whether
        the following state is inadmissible.
    choice : int
        Choice of the agent.
    tau : float
        Smoothing parameter for choice probabilities.

    Returns
    -------
    prob_choice : float
        Smoothed probability of choice.

    """
    n_draws, n_choices = draws.shape

    value_functions = np.zeros((n_choices, n_draws))

    prob_choice[0] = 0.0

    for i in range(n_draws):

        max_value_functions = 0.0

        for j in range(n_choices):
            value_function, _ = _aggregate_keane_wolpin_utility(
                wages[j],
                nonpec[j],
                continuation_values[j],
                draws[i, j],
                delta,
                is_inadmissible[j],
            )

            value_functions[j, i] = value_function

            if value_function > max_value_functions:
                max_value_functions = value_function

        sum_smooth_values = 0.0

        for j in range(n_choices):
            val_exp = np.exp((value_functions[j, i] - max_value_functions) / tau)

            val_clipped = clip(val_exp, 0.0, HUGE_FLOAT)

            value_functions[j, i] = val_clipped
            sum_smooth_values += val_clipped

        prob_choice[0] += value_functions[choice, i] / sum_smooth_values

    prob_choice[0] /= n_draws


def log_like_obs(state_space, df, base_draws_est, tau, optim_paras):
    """Calculate the likelihood contribution of each individual in the sample.

    The function calculates all likelihood contributions for all observations in the
    data which means all individual-period-type combinations. Then, likelihoods are
    accumulated within each individual and type over all periods. After that, the result
    is multiplied with the type-specific shares which yields the contribution to the
    likelihood for each individual.

    Parameters
    ----------
    state_space : class
        Class of state space.
    df : pd.DataFrame
        DataFrame with the empirical dataset.
    base_draws_est : np.ndarray
        Array with shape (n_periods, n_draws, n_choices) containing i.i.d. draws from
        standard normal distributions.
    tau : float
        Smoothing parameter for choice probabilities.
    optim_paras : dict
        Dictionary with quantities that were extracted from the parameter vector.

    Returns
    -------
    contribs : np.ndarray
        Array with shape (n_individuals,) containing contributions of individuals in the
        empirical data.

    """
    # Convert data to NumPy arrays.
    periods = df.Period.to_numpy()
    lagged_choices = df.Lagged_Choice.to_numpy()
    choices = df.Choice.to_numpy()
    exps = tuple(df[col].to_numpy() for col in df.filter(like="Experience_").columns)
    wages_observed = df["Wage"].to_numpy()

    # Get the number of observations for each individual and an array with indices of
    # each individual's first observation. After that, extract initial education levels
    # per agent which are important for type-specific probabilities.
    num_obs_per_agent = np.bincount(df.Identifier.to_numpy())
    idx_individuals_first_observation = np.hstack(
        (0, np.cumsum(num_obs_per_agent)[:-1])
    )
    individuals_initial_education_levels = exps[2][idx_individuals_first_observation]

    # Update type-specific probabilities conditional on whether the initial level of
    # education is greater than nine.
    type_shares = get_conditional_probabilities(
        optim_paras["type_shares"], individuals_initial_education_levels
    )

    # Get indices of states in the state space corresponding to all observations for all
    # types. The indexer has the shape (n_obs, n_types).
    ks = state_space.indexer[(periods,) + exps + (lagged_choices,)]
    n_obs, n_types = ks.shape

    wages_observed = wages_observed.repeat(n_types)
    log_wages_observed = np.clip(np.log(wages_observed), -HUGE_FLOAT, HUGE_FLOAT)
    wages_systematic = state_space.wages[ks].reshape(n_obs * n_types, -1)
    num_choices = wages_systematic.shape[1]
    choices = choices.repeat(n_types)
    periods = state_space.states[ks, 0].flatten()

    draws, prob_wages = create_draws_and_prob_wages(
        log_wages_observed,
        wages_systematic,
        base_draws_est,
        choices,
        optim_paras["shocks_cholesky"],
        optim_paras["meas_error"],
        periods,
    )

    draws = draws.reshape(n_obs, n_types, -1, num_choices)

    prob_choices = simulate_probability_of_individuals_observed_choice(
        state_space.wages[ks],
        state_space.nonpec[ks],
        state_space.continuation_values[ks],
        draws,
        optim_paras["delta"],
        state_space.is_inadmissible[ks],
        choices.reshape(-1, n_types),
        tau,
    )

    prob_obs = prob_choices * prob_wages.reshape(n_obs, -1)

    # Accumulate the likelihood of observations for each individual-type combination
    # over all periods.
    prob_type = np.multiply.reduceat(prob_obs, idx_individuals_first_observation)

    # Multiply each individual-type contribution with its type-specific shares and sum
    # over types to get the likelihood contribution for each individual.
    contribs = (prob_type * type_shares).sum(axis=1)

    contribs = np.clip(np.log(contribs), -HUGE_FLOAT, HUGE_FLOAT)

    return contribs


def _process_estimation_data(df, options):
    df = df.sort_values(["Identifier", "Period"])

    # Recode choices to model codes. It is not possible to use ``.cat.codes`` because
    # the codes might be in a different order than for the model required which is
    # choices_w_exp_w_wag, choices_w_exp_wo_wage, choices_wo_exp_wo_wage.
    choices_to_codes = {sec: i for i, sec in enumerate(options["choices"])}
    df.Choice = df.Choice.cat.rename_categories(choices_to_codes).astype(int)
    df.Lagged_Choice = df.Lagged_Choice.cat.rename_categories(choices_to_codes).astype(
        int
    )

    return df
