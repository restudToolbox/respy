""" Auxiliary functions for development test suite.
"""

# standard library
import numpy as np

import shutil
import glob
import os

# ROBUPY import
from robupy.python.solve_python import _create_state_space
from robupy import read

# module-wide variables
ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = ROOT_DIR.replace('/robupy/tests/codes', '')


''' Auxiliary functions.
'''


def distribute_model_description(robupy_obj, *args):
    """ This function distributes the model description.
    """

    ret = []

    for arg in args:
        ret.append(robupy_obj.get_attr(arg))

    return ret


def write_interpolation_grid(file_name):
    """ Write out an interpolation grid that can be used across
    implementations.
    """
    # Process relevant initialization file
    robupy_obj = read(file_name)

    # Distribute class attributes
    num_periods, num_points, edu_start, is_python, edu_max, min_idx = \
        distribute_model_description(robupy_obj,
            'num_periods', 'num_points', 'edu_start', 'is_python', 'edu_max',
            'min_idx')

    # Determine maximum number of states
    _, states_number_period, _, max_states_period = \
        _create_state_space(num_periods, edu_start, edu_max, min_idx, is_python)

    # Initialize container
    booleans = np.tile(True, (max_states_period, num_periods))

    # Iterate over all periods
    for period in range(num_periods):

        # Construct auxiliary objects
        num_states = states_number_period[period]
        any_interpolation = (num_states - num_points) > 0

        # Check applicability
        if not any_interpolation:
            continue

        # Draw points for interpolation
        indicators = np.random.choice(range(num_states),
                            size=num_states - num_points, replace=False)

        # Replace indicators
        for i in range(num_states):
            if i in indicators:
                booleans[i, period] = False

    # Write out to file
    np.savetxt('interpolation.txt', booleans, fmt='%s')

    # Some information that is useful elsewhere.
    return max_states_period


def write_disturbances(num_periods, max_draws):
    """ Write out disturbances to potentially align the different
    implementations of the model. Note that num draws has to be less or equal
    to the largest number of requested random deviates.
    """
    # Draw standard deviates
    standard_deviates = np.random.multivariate_normal(np.zeros(4),
        np.identity(4), (num_periods, max_draws))

    # Write to file to they can be read in by the different implementations.
    with open('disturbances.txt', 'w') as file_:
        for period in range(num_periods):
            for i in range(max_draws):
                line = ' {0:15.10f} {1:15.10f} {2:15.10f} {3:15.10f}\n'.format(
                    *standard_deviates[period, i, :])
                file_.write(line)


def build_robupy_package(is_hidden):
    """ Compile toolbox
    """
    # Auxiliary objects
    package_dir = ROOT_DIR + '/robupy'
    tests_dir = os.getcwd()

    # Compile package
    os.chdir(package_dir)

    for i in range(1):

        os.system('./waf distclean > /dev/null 2>&1')

        cmd = './waf configure build --fortran --debug '

        if is_hidden:
            cmd += ' > /dev/null 2>&1'

        os.system(cmd)

        # In a small number of cases the build process seems to fail for no
        # reason.
        try:
            import robupy.python.f2py.f2py_library
            break
        except ImportError:
            pass

        if i == 10:
            raise AssertionError

    os.chdir(tests_dir)


def build_testing_library(is_hidden):
    """ Build the F2PY testing interface for testing.f
    """
    tmp_dir = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    try:
        shutil.rmtree('build')
    except FileNotFoundError:
        pass

    os.mkdir('build')

    os.chdir('build')

    # Get all sources from the FORTRAN package.
    files = glob.glob('../../../fortran/*.f*')

    for file_ in files:
        shutil.copy(file_, '.')

    shutil.copy('../robufort_testing.f90', '.')
    shutil.copy('../f2py_interface_testing.f90', '.')

    # Build static library
    compiler_options = '-O3 -fpic'

    files = ['robufort_constants.f90', 'robufort_auxiliary.f90',
             'robufort_slsqp.f', 'robufort_emax.f90', 'robufort_risk.f90',
             'robufort_ambiguity.f90', 'robufort_library.f90',
             'robufort_testing.f90']

    for file_ in files:

        cmd = 'gfortran ' + compiler_options + ' -c ' + file_

        if is_hidden:
            cmd += ' > /dev/null 2>&1'
        os.system(cmd)

    os.system('ar crs libfort_testing.a *.o *.mod')

    # Prepare directory structure
    for dir_ in ['include', 'lib']:
        try:
            shutil.rmtree(dir_)
        except OSError:
                pass
        try:
            os.makedirs(dir_)
        except OSError:
            pass

    # Finalize static library
    module_files = glob.glob('*.mod')
    for file_ in module_files:
        shutil.move(file_, 'include/')
    shutil.move('libfort_testing.a', 'lib/')

    # Build interface
    cmd = 'f2py3 -c -m  f2py_testing f2py_interface_testing.f90 -Iinclude ' \
          ' -Llib -lfort_testing -L/usr/lib/lapack -llapack'

    if is_hidden:
        cmd += ' > /dev/null 2>&1'

    os.system(cmd)

    lib_name = glob.glob('f2py_testing.*.so')[0]
    try:
        os.mkdir('../../lib/')
    except FileExistsError:
        pass

    shutil.copy(lib_name, '../../lib/')
    os.chdir('../')
    shutil.rmtree('build')
    # Finish
    os.chdir(tmp_dir)

