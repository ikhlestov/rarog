#!/bin/bash
export RAROG_TEST_DB_PORT=4242
# start container with test database
DB_CONTAINER_NAME=`docker run -d --name clickhouse_test --ulimit nofile=262144:262144 -p $RAROG_TEST_DB_PORT:9000 yandex/clickhouse-server`

# run tests and capture exit code
if [ $1 ] && [ $1 == "tox" ]
then
    echo "Start tox tests"
    tox && TEST_EXIT_CODE=$?
else
    echo "Start pytest tests"
    pytest --cov=rarog tests/
    TEST_EXIT_CODE=$?
    coverage html
    pycodestyle rarog tests
fi

# stop container with the test database
docker rm -f $DB_CONTAINER_NAME &>/dev/null
exit $TEST_EXIT_CODE
