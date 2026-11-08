"""Fixed value sets and small records shared by every layer."""
from enum import StrEnum
from typing import NamedTuple


class Kind(StrEnum):
    """What an incident is, as the reader classifies it."""
    SUPPLIER_DELAY = "supplier_delay"
    PLANT_OUTAGE = "plant_outage"
    QUALITY_HOLD = "quality_hold"
    NOISE = "noise"
    UNCONFIRMED = "unconfirmed"


class Tool(StrEnum):
    """Enterprise tools the agents may call."""
    RESCHEDULE = "mes.reschedule"
    TRANSFER = "mes.transfer"
    NOTIFY_DEALER = "dealer.notify"
    STOP_SALE = "dealer.stop_sale"
    ASSIGN_LOANER = "crm.assign_loaner"
    NOTIFY_CUSTOMER = "crm.notify_customer"
    HOLD_LOT = "quality.hold_lot"
    ESCALATE = "escalate"


class Tier(StrEnum):
    """Customer loyalty tier."""
    PLATINUM = "Platinum"
    GOLD = "Gold"
    STANDARD = "Standard"


class Status(StrEnum):
    """Where an incident stands, shown to the user."""
    RESOLVED = "resolved"
    VERIFIED = "verified"
    REVIEW = "review"
    IGNORED = "ignored"
    BLOCKED = "blocked"
    PARTIAL = "partial"
    FAILED = "failed"


REAL_KINDS = (Kind.PLANT_OUTAGE, Kind.SUPPLIER_DELAY, Kind.QUALITY_HOLD)
MOVES = (Tool.RESCHEDULE, Tool.TRANSFER)
TIER_RANK = {Tier.PLATINUM: 0, Tier.GOLD: 1, Tier.STANDARD: 2}
LOANER_TIERS = (Tier.PLATINUM, Tier.GOLD)


class Placement(NamedTuple):
    """Where the planner puts one build; tool is None when no compliant slot exists."""
    tool: Tool | None
    plant: str | None
    idx: int | None
    why: str


class Downstream(NamedTuple):
    """A customer order waiting on a build, with its dealer and customer."""
    customer_order: str
    dealer: str
    customer: str
