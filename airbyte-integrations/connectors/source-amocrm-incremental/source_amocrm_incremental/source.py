#
# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pendulum
import datetime
import requests
import logging
from airbyte_cdk.models import SyncMode, ConfiguredAirbyteCatalog, AirbyteMessage, AirbyteStateMessage, Type
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream, IncrementalMixin
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.requests_native_auth.oauth import SingleUseRefreshTokenOauth2Authenticator


# Basic full refresh stream
class AmocrmIncrementalStream(HttpStream, ABC):
    url_base = "https://hexlet.amocrm.ru/api/v4/"

    def check_availability(self, logger: logging.Logger, source: Optional["Source"] = None) -> Tuple[bool, Optional[str]]:
        return True, None

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        if response.status_code == 204:
            return {}

        current_page = response.json().get("_page")

        if current_page:
            return {"page": current_page + 1}

        return None

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
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


# Basic incremental stream
class IncrementalAmocrmIncrementalStream(AmocrmIncrementalStream, IncrementalMixin, ABC):
    # TODO: Fill in to checkpoint stream reads after N records. This prevents re-reading of data if the stream fails for any reason.
    state_checkpoint_interval = None

    @property
    def state(self) -> Mapping[str, Any]:
        if hasattr(self, "_state"):
            return self._state
        else:
            return {}

    @state.setter
    def state(self, value: Mapping[str, Any]):
        self._state = value

    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field: List[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        for record in super().read_records(
            sync_mode=sync_mode, cursor_field=cursor_field, stream_slice=stream_slice, stream_state=stream_state
        ):
          yield record

          stream_state_value = self.state.get(self.cursor_field, 0)
          self.state = {self.cursor_field: max(record[self.cursor_field], stream_state_value)}

    def stream_slices(self, stream_state: Mapping[str, Any] = None, **kwargs) -> Iterable[Optional[Mapping[str, any]]]:
      start_date_for_replication_ts = pendulum.parse(self.start_date_for_replication).format("X")
      start_ts = stream_state.get(self.cursor_field, start_date_for_replication_ts) if stream_state else start_date_for_replication_ts

      yield {"start_date": start_ts}



class Leads(IncrementalAmocrmIncrementalStream):
    cursor_field = "updated_at"

    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        self.start_date_for_replication = config["start_date_for_replication"]
        super().__init__(**kwargs)

    def path(self, **kwargs) -> str:
        return "leads"

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {
            "limit": 250,
            "with": "contacts,loss_reason",
            "filter[updated_at][from]": stream_slice["start_date"],
        }

        if next_page_token:
            params.update(**next_page_token)

        return params


class Events(IncrementalAmocrmIncrementalStream):
    cursor_field = "created_at"

    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        self.start_date_for_replication = config["start_date_for_replication"]
        self.end_date_for_replication = config["end_date_for_replication"]
        self.events = config.get("events")
        super().__init__(**kwargs)

    def path(self, **kwargs) -> str:
        return "events"

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        end_date_for_replication_ts = pendulum.parse(self.end_date_for_replication).format("X")
        params = {
            "limit": 250,
            "filter[created_at][from]": stream_slice["start_date"],
            "filter[created_at][to]": end_date_for_replication_ts,
        }

        if self.events:
            events = self.events.replace(" ", "").split(",")
            for idx, event in enumerate(events):
                params[f"filter[type][{idx}]"] = event

        if next_page_token:
            params.update(**next_page_token)

        return params

class Contacts(IncrementalAmocrmIncrementalStream):
    cursor_field = "updated_at"

    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        self.start_date_for_replication = config["start_date_for_replication"]
        super().__init__(**kwargs)

    def path(self, **kwargs) -> str:
        return "contacts"

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {
            "limit": 250,
            "filter[updated_at][from]": stream_slice["start_date"],
        }

        if next_page_token:
            params.update(**next_page_token)

        return params


class Pipelines(AmocrmIncrementalStream):
    primary_key = "id"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "leads/pipelines"


class Users(AmocrmIncrementalStream):
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


class Tasks(IncrementalAmocrmIncrementalStream):
    cursor_field = "updated_at"

    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.start_date_for_replication = config["start_date_for_replication"]

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        params = {
            "limit": 250,
            "filter[updated_at]": stream_slice["start_date"],
        }

        if next_page_token:
            params.update(**next_page_token)

        return params

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "tasks"


# Source
class SourceAmocrmIncremental(AbstractSource):
    refresh_endpoint = "https://hexlet.amocrm.ru/oauth2/access_token"

    def check_connection(self, logger, config) -> Tuple[bool, Any]:
        try:
            # Check connectivity
            auth = SingleUseRefreshTokenOauth2Authenticator(
                config,
                token_refresh_endpoint=self.refresh_endpoint,
            )
            leads_stream = Leads(authenticator=auth, config=config)

            stream_slices = list(leads_stream.stream_slices(sync_mode=SyncMode.full_refresh))
            next(leads_stream.read_records(sync_mode=SyncMode.full_refresh, stream_slice=stream_slices[0]))

            return True, None
        except Exception as error:
            return False, error

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        auth = SingleUseRefreshTokenOauth2Authenticator(
            config,
            token_refresh_endpoint=self.refresh_endpoint,
        )
        return [
            Events(authenticator=auth, config=config),
            Contacts(authenticator=auth, config=config),
            Leads(authenticator=auth, config=config),
            Pipelines(authenticator=auth),
            Users(authenticator=auth),
            Tasks(authenticator=auth, config=config),
        ]
