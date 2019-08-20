import os

import pytest
from clickhouse_driver import Client


@pytest.fixture(scope="session")
def db_port():
    try:
        return int(os.getenv("RAROG_TEST_DB_PORT"))
    except TypeError:
        raise Exception("You should provide test database port")


@pytest.fixture()
def client(db_port):
    return Client(host="localhost", port=db_port)
