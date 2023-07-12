#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import requests
import pendulum
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator

URL_BASE: str = "https://ads.vk.com/api/v2/"


# Basic full refresh stream
class VkAds_2Stream(HttpStream, ABC):
    url_base = URL_BASE
    limit = 100

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        response = response.json()
        offset = response.get("offset", 0)
        total_counts = response.get("count", 0)
        if self.limit + offset < total_counts:
            return {
                "offset": self.limit + offset
            }

        return None

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {
            "limit": self.limit
        }
        if next_page_token:
            params.update(**next_page_token)

        return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        return response.json().get('items')

class AdPlans(VkAds_2Stream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ad_plans.json"

class AdGroups(VkAds_2Stream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ad_groups.json"

class Banners(VkAds_2Stream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "banners.json"

class Statistics(VkAds_2Stream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "statistics/banners/day.json"

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        return {
            # "date_from": f"{self.config['start_date']}",
            "date_from": "2023-07-12",
            "date_to": f"{pendulum.today().date()}"
        }

# Source
class SourceVkAds_2(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        try:
            auth = TokenAuthenticator(token=config['access_token'])

            url = f"{URL_BASE}user.json"
            response = requests.get(
                url,
                headers=auth.get_auth_header(),
                timeout=5
            )

            if response.status_code == 200:
                return True, None
            else:
                return False, "Invalid API credentials"

        except Exception as error:
            return False, error

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        auth = TokenAuthenticator(token=config['access_token'])

        return [
            AdPlans(authenticator=auth),
            AdGroups(authenticator=auth),
            Banners(authenticator=auth),
            Statistics(authenticator=auth),
        ]
