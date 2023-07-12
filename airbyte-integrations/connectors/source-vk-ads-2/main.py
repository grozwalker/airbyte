#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_vk_ads_2 import SourceVkAds_2

if __name__ == "__main__":
    source = SourceVkAds_2()
    launch(source, sys.argv[1:])
