#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pendulum
import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.requests_native_auth.oauth import SingleUseRefreshTokenOauth2Authenticator


# Basic full refresh stream
class AmocrmStream(HttpStream, ABC):
    url_base = "https://hexlet.amocrm.ru/api/v4/"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        if response.status_code == 204:
            return {}

        current_page = response.json().get("_page")

        if current_page:
            return {"page": current_page + 1}

        return None

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        params = {"limit": 250}
        if next_page_token:
            params.update(**next_page_token)

        return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        if response.status_code == 204:
            return []

        data = response.json().get("_embedded").get(self.name)

        yield from data


class Leads(AmocrmStream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "leads"

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {"limit": 250, "with": "contacts,loss_reason"}

        if next_page_token:
            params.update(**next_page_token)

        return params


class Pipelines(AmocrmStream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "leads/pipelines"


class Users(AmocrmStream):
    primary_key = "id"

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        params = {"limit": 250, "with": "role,group"}

        if next_page_token:
            params.update(**next_page_token)

        return params

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "users"


class Tasks(AmocrmStream):
    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.start_date_for_replication = config['start_date_for_replication']

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        params = {
            'limit': 250,
            'filter[updated_at]': pendulum.parse(self.start_date_for_replication).format('X') or ''
        }

        if next_page_token:
            params.update(**next_page_token)

        return params

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "tasks"


class Events(AmocrmStream):
    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.start_date_for_replication = config['start_date_for_replication']
        self.events = config.get('events')

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        params = {
            'limit': 250,
            'filter[created_at]': pendulum.parse(self.start_date_for_replication).format('X') or ''
        }

        if self.events:
            events = self.events.replace(" ", "").split(",")
            for idx, event in enumerate(events):
                params[f"filter[type][{idx}]"] = event

        if next_page_token:
            params.update(**next_page_token)

        return params

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "events"


class Contacts(AmocrmStream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "contacts"

# Source
class SourceAmocrm(AbstractSource):
    refresh_endpoint = "https://hexlet.amocrm.ru/oauth2/access_token"

    def check_connection(self, logger, config) -> Tuple[bool, any]:
        try:
            # Check connectivity
            auth = SingleUseRefreshTokenOauth2Authenticator(
                config,
                token_refresh_endpoint=self.refresh_endpoint,
            )
            leads_stream = Leads(authenticator=auth)

            next(leads_stream.read_records(sync_mode=SyncMode.full_refresh))

            return True, None
        except Exception as error:
            return False, error

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        auth = SingleUseRefreshTokenOauth2Authenticator(
            config,
            token_refresh_endpoint=self.refresh_endpoint,
        )
        return [
            Contacts(authenticator=auth),
            Pipelines(authenticator=auth),
            Leads(authenticator=auth),
            Users(authenticator=auth),
            Tasks(authenticator=auth, config=config),
            Events(authenticator=auth, config=config),
        ]
