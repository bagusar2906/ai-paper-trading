from dataclasses import dataclass


@dataclass
class EMARSIADXConfig:

    ema_length: int = 200

    rsi_length: int = 14

    rsi_os: int = 20

    rsi_ob: int = 80

    adx_length: int = 14

    adx_smoothing: int = 14

    adx_level: int = 25

    stop_loss_pips: int = 200

    risk_reward: float = 2.0