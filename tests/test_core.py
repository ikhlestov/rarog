import datetime
from functools import partial

import numpy as np
import pytest

from rarog import RarogException, Manager, Tracker
from rarog.core import NUMPY_DATATYPE_TO_CLICKHOUSE, python_type_to_click, check_value


# Functions tests
def test_python_type_to_click_numpy_raises_wrong_shape():
    with pytest.raises(NotImplementedError):
        python_type_to_click(np.arange(10).reshape(2, 5))


def test_python_type_to_click_numpy_raises_not_supported_dtype():
    with pytest.raises(NotImplementedError):
        python_type_to_click(np.array(['some', 'strings']))


def test_python_type_to_click_iterables_raises_in_case_of_different_datatypes():
    with pytest.raises(NotImplementedError):
        python_type_to_click([10, 2.2, 'any'])


def test_python_type_to_click_raises_iterable_wrong_inner_datatype():
    with pytest.raises(NotImplementedError):
        python_type_to_click([complex(10, 1)])


def test_python_type_to_click_raises_wrong_datatype():
    with pytest.raises(NotImplementedError):
        python_type_to_click(complex(10, 1))


def test_check_value_incorrect_numpy_shape():
    with pytest.raises(NotImplementedError):
        check_value(np.arange(10).reshape(2, 5))


# Manager tests
@pytest.fixture
def manager(db_port):
    return Manager(host='localhost', port=db_port)


def test_manager_list_experiments(client, manager):
    # check that we have no previous experiments
    assert not manager.list_experiments()
    experiments = ['first', 'second']
    for experiment_name in experiments:
        client.execute(
            '''
            CREATE TABLE {table_name} (
                step UInt32
            ) ENGINE = Memory()
            '''.format(table_name=experiment_name)
        )
    # check that experiments now available
    assert sorted(manager.list_experiments()) == sorted(experiments)
    for experiment_name in experiments:
        client.execute('DROP TABLE {table_name}'.format(table_name=experiment_name))
    assert not manager.list_experiments()


def test_manager_remove_experiment_ok(client, manager):
    client.execute(
        '''
        CREATE TABLE test_manager_remove_experiment_ok (
            step UInt32
        ) ENGINE = Memory()
        '''
    )
    manager.remove_experiment('test_manager_remove_experiment_ok')
    assert not client.execute('SHOW TABLES')


def test_manager_remove_experiment_failed(client, manager):
    with pytest.raises(RarogException):
        manager.remove_experiment("test_manager_remove_experiment_failed")


# Tracker tests
@pytest.fixture
def partial_tracker(db_port):
    """Partially initialized tracker"""
    return partial(Tracker, host='localhost', port=db_port)


def test_tracker__init__ok(client, partial_tracker):
    partial_tracker('test_logger__init__ok')
    assert 'test_logger__init__ok' in client.execute('SHOW TABLES')[0]
    client.execute('DROP TABLE test_logger__init__ok')


def test_tracker__init__raises_exception(client, partial_tracker):
    client.execute('CREATE TABLE test_logger__init__failed (step UInt32) ENGINE = Memory()')
    with pytest.raises(RarogException):
        partial_tracker(name='test_logger__init__failed')
    client.execute('DROP TABLE test_logger__init__failed')


def test_tracker__init__not_raises_exception(client, partial_tracker):
    """Tracker shohuld be avaiable to continue experiment"""
    partial_tracker(name='test_tracker__init__not_raises_exception')
    partial_tracker(name='test_tracker__init__not_raises_exception', exist_ok=True)
    client.execute('DROP TABLE test_tracker__init__not_raises_exception')


def test_tracker__repr__(client, partial_tracker):
    tracker = partial_tracker('test_tracker__repr__')
    assert str(tracker) == 'Tracker:test_tracker__repr__'
    client.execute('DROP TABLE test_tracker__repr__')


def test_tracker_metrics_propery(client, partial_tracker):
    tracker = partial_tracker('test_tracker_metrics_propery')
    assert sorted(tracker.metrics) == ['phase', 'step', 'time']
    client.execute('DROP TABLE test_tracker_metrics_propery')


@pytest.mark.parametrize('value', [True, 10, 3.14, 'string', b'bytes', datetime.date.today(),
                                   datetime.datetime.now()])
def test_tracker__non_batch_tracing(value, client, partial_tracker):
    tracker_suffix = str(type(value)).replace("<class '", "").replace("'>", "").replace(".", "")
    tracker_name = 'test_tracker__non_batch_tracing' + tracker_suffix
    tracker = partial_tracker(tracker_name)
    assert client.execute(
        'SELECT count(*) from {table_name}'.format(table_name=tracker_name))[0][0] == 0
    tracker._Tracker__non_batch_tracing('any_metric', value, step=1, phase='train')
    assert client.execute(
        'SELECT count(*) from {table_name}'.format(table_name=tracker_name))[0][0] == 1
    client.execute('DROP TABLE {table_name}'.format(table_name=tracker_name))


def test_tracker__non_batch_tracing_multy(client, partial_tracker):
    tracker = partial_tracker('test_tracker__non_batch_tracing_multy')
    assert client.execute('SELECT count(*) from test_tracker__non_batch_tracing_multy')[0][0] == 0
    tracker._Tracker__non_batch_tracing_multy({'first': 1, 'second': 2}, step=1, phase='val')
    assert client.execute('SELECT count(*) from test_tracker__non_batch_tracing_multy')[0][0] == 1
    client.execute('DROP TABLE test_tracker__non_batch_tracing_multy')


