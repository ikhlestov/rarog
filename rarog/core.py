import datetime
from collections import defaultdict
from time import time

import numpy as np
from clickhouse_driver import Client
from clickhouse_driver import errors as click_errors


PYTHON_DATATYPE_TO_CLICKHOUSE = {
    bool: 'UInt8',
    int: 'Int32',
    float: 'Float32',
    str: 'String',
    bytes: 'String',
    datetime.date: 'Date',
    datetime.datetime: 'DateTime',
}


NUMPY_DATATYPE_TO_CLICKHOUSE = {
    np.dtype('bool'): 'UInt8',
    np.dtype('int8'): 'Int8',
    np.dtype('int16'): 'Int16',
    np.dtype('int32'): 'Int32',
    np.dtype('int64'): 'Int64',
    np.dtype('uint8'): 'UInt8',
    np.dtype('uint16'): 'UInt16',
    np.dtype('uint32'): 'UInt32',
    np.dtype('uint64'): 'UInt64',
    np.dtype('float32'): 'Float32',
    np.dtype('float64'): 'Float64',
}


def python_type_to_click(value):
    """Convert python data type to clickhouse"""
    error_msg = "Data type {data_type} is not supported"
    if isinstance(value, np.ndarray):
        if value.ndim > 1:
            raise NotImplementedError(
                "Numpy arrays with dimensions more than one are not supported")
        try:
            return 'Array({inner_type})'.format(
                inner_type=NUMPY_DATATYPE_TO_CLICKHOUSE[value.dtype])
        except KeyError:
            raise NotImplementedError(error_msg.format(data_type=value.dtype))
    if isinstance(value, (list, tuple, set)):
        if len(set([type(i) for i in value])) != 1:
            raise NotImplementedError("Iterable must contain values of the same type.")
        inner_python_type = type(next(iter(value)))
        try:
            return 'Array({inner_type})'.format(
                inner_type=PYTHON_DATATYPE_TO_CLICKHOUSE[inner_python_type])
        except KeyError:
            raise NotImplementedError(error_msg.format(data_type=type(inner_python_type)))
    try:
        return PYTHON_DATATYPE_TO_CLICKHOUSE[type(value)]
    except KeyError:
        raise NotImplementedError(error_msg.format(data_type=type(value)))


def check_value(value):
    """Check that value can be stored in the database"""
    if isinstance(value, np.ndarray):
        if value.ndim > 1:
            raise NotImplementedError(
                "Numpy arrays with dimensions more than one are not supported")
    return value


class RarogException(Exception):
    pass


class Manager(Client):
    """Base logger that allows you to manipulate with experiments"""

    def __init__(self, host='localhost', *args, **kwargs):
        super().__init__(host=host, *args, **kwargs)

    def list_experiments(self):
        """Show available experiments"""
        return [table[0] for table in self.execute('SHOW TABLES')]

    def remove_experiment(self, name):
        """Remove experiment by name

        Args:
            name (str): name of experiment to be deleted

        Raises:
            RarogException: if experiment was not found in database
        """
        try:
            self.execute('DROP TABLE {table_name}'.format(table_name=name))
        except click_errors.ServerException as e:
            if "doesn't exist.." in e.message:
                raise RarogException("Experiment `{name}` doesn't exist already".format(
                    name=name))


