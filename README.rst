===================================================
Monitoring utility for machine learning experiments
===================================================

.. image:: https://travis-ci.com/ikhlestov/rarog.svg?branch=master
   :target: https://travis-ci.com/ikhlestov/rarog/
   :alt: Travis status for master branch

.. image:: https://codecov.io/gh/ikhlestov/rarog/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/ikhlestov/rarog/
   :alt: codecov.io status for master branch

.. image:: https://img.shields.io/pypi/pyversions/rarog.svg
    :target: https://pypi.org/project/rarog


Rarog is a monitoring utility for machine learning experiments. You may use it as a
light-weight alternative for `TensorBoard <https://github.com/tensorflow/tensorboard>`_
or `Visdom <https://github.com/facebookresearch/visdom>`_. Rarog stores all records in
`ClickHouse`_ database using 
`ClickHouse Python Driver <https://github.com/mymarilyn/clickhouse-driver>`__.

Features
========

- log common python data types(bool, int, float, string, iterables)
- log 1d numpy arrays
- distributed experiments monitoring

Setup
=====

Install via `pip`_:

.. code-block:: bash

    pip install rarog

Start `ClickHouse`_ database if required:

.. code-block:: bash

    docker run -d --name clickhouse --ulimit nofile=262144:262144 -p 9000:9000 yandex/clickhouse-server

**Important note:** the example above is just the easiest way. For production, you should
setup database backups or replicated.

Rarog supports Python 3.4 and newer.

Usage
===============

.. code:: python3

    import random
    
    from rarog import Tracker
    
    tracker = Tracker(name='experiment_name')
    
    # trace values one by one
    for step in range(10):
        tracker.trace(
            name='int_value',
            value=random.randint(10, 20),
            step=step)
        tracker.trace(
            name='float_value',
            value=random.random(),
            step=step)
        # provide experiment phase as a string
        tracker.trace(
            name='list_value',
            value=[random.random(), random.random()],
            step=step,
            phase='val')
        
    # trace values by dict
    for step in range(10, 20):
        tracker.multy_trace({
            'int_value': random.randint(10, 20),
            'float_value': random.random()
        }, step=step)
    
    # get names of traced metrics
    tracker.metrics
    # Out: ['time', 'step', 'phase', 'int_value', 'float_value', 'list_value']


If you are going to record more than 100 entries per second,
it's better to use ``sync_step`` or ``sync_seconds`` arguments.
Thus writing to the database will be done with some period, which is much faster.

.. code:: python3

    # `exist_ok` flag allow to use the same name for experiment
    step_tracker = Tracker(name='experiment_name', sync_step=1000, exist_ok=True)
    
    for step in range(20, 10**4):
        step_tracker.trace(name='bool_value', value=bool(random.randint(0, 1)), step=step)
        step_tracker.multy_trace({
            'int_value': random.randint(10, 20),
            'float_value': random.random()
        }, step=step)
    
    # tracker should be manually synchronized after last entry
    step_tracker.sync_accumulated_values()

Experiments can be handled via manager

.. code:: python3

    from rarog import Manager
    
    manager = Manager()
    manager.list_experiments()
    # Out: ['experiment_name']
    
    manager.remove_experiment('experiment_name')



Retrieving your data
====================

TODO (manually and with visualization)


.. _ClickHouse: https://clickhouse.yandex
.. _pip: https://pip.pypa.io/en/stable/quickstart/
