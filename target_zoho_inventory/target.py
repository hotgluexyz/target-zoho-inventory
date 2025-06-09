"""ZohoInventory target class."""

from target_hotglue.target import TargetHotglue
from typing import List, Optional, Union
from pathlib import PurePath
from singer_sdk import typing as th

from target_zoho_inventory.sinks import (
    PurchaseOrderSink,
    BuyOrderSink,
    AssemblyOrderSink
)


class TargetZohoInventory(TargetHotglue):
    """Sample target for ZohoInventory."""

    def __init__(
        self,
        config: Optional[Union[dict, PurePath, str, List[Union[PurePath, str]]]] = None,
        parse_env_config: bool = False,
        validate_config: bool = True,
        state: str = None
    ) -> None:
        self.config_file = config[0]
        super().__init__(config, parse_env_config, validate_config)
    
    name = "target-zohoinventory"
    config_jsonschema = th.PropertiesList(
        th.Property(
            "client_id",
            th.StringType,
            description="Application ID for Zoho Inventory OAuth application"
        ),
        th.Property(
            "client_secret",
            th.StringType,
            description="Client Secret for Zoho Inventory OAuth application"
        ),
        th.Property(
            "refresh_token",
            th.StringType,
            description="Refresh token for client app"
        )
    ).to_dict()
    SINK_TYPES = [PurchaseOrderSink, BuyOrderSink, AssemblyOrderSink]

if __name__ == "__main__":
    TargetZohoInventory.cli()