class Tracker(Manager):
    """Track metrics from your experiment"""

    def __init__(self, name, sync_step=0, sync_seconds=0, host='localhost', exist_ok=False,
                 *args, **kwargs):
        """Initialize connection and create table for experiment

        Args:
            name (str): name of experiment to be logged
            sync_step (int): step frequency for dumping results into database
            sync_seconds (int): time frequency for dumping results into database
            exist_ok (bool): if exist_ok if `False`(default) raises an exception if an
                experiment with the same name already exists

        Raises:
            RarogException: if experiment already exists
        """
        super().__init__(host=host, *args, **kwargs)
        self.table = name
        if sync_step or sync_seconds:
            self.__trace_method = self.__batch_tracing
            self.__multy_trace_method = self.__batch_tracing_multy
            self.__upload_values = {}
            self.__sync_step = sync_step
            self.__sync_seconds = sync_seconds
            self.__last_steps_sync = 0
            self.__last_time_sync = time()
        else:
            self.__trace_method = self.__non_batch_tracing
            self.__multy_trace_method = self.__non_batch_tracing_multy
        try:
            self.execute(
                '''CREATE TABLE {table_name} (
                    time DateTime DEFAULT now(),
                    step UInt32,
                    phase String
                ) ENGINE = SummingMergeTree()
                PARTITION BY toYYYYMMDD(time)
                ORDER BY (step, phase)
                '''.format(table_name=self.table)
            )
        except click_errors.ServerException as e:
            if 'already exists..' in e.message:
                if not exist_ok:
                    raise RarogException(
                        'Experiment `{name}` already exists'.format(name=self.table))
            else:
                raise e

    def __repr__(self):
        return '{class_name}:{table_name}'.format(
            class_name=self.__class__.__name__, table_name=self.table)

    @property
    def metrics(self):
        """Return existing metrics in the experiment"""
        return [col[0] for col in self.execute('DESCRIBE TABLE {name}'.format(name=self.table))]

    def __non_batch_tracing(self, name, value, step, phase):
        """Log metric by name straightway to the database

        Args:
            name (str): name of the metric
            value (int, float, ..): value of the metric
            step (int): increment
            phase (str): phase of the experiment
        """
        try:
            self.execute(
                'INSERT INTO {table_name} ({column_name}, step, phase) VALUES'.format(
                    table_name=self.table, column_name=name),
                [{name: check_value(value), 'step': step, 'phase': phase}])
        except click_errors.ServerException as e:
            if 'No such column' in e.message:
                self.__add_column(name, value)
                self.trace(name, value, step, phase)
            else:
                raise e

    def __non_batch_tracing_multy(self, names_to_values, step, phase):
        """Log several metrics straightway to the database

        Args:
            names_to_values (dict): metric name to value mapping
            step (int): increment
            phase (str): phase of the experiment
        """
        columns_names = ','.join(list(names_to_values.keys()))
        values = [{'step': step, 'phase': phase, **names_to_values}]
        self.__write_batch_of_metrics(columns_names=columns_names, values=values)

    def __batch_tracing(self, name, value, step, phase):
        """Log metric by name with step or time batching

        Args:
            name (str): name of the metric
            value (int, float, ..): value of the metric
            step (int): increment
            phase (str): phase of the experiment
        """
        self.__batch_tracing_multy({name: value}, step, phase)

    def __batch_tracing_multy(self, names_to_values, step, phase):
        """Log several metrics with step or time batching

        Args:
            names_to_values (dict): metric name to value mapping
            step (int): increment
            phase (str): phase of the experiment

        """
        if (self.__sync_step and (step - self.__last_steps_sync) >= self.__sync_step) or \
                (self.__sync_seconds and (time() - self.__last_time_sync) >= self.__sync_seconds):
            self.sync_accumulated_values()
            self.__last_steps_sync = step
            self.__last_time_sync = time()
        update_dict = {**names_to_values, 'time': int(time())}
        try:
            self.__upload_values[step][phase].update(update_dict)
        except KeyError:
            if step not in self.__upload_values:
                self.__upload_values[step] = {}
            self.__upload_values[step][phase] = update_dict

    def __write_batch_of_metrics(self, columns_names, values):
        """Write batch of values to the database. Create necessary columns if required.

        Args:
            columns_names (str): comma separated names of the columns
            values (list(dict)): list with mapping of inserted values
        """
        try:
            values = [
                {key: check_value(value) for key, value in values_dict.items()} for
                values_dict in values
            ]
            self.execute(
                'INSERT INTO {table_name} ({columns_names}, step, phase) VALUES'.format(
                    table_name=self.table, columns_names=columns_names), values
            )
        except click_errors.ServerException as e:
            if 'No such column' in e.message:
                missed_column_name = e.message.split('No such column ')[-1].split(' in table')[0]
                self.__add_column(missed_column_name, values[0][missed_column_name])
                self.__write_batch_of_metrics(columns_names, values)
            else:
                raise e

    def __add_column(self, name, value):
        """Add required column to the experiment table

        Args:
            name (str): column name
            value (any): value example to be stored in the column
        """
        data_type = python_type_to_click(value)
        self.execute('ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}'.format(
            table_name=self.table, column_name=name, data_type=data_type))

    def trace(self, name, value, step, phase='train'):
        """Log metric by name by batches or straightway

        Args:
            name (str): name of the metric
            value (int, float, ..): value of the metric
            step (int): increment
            phase (str): phase of the experiment
        """
        self.__trace_method(name=name, value=value, step=step, phase=phase)

    def multy_trace(self, names_to_values, step, phase='train'):
        """Log several metrics

        Args:
            names_to_values (dict): metric name to value mapping
            step (int): increment
            phase (str): phase of the experiment
        """
        self.__multy_trace_method(names_to_values=names_to_values, step=step, phase=phase)

    def sync_accumulated_values(self):
        """Sync accumulated values to the db"""
        columns_to_values = defaultdict(list)
        for step, step_data in self.__upload_values.items():
            for phase, phase_data in step_data.items():
                columns_to_values[','.join(phase_data.keys())].append({
                    'step': step, 'phase': phase, **phase_data})
        for columns_names, values in columns_to_values.items():
            self.__write_batch_of_metrics(columns_names=columns_names, values=values)
        self.__upload_values = {}
