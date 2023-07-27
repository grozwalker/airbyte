#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_yandex_webmaster import SourceYandexWebmaster

if __name__ == "__main__":
    source = SourceYandexWebmaster()
    launch(source, sys.argv[1:])
