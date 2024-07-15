# Copyright (c) 2023 Airbyte, Inc., all rights reserved.

import json
# from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional
from unittest import TestCase

# import freezegun
from airbyte_cdk.sources.source import TState
from airbyte_cdk.test.catalog_builder import CatalogBuilder
from airbyte_cdk.test.entrypoint_wrapper import EntrypointOutput, read
from airbyte_cdk.test.mock_http import HttpMocker, HttpRequest, HttpResponse
from airbyte_protocol.models import ConfiguredAirbyteCatalog, SyncMode
from source_amocrm_incremental import SourceAmocrmIncremental
from airbyte_cdk.test.mock_http.response_builder import find_template

_A_CONFIG = {
        "credentials": {
            "auth_type": "oauth2.0",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "access_token": "access_token",
            "refresh_token": "refresh_token",
            "token_expiry_date": "2044-05-22T23:59:00.000000+00:00"
        },
        "start_date_for_replication": "2024-05-22"
    }
RESPONSE = """
        {
    "_links": {
        "self": {
            "href": "https://hexlet.amocrm.ru/api/v4/leads?limit=1&page=1"
        },
        "next": {
            "href": "https://hexlet.amocrm.ru/api/v4/leads?limit=1&page=2"
        }
    },
    "_embedded": {
        "leads": [
            {
                "id": 9228191,
                "name": "Автосделка: rogedkone@protonmail.com: Фронтенд-разработчик",
                "price": 124000,
                "responsible_user_id": 7902115,
                "group_id": 382786,
                "status_id": 143,
                "pipeline_id": 5204152,
                "loss_reason_id": null,
                "created_by": 0,
                "updated_by": 7902115,
                "created_at": 1651320035,
                "updated_at": 1654014416,
                "closed_at": 1652194613,
                "closest_task_at": null,
                "is_deleted": false,
                "custom_fields_values": [
                    {
                        "field_id": 774349,
                        "field_name": "hexlet_lead_id",
                        "field_code": null,
                        "field_type": "numeric",
                        "values": [
                            {
                                "value": "14012"
                            }
                        ]
                    },
                    {
                        "field_id": 838363,
                        "field_name": "lead_type",
                        "field_code": null,
                        "field_type": "text",
                        "values": [
                            {
                                "value": "b2c"
                            }
                        ]
                    },
                    {
                        "field_id": 907431,
                        "field_name": "hexlet_first_lead_id",
                        "field_code": null,
                        "field_type": "numeric",
                        "values": [
                            {
                                "value": "14011"
                            }
                        ]
                    },
                    {
                        "field_id": 913727,
                        "field_name": "utm_data",
                        "field_code": null,
                        "field_type": "text",
                        "values": [
                            {
                                "value": "/"
                            }
                        ]
                    },
                    {
                        "field_id": 921871,
                        "field_name": "stack",
                        "field_code": null,
                        "field_type": "select",
                        "values": [
                            {
                                "value": "frontend",
                                "enum_id": 497443,
                                "enum_code": null
                            }
                        ]
                    },
                    {
                        "field_id": 933841,
                        "field_name": "hexlet_user_id",
                        "field_code": null,
                        "field_type": "numeric",
                        "values": [
                            {
                                "value": "384788"
                            }
                        ]
                    },
                    {
                        "field_id": 936587,
                        "field_name": "source_form",
                        "field_code": null,
                        "field_type": "text",
                        "values": [
                            {
                                "value": "signed_up_program"
                            }
                        ]
                    },
                    {
                        "field_id": 938495,
                        "field_name": "learning_format",
                        "field_code": null,
                        "field_type": "select",
                        "values": [
                            {
                                "value": "group",
                                "enum_id": 517665,
                                "enum_code": null
                            }
                        ]
                    },
                    {
                        "field_id": 316923,
                        "field_name": "utm_referrer",
                        "field_code": "UTM_REFERRER",
                        "field_type": "tracking_data",
                        "values": [
                            {
                                "value": "https://ru.hexlet.io/programs/frontend"
                            }
                        ]
                    },
                    {
                        "field_id": 838417,
                        "field_name": "source_page",
                        "field_code": "SOURCE_PAGE",
                        "field_type": "tracking_data",
                        "values": [
                            {
                                "value": "hexlet"
                            }
                        ]
                    },
                    {
                        "field_id": 838419,
                        "field_name": "source_domain",
                        "field_code": "SOURCE_DOMAIN",
                        "field_type": "tracking_data",
                        "values": [
                            {
                                "value": "hexlet.io"
                            }
                        ]
                    },
                    {
                        "field_id": 921827,
                        "field_name": "payment_source",
                        "field_code": null,
                        "field_type": "select",
                        "values": [
                            {
                                "value": "Cloudpayments",
                                "enum_id": 497367,
                                "enum_code": null
                            }
                        ]
                    }
                ],
                "score": null,
                "account_id": 29978305,
                "labor_cost": null,
                "_links": {
                    "self": {
                        "href": "https://hexlet.amocrm.ru/api/v4/leads/9228191?limit=1&page=1"
                    }
                },
                "_embedded": {
                    "tags": [],
                    "companies": []
                }
            }
        ]
    }
}
"""


# @freezegun.freeze_time(_NOW.isoformat())
class FullRefreshTest(TestCase):

    @HttpMocker()
    def test_read_a_single_page(self, http_mocker: HttpMocker) -> None:
        query_params = {
            "limit": 250,
            "with": "contacts,loss_reason",
            "filter[updated_at][from]": 1716336000,
        }
        http_mocker.get(
            HttpRequest(
                url="https://hexlet.amocrm.ru/api/v4/leads",
                query_params=query_params
            ),
            HttpResponse(body=RESPONSE, status_code=200)
        )

        catalog = _configured_catalog("leads", SyncMode.incremental)

        output = self._read(_A_CONFIG, catalog)

        assert len(output.records) == 1

    def _read(self, config: Mapping[str, Any], configured_catalog: ConfiguredAirbyteCatalog, expecting_exception: bool = False) -> EntrypointOutput:
        return _read(config, configured_catalog=configured_catalog, expecting_exception=expecting_exception)


def _read(
    config: Mapping[str, Any],
    configured_catalog: ConfiguredAirbyteCatalog,
    state: Optional[Dict[str, Any]] = None,
    expecting_exception: bool = False
) -> EntrypointOutput:
    return read(_source(configured_catalog, config, state), config, configured_catalog, state, expecting_exception)


def _configured_catalog(stream_name: str, sync_mode: SyncMode) -> ConfiguredAirbyteCatalog:
    return CatalogBuilder().with_stream(stream_name, sync_mode).build()


def _source(catalog: ConfiguredAirbyteCatalog, config: Dict[str, Any], state: Optional[TState]) -> SourceAmocrmIncremental:
    return SourceAmocrmIncremental()
