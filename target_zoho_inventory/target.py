"""ZohoInventory target class."""

from target_hotglue.target import TargetHotglue
from singer_sdk import typing as th

from target_zoho_inventory.sinks import (
    PurchaseOrderSink,
)


class TargetZohoInventory(TargetHotglue):
    """Sample target for ZohoInventory."""
    
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
    SINK_TYPES = [PurchaseOrderSink]

if __name__ == "__main__":
    TargetZohoInventory.cli()
