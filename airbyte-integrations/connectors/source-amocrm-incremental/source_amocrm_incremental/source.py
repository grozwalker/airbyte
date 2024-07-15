#
# Copyright (c) 2024 Airbyte, Inc., all rights reserved.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pendulum
import datetime
import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.requests_native_auth.oauth import SingleUseRefreshTokenOauth2Authenticator


# Basic full refresh stream
class AmocrmIncrementalStream(HttpStream, ABC):
    url_base = "https://hexlet.amocrm.ru/api/v4/"

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
class IncrementalAmocrmIncrementalStream(AmocrmIncrementalStream, ABC):
    # TODO: Fill in to checkpoint stream reads after N records. This prevents re-reading of data if the stream fails for any reason.
    state_checkpoint_interval = None

    @property
    def cursor_field(self) -> str:
        """
        TODO
        Override to return the cursor field used by this stream e.g: an API entity might always use created_at as the cursor field. This is
        usually id or date based. This field's presence tells the framework this in an incremental stream. Required for incremental.

        :return str: The name of the cursor field.
        """
        return self.cursor_field

    def get_updated_state(self, current_stream_state: MutableMapping[str, Any], latest_record: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Override to determine the latest state after reading the latest record. This typically compared the cursor_field from the latest record and
        the current state and picks the 'most' recent cursor. This is how a stream's state is determined. Required for incremental.
        """
        state_value = max(current_stream_state.get(self.cursor_field, 0), latest_record.get(self.cursor_field, ""))
        return {self.cursor_field: state_value}


class Leads(IncrementalAmocrmIncrementalStream):
    cursor_field = "updated_at"

    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        self.start_date_for_replication = config["start_date_for_replication"]
        super().__init__(**kwargs)

    def path(self, **kwargs) -> str:
        return "leads"

    def stream_slices(self, stream_state: Mapping[str, Any] = None, **kwargs) -> Iterable[Optional[Mapping[str, any]]]:
        """
        TODO: Optionally override this method to define this stream's slices. If slicing is not needed, delete this method.

        Slices control when state is saved. Specifically, state is saved after a slice has been fully read.
        This is useful if the API offers reads by groups or filters, and can be paired with the state object to make reads efficient. See the "concepts"
        section of the docs for more information.

        The function is called before reading any records in a stream. It returns an Iterable of dicts, each containing the
        necessary data to craft a request for a slice. The stream state is usually referenced to determine what slices need to be created.
        This means that data in a slice is usually closely related to a stream's cursor_field and stream_state.

        An HTTP request is made for each returned slice. The same slice can be accessed in the path, request_params and request_header functions to help
        craft that specific request.

        For example, if https://example-api.com/v1/employees offers a date query params that returns data for that particular day, one way to implement
        this would be to consult the stream state object for the last synced date, then return a slice containing each date from the last synced date
        till now. The request_params function would then grab the date from the stream_slice and make it part of the request by injecting it into
        the date query param.
        """
        # raise NotImplementedError("Implement stream slices or delete this method!")

        start_date_for_replication_ts = pendulum.parse(self.start_date_for_replication).format("X")
        start_ts = stream_state.get(self.cursor_field, start_date_for_replication_ts) if stream_state else start_date_for_replication_ts

        yield {"start_date": start_ts}

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
            Leads(authenticator=auth, config=config),
        ]
