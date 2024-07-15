#
# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
#
import pytest
from unittest.mock import MagicMock, patch

from source_amocrm_incremental.source import SourceAmocrmIncremental, Leads


@pytest.fixture
def config():
    CONFIG = {
        "credentials": {
            "client_id": "client_id",
            "client_secret": "client_secret"
        }
    }

    return CONFIG


@pytest.fixture
def leads():
    return [
        {
            "id": 19619,
            "name": "Сделка для примера",
            "price": 46333,
            "responsible_user_id": 123321,
            "group_id": 625,
            "status_id": 142,
            "pipeline_id": 1300,
            "loss_reason_id": "null",
            "source_id": "null",
            "created_by": 321123,
            "updated_by": 321123,
            "created_at": 1453279607,
            "updated_at": 1502193501,
            "closed_at": 1483005931,
            "closest_task_at": "null",
            "is_deleted": "false",
            "custom_fields_values": "null",
            "score": "null",
            "account_id": 5135160,
            "_links": {
                "self": {
                    "href": "https://example.amocrm.ru/api/v4/leads/19619"
                }
            },
            "_embedded": {
                "tags": [],
                "companies": []
            }
        },
        {
            "id": 14460,
            "name": "Сделка для примера 2",
            "price": 655,
            "responsible_user_id": 123321,
            "group_id": 625,
            "status_id": 142,
            "pipeline_id": 1300,
            "loss_reason_id": "null",
            "source_id": "null",
            "created_by": 321123,
            "updated_by": 321123,
            "created_at": 1453279607,
            "updated_at": 1502193501,
            "closed_at": 1483005931,
            "closest_task_at": "null",
            "is_deleted": "false",
            "custom_fields_values": "null",
            "score": "null",
            "account_id": 1351360,
            "_links": {
                "self": {
                    "href": "https://example.amocrm.ru/api/v4/leads/14460"
                }
            },
            "_embedded": {
                "tags": [],
                "companies": []
            }
        }
    ]


def test_check_connection(config, leads):
    with patch.object(Leads, "read_records", return_value=iter([leads])):
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