def test_tracker__batch_tracing(client, partial_tracker):
    tracker = partial_tracker('test_tracker__batch_tracing', sync_step=2)
    assert client.execute('SELECT count(*) from test_tracker__batch_tracing')[0][0] == 0
    tracker._Tracker__batch_tracing('first', 1, step=0, phase='train')
    tracker._Tracker__batch_tracing('second', 2, step=1, phase='train')
    tracker._Tracker__batch_tracing('first', 1, step=0, phase='val')
    tracker._Tracker__batch_tracing('second', 2, step=1, phase='val')
    assert client.execute('SELECT count(*) from test_tracker__batch_tracing')[0][0] == 0
    tracker._Tracker__batch_tracing('first', 1, step=3, phase='train')
    assert client.execute('SELECT count(*) from test_tracker__batch_tracing')[0][0] == 4
    client.execute('DROP TABLE test_tracker__batch_tracing')


def test_tracker__batch_tracing_multy(client, partial_tracker):
    tracker = partial_tracker('test_tracker__batch_tracing', sync_step=2)
    assert client.execute('SELECT count(*) from test_tracker__batch_tracing')[0][0] == 0
    tracker._Tracker__batch_tracing_multy({'first': 1, 'second': 2}, step=0, phase='train')
    tracker._Tracker__batch_tracing_multy({'first': 1, 'second': 2}, step=1, phase='val')
    assert client.execute('SELECT count(*) from test_tracker__batch_tracing')[0][0] == 0
    tracker._Tracker__batch_tracing_multy({'first': 1, 'second': 2}, step=2, phase='val')
    assert client.execute('SELECT count(*) from test_tracker__batch_tracing')[0][0] == 2
    client.execute('DROP TABLE test_tracker__batch_tracing')


def test_tracker__write_batch_of_metrics(client, partial_tracker):
    tracker = partial_tracker('test_tracker__write_batch_of_metrics')
    assert client.execute('SELECT count(*) from test_tracker__write_batch_of_metrics')[0][0] == 0
    tracker._Tracker__write_batch_of_metrics(
        'first,step,phase', [
            {'first': 1, 'step': 42, 'phase': 'val'},
            {'first': 1, 'step': 42, 'phase': 'train'}]
    )
    assert client.execute('SELECT count(*) from test_tracker__write_batch_of_metrics')[0][0] == 2
    client.execute('DROP TABLE test_tracker__write_batch_of_metrics')


@pytest.mark.parametrize('np_dtype', NUMPY_DATATYPE_TO_CLICKHOUSE.keys())
def test__add_column_numpy(np_dtype, client, partial_tracker):
    tracker_suffix = str(np_dtype).replace("<class '", "").replace("'>", "").replace(".", "")
    tracker_name = 'test__add_column_numpy' + tracker_suffix
    tracker = partial_tracker(tracker_name)
    tracker._Tracker__add_column('any_metric_name', np.array([10, 20, 30]).astype(np_dtype))
    client.execute('DROP TABLE {table_name}'.format(table_name=tracker_name))


@pytest.mark.parametrize('iterable', [list, tuple, set])
def test__add_column_iterables(iterable, client, partial_tracker):
    tracker_suffix = str(iterable).replace("<class '", "").replace("'>", "")
    tracker_name = 'test__add_column_iterables' + tracker_suffix
    tracker = partial_tracker(tracker_name)
    tracker._Tracker__add_column('any_metric_name', iterable([10, 20, 30]))
    client.execute('DROP TABLE {table_name}'.format(table_name=tracker_name))


@pytest.mark.parametrize('value', [True, 10, 3.14, 'string', b'bytes', datetime.date.today(),
                                   datetime.datetime.now()])
def test__add_column_various_values(value, client, partial_tracker):
    tracker_suffix = str(type(value)).replace("<class '", "").replace("'>", "").replace(".", "")
    tracker_name = 'test__add_column_various_values' + tracker_suffix
    tracker = partial_tracker(tracker_name)
    tracker._Tracker__add_column('metrics', value)
    client.execute('DROP TABLE {table_name}'.format(table_name=tracker_name))


def test_tracker_trace(client, partial_tracker):
    tracker = partial_tracker('test_tracker_trace')
    assert client.execute('SELECT count(*) from test_tracker_trace')[0][0] == 0
    tracker.trace('metric_name', 42, step=1)
    assert client.execute('SELECT count(*) from test_tracker_trace')[0][0] == 1
    client.execute('DROP TABLE test_tracker_trace')


def test_tracker_multy_trace(client, partial_tracker):
    tracker = partial_tracker('test_tracker_multy_trace')
    assert client.execute('SELECT count(*) from test_tracker_multy_trace')[0][0] == 0
    tracker.multy_trace({'first': 1, 'second': 2}, step=1)
    assert client.execute('SELECT count(*) from test_tracker_multy_trace')[0][0] == 1
    client.execute('DROP TABLE test_tracker_multy_trace')


def test_tracker_sync_accumulated_values(client, partial_tracker, db_port):
    tracker = partial_tracker('test_tracker_sync_accumulated_values', sync_step=1)
    tracker._Tracker__upload_values = {
        1: {
            'train': {'value': 42}
        },
        2: {
            'train': {'value': 43}
        }
    }
    tracker.sync_accumulated_values()
    client.execute('DROP TABLE test_tracker_sync_accumulated_values')
