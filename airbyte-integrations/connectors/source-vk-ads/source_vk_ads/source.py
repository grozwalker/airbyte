#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pendulum
import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream, HttpSubStream
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator

class VkAdsStream(HttpStream, ABC):
    url_base = "https://api.vk.com/method/"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)

        self.config = config

    @property
    def http_method(self) -> str:
        return "POST"

    @property
    def max_retries(self) -> int:
        return 10

    def should_retry(self, response: requests.Response) -> bool:
        error = response.json().get("error")

        if error:
            return error.get("error_code") == 9

        return False

    def backoff_time(self, response: requests.Response) -> Optional[float]:
        return 30

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        return {
            "v": 5.131,
            "account_id": self.config["account_id"]
        }

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        records = response.json().get("response")

        yield from records

class Campaigns(VkAdsStream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ads.getCampaigns"

class Ads(VkAdsStream):
    primary_key = "id"

    @property
    def use_cache(self) -> bool:
        return True

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ads.getAds"

class Statistics(HttpSubStream, VkAdsStream):
    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], authenticator: TokenAuthenticator, **kwargs):
        super().__init__(
            authenticator=authenticator,
            config=config,
            parent=Ads(authenticator=authenticator, config=config, **kwargs),
        )

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ads.getStatistics"

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        ads_stream = Ads(config=self.config, authenticator=self.authenticator)

        ads = []

        for ad in ads_stream.read_records(sync_mode=None):
            ads.append(str(ad["id"]))

        start = 0
        end = len(ads)
        step = 100
        if end < step:
            yield { "ads": ads }
        else:
            for i in range(start, end, step):
                x = i
                yield { "ads": ads[x:x+step] }

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        ads = stream_slice["ads"]

        params = super().request_params(stream_state=stream_state, next_page_token=next_page_token)

        params.update({
            "ids_type": "ad",
            "ids": ",".join(ads),
            "period": "day",
            "date_from": f"{self.config['start_date']}",
            "date_to": f"{pendulum.today().date()}"
        })

        return params

class AdLayouts(VkAdsStream):
    primary_key = "id"

    @property
    def use_cache(self) -> bool:
        return True

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "ads.getAdsLayout"

class Walls(HttpSubStream, VkAdsStream):
    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], authenticator: TokenAuthenticator, **kwargs):
        super().__init__(
            authenticator=authenticator,
            config=config,
            parent=AdLayouts(authenticator=authenticator, config=config, **kwargs),
        )

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "wall.getById"

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        ad_layouts_stream = AdLayouts(authenticator=self.authenticator, config=self.config)

        # Маска, по которой можно отличить, что объявление является постом
        POST_PREFIX = 'http://vk.com/wall'
        wall_ids = []

        for ad in ad_layouts_stream.read_records(sync_mode=None):
            link_url = ad.get('link_url')

            if link_url and link_url.startswith(POST_PREFIX):
                # Находим ID записи на стене
                wall_id = link_url[len(POST_PREFIX):]
                wall_ids.append(wall_id)

        start = 0
        end = len(wall_ids)
        step = 100
        if end < step:
            yield { "wall_ids": wall_ids }
        else:
            for i in range(start, end, step):
                x = i
                yield { "wall_ids": wall_ids[x:x+step] }

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = super().request_params(stream_state=stream_state, next_page_token=next_page_token)

        params.update({
            "posts": ",".join(stream_slice["wall_ids"])
        })

        return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        records = response.json().get("response")

        for row in records:
            res = {
                "id": row.get("id"),
                "owner_id": row.get("owner_id"),
                "text": row.get('text')
            }
            attachments = row.get('attachments')

            link_types = ['link']
            link_attachments = [d for d in attachments if d['type'] in link_types]

            if link_attachments:
                res["url"] = link_attachments[0].get("link").get('url')

            yield res


# Source
class SourceVkAds(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        try:
            # Check connectivity
            auth = TokenAuthenticator(token=config["auth_token"])
            campaigns_stream = Ads(authenticator=auth, config=config)

            next(campaigns_stream.read_records(sync_mode=None))

            return True, None
        except Exception as e:
            return False, e

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        auth = TokenAuthenticator(token=config["auth_token"])
        return [
            Campaigns(authenticator=auth, config=config),
            Ads(authenticator=auth, config=config),
            AdLayouts(authenticator=auth, config=config),
            Walls(authenticator=auth, config=config),
            Statistics(authenticator=auth, config=config)
        ]
