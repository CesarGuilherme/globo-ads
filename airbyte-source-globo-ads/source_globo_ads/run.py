import sys

from airbyte_cdk.entrypoint import launch

from .source import SourceGloboAds


def run() -> None:
    launch(SourceGloboAds(), sys.argv[1:])
