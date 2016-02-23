#!/usr/bin/env python
""" This module contains the functions to plot the results from the model
misspecification exercises.
"""

# standard library
import pickle as pkl

import argparse
import sys
import os

# module-wide variable
ROBUPY_DIR = os.environ['ROBUPY']

# PYTHONPATH
sys.path.insert(0, ROBUPY_DIR + '/development/analyses/robust/_scripts')
sys.path.insert(0, ROBUPY_DIR)

# _scripts
from _auxiliary import float_to_string

# project library
from auxiliary import plot_indifference_curve
from auxiliary import plot_choice_patterns
from auxiliary import get_period_choices

''' Core function
'''


def create():
    """ Create a visual representation of the results from the model
    misspecification exercise.
    """
    # Read results
    rslts = pkl.load(open('rslts/indifference_curve.robupy.pkl', 'rb'))

    # Prepare results for plotting, redo scaling. The graph of the
    # indifference curve thus shows the case for re-enrollment.
    levels = sorted(rslts['opt'].keys())
    intercepts = []
    for level in levels:
        # TODO: This is hard-coded for the second specification at this point.
        intercepts += [-(rslts['opt'][level][0] - 15000)]

    # Plot the results from the model misspecification exercise.
    plot_indifference_curve(intercepts, levels)

    # If all detailed information was downloaded, then we can also have a
    # look at the distribution of choices for these economies.
    # TODO: Cleanup the loop ... complicated due to psychic costs shift.
    for i in range(len(levels)):
        level = levels[i]
        level_fmt = float_to_string(levels[i])
        intercept_fmt = float_to_string(rslts['opt'][level][0])
        if not os.path.exists('rslts/' + level_fmt + '/' + intercept_fmt):
            return

    # Create graphs with choice probabilities over time.
    os.chdir('rslts')

    for level in rslts['opt'].keys():

        # Get the optimal value.
        intercept = rslts['opt'][level][0]

        # Step into optimal subdirectory.
        os.chdir(float_to_string(level))
        os.chdir(float_to_string(intercept))

        # Get the choice probabilities
        choices = get_period_choices()

        # Back to level of rslt directory
        os.chdir('../'), os.chdir('../')

        # Create graphs with choice probabilities over time
        plot_choice_patterns(choices, level)

    os.chdir('../')

''' Execution of module as script.
'''


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Assess implications of model misspecification.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    create()
