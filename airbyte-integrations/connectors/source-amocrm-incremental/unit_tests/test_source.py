#
# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
#
import pytest
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from source_amocrm_incremental.source import SourceAmocrmIncremental, Leads
from 


@pytest.fixture
def config():
    CONFIG = {
        "credentials": {
            "client_id": "client_id",
            "client_secret": "client_secret"
        }
    }

    return CONFIG


def test_check_connection(config):
    with patch.object(Leads, "read_records", return_value=iter([{"Id": 180519267}, {"Id": 180278106}])):
        source = SourceAmocrmIncremental()
        logger_mock = MagicMock()
        assert source.check_connection(logger_mock, config) == (True, None)


def test_streams(mocker):
    source = SourceAmocrmIncremental()
    config_mock = MagicMock()
    streams = source.streams(config_mock)
    # TODO: replace this with your streams number
    expected_streams_number = 2
    assert len(streams) == expected_streams_number
