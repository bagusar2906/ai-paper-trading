from dataclasses import dataclass


@dataclass
class Strategy:

    id: int | None = None

    name: str = ""

    description: str = ""

    strategy_type: str = ""

    config: dict | None = None

    is_active: bool = False