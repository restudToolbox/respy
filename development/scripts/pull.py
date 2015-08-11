#!/usr/bin/env python
""" Pull all from remote repositories.
"""

# standard library
import argparse
import os

# module-wide variables
REPOS = ['documentation/sources', 'package']

REPOS += ['documentation/robustToolbox.github.io']


''' Functions
'''
def update():
    """ Update all remote repositories.
    """
    for repo in REPOS:

        # Check if checked out
        try:

            print('\n.. updating ' + repo)

            os.chdir(repo)

            os.system('git pull')

            os.chdir('../')

        except Exception:

            pass

    print('')

''' Execution of module as script
'''
if __name__ == '__main__':

    parser  = argparse.ArgumentParser(description = \
        'Update all remote repositories.',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter)

    args = parser.parse_args()

    update()
