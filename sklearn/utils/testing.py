"""Testing utilities."""

# Copyright (c) 2011, 2012
# Authors: Pietro Berkes,
#          Andreas Muller
#          Mathieu Blondel
#          Olivier Grisel
#          Arnaud Joly
# License: BSD 3 clause
import inspect
import pkgutil
import warnings

import scipy as sp
from functools import wraps
try:
    # Python 2
    from urllib2 import urlopen
    from urllib2 import HTTPError
except ImportError:
    # Python 3+
    from urllib.request import urlopen
    from urllib.error import HTTPError

import sklearn
from sklearn.base import BaseEstimator
from .fixes import savemat

# Conveniently import all assertions in one place.
from nose.tools import assert_equal
from nose.tools import assert_not_equal
from nose.tools import assert_true
from nose.tools import assert_false
from nose.tools import assert_raises
from nose.tools import raises
from nose import SkipTest
from nose import with_setup

from numpy.testing import assert_almost_equal
from numpy.testing import assert_array_equal
from numpy.testing import assert_array_almost_equal
from numpy.testing import assert_array_less
import numpy as np

from sklearn.base import (ClassifierMixin, RegressorMixin, TransformerMixin,
                          ClusterMixin)

__all__ = ["assert_equal", "assert_not_equal", "assert_raises", "raises",
           "with_setup", "assert_true", "assert_false", "assert_almost_equal",
           "assert_array_equal", "assert_array_almost_equal",
           "assert_array_less"]


try:
    from nose.tools import assert_in, assert_not_in
except ImportError:
    # Nose < 1.0.0

    def assert_in(x, container):
        assert_true(x in container, msg="%r in %r" % (x, container))

    def assert_not_in(x, container):
        assert_false(x in container, msg="%r in %r" % (x, container))


def _assert_less(a, b, msg=None):
    message = "%r is not lower than %r" % (a, b)
    if msg is not None:
        message += ": " + msg
    assert a < b, message


def _assert_greater(a, b, msg=None):
    message = "%r is not greater than %r" % (a, b)
    if msg is not None:
        message += ": " + msg
    assert a > b, message


# To remove when we support numpy 1.7
def assert_warns(warning_class, func, *args, **kw):
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

        # Trigger a warning.
        result = func(*args, **kw)

        # Verify some things
        if not len(w) > 0:
            raise AssertionError("No warning raised when calling %s"
                                 % func.__name__)

        if not w[0].category is warning_class:
            raise AssertionError("First warning for %s is not a "
                                 "%s( is %s)"
                                 % (func.__name__, warning_class, w[0]))

    return result


# To remove when we support numpy 1.7
def assert_no_warnings(func, *args, **kw):
    # XXX: once we may depend on python >= 2.6, this can be replaced by the
    # warnings module context manager.
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')

        result = func(*args, **kw)
        if len(w) > 0:
            raise AssertionError("Got warnings when calling %s: %s"
                                 % (func.__name__, w))
    return result

try:
    from nose.tools import assert_less
except ImportError:
    assert_less = _assert_less

try:
    from nose.tools import assert_greater
except ImportError:
    assert_greater = _assert_greater


def _assert_allclose(actual, desired, rtol=1e-7, atol=0,
                     err_msg='', verbose=True):
    actual, desired = np.asanyarray(actual), np.asanyarray(desired)
    if np.allclose(actual, desired, rtol=rtol, atol=atol):
        return
    msg = ('Array not equal to tolerance rtol=%g, atol=%g:'
           'actual %s, desired %s') % (rtol, atol, actual, desired)
    raise AssertionError(msg)


if hasattr(np.testing, 'assert_allclose'):
    assert_allclose = np.testing.assert_allclose
else:
    assert_allclose = _assert_allclose


def assert_raise_message(exception, message, function, *args, **kwargs):
    """Helper function to test error messages in exceptions"""

    try:
        function(*args, **kwargs)
        raise AssertionError("Should have raised %r" % exception(message))
    except exception as e:
        error_message = str(e)
        assert_in(message, error_message)


def fake_mldata(columns_dict, dataname, matfile, ordering=None):
    """Create a fake mldata data set.

    Parameters
    ----------
    columns_dict: contains data as
                  columns_dict[column_name] = array of data
    dataname: name of data set
    matfile: file-like object or file name
    ordering: list of column_names, determines the ordering in the data set

    Note: this function transposes all arrays, while fetch_mldata only
    transposes 'data', keep that into account in the tests.
    """
    datasets = dict(columns_dict)

    # transpose all variables
    for name in datasets:
        datasets[name] = datasets[name].T

    if ordering is None:
        ordering = sorted(list(datasets.keys()))
    # NOTE: setting up this array is tricky, because of the way Matlab
    # re-packages 1D arrays
    datasets['mldata_descr_ordering'] = sp.empty((1, len(ordering)),
                                                 dtype='object')
    for i, name in enumerate(ordering):
        datasets['mldata_descr_ordering'][0, i] = name

    savemat(matfile, datasets, oned_as='column')


class mock_mldata_urlopen(object):

    def __init__(self, mock_datasets):
        """Object that mocks the urlopen function to fake requests to mldata.

        `mock_datasets` is a dictionary of {dataset_name: data_dict}, or
        {dataset_name: (data_dict, ordering).
        `data_dict` itself is a dictionary of {column_name: data_array},
        and `ordering` is a list of column_names to determine the ordering
        in the data set (see `fake_mldata` for details).

        When requesting a dataset with a name that is in mock_datasets,
        this object creates a fake dataset in a StringIO object and
        returns it. Otherwise, it raises an HTTPError.
        """
        self.mock_datasets = mock_datasets

    def __call__(self, urlname):
        dataset_name = urlname.split('/')[-1]
        if dataset_name in self.mock_datasets:
            resource_name = '_' + dataset_name
            from io import BytesIO
            matfile = BytesIO()

            dataset = self.mock_datasets[dataset_name]
            ordering = None
            if isinstance(dataset, tuple):
                dataset, ordering = dataset
            fake_mldata(dataset, resource_name, matfile, ordering)

            matfile.seek(0)
            return matfile
        else:
            raise HTTPError(urlname, 404, dataset_name + " is not available",
                            [], None)


def install_mldata_mock(mock_datasets):
    # Lazy import to avoid mutually recursive imports
    from sklearn import datasets
    datasets.mldata.urlopen = mock_mldata_urlopen(mock_datasets)


def uninstall_mldata_mock():
    # Lazy import to avoid mutually recursive imports
    from sklearn import datasets
    datasets.mldata.urlopen = urlopen


# Meta estimators need another estimator to be instantiated.
meta_estimators = ["OneVsOneClassifier",
                   "OutputCodeClassifier", "OneVsRestClassifier", "RFE",
                   "RFECV", "BaseEnsemble"]
# estimators that there is no way to default-construct sensibly
other = ["Pipeline", "FeatureUnion", "GridSearchCV", "RandomizedSearchCV"]


def all_estimators(include_meta_estimators=False, include_other=False,
                   type_filter=None):
    """Get a list of all estimators from sklearn.

    This function crawls the module and gets all classes that inherit
    from BaseEstimator. Classes that are defined in test-modules are not
    included.
    By default meta_estimators such as GridSearchCV are also not included.

    Parameters
    ----------
    include_meta_estimators : boolean, default=False
        Whether to include meta-estimators that can be constructed using
        an estimator as their first argument. These are currently
        BaseEnsemble, OneVsOneClassifier, OutputCodeClassifier,
        OneVsRestClassifier, RFE, RFECV.

    include_others : boolean, default=False
        Wether to include meta-estimators that are somehow special and can
        not be default-constructed sensibly. These are currently
        Pipeline, FeatureUnion and GridSearchCV

    type_filter : string or None, default=None
        Which kind of estimators should be returned. If None, no filter is
        applied and all estimators are returned.  Possible values are
        'classifier', 'regressor', 'cluster' and 'transformer' to get
        estimators only of these specific types.

    Returns
    -------
    estimators : list of tuples
        List of (name, class), where ``name`` is the class name as string
        and ``class`` is the actuall type of the class.
    """
    def is_abstract(c):
        if not(hasattr(c, '__abstractmethods__')):
            return False
        if not len(c.__abstractmethods__):
            return False
        return True

    all_classes = []
    # get parent folder
    path = sklearn.__path__
    for importer, modname, ispkg in pkgutil.walk_packages(
            path=path, prefix='sklearn.', onerror=lambda x: None):
        module = __import__(modname, fromlist="dummy")
        if ".tests." in modname:
            continue
        classes = inspect.getmembers(module, inspect.isclass)
        all_classes.extend(classes)

    all_classes = set(all_classes)

    estimators = [c for c in all_classes
                  if (issubclass(c[1], BaseEstimator)
                      and c[0] != 'BaseEstimator')]
    # get rid of abstract base classes
    estimators = [c for c in estimators if not is_abstract(c[1])]

    if not include_other:
        estimators = [c for c in estimators if not c[0] in other]
    # possibly get rid of meta estimators
    if not include_meta_estimators:
        estimators = [c for c in estimators if not c[0] in meta_estimators]

    if type_filter == 'classifier':
        estimators = [est for est in estimators
                      if issubclass(est[1], ClassifierMixin)]
    elif type_filter == 'regressor':
        estimators = [est for est in estimators
                      if issubclass(est[1], RegressorMixin)]
    elif type_filter == 'transformer':
        estimators = [est for est in estimators
                      if issubclass(est[1], TransformerMixin)]
    elif type_filter == 'cluster':
        estimators = [est for est in estimators
                      if issubclass(est[1], ClusterMixin)]
    elif type_filter is not None:
        raise ValueError("Parmeter type_filter must be 'classifier', "
                         "'regressor', 'transformer', 'cluster' or None, got"
                         " %s." % repr(type_filter))

    # We sort in order to have reproducible test failures
    return sorted(estimators)


def set_random_state(estimator, random_state=0):
    if "random_state" in estimator.get_params().keys():
        estimator.set_params(random_state=random_state)


def if_matplotlib(func):
    """Test decorator that skips test if matplotlib not installed. """

    @wraps(func)
    def run_test(*args, **kwargs):
        try:
            import matplotlib
            matplotlib.use('Agg', warn=False)
            # this fails if no $DISPLAY specified
            matplotlib.pylab.figure()
        except:
            raise SkipTest('Matplotlib not available.')
        else:
            return func(*args, **kwargs)
    return run_test
