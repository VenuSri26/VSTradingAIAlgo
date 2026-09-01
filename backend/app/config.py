"""
Canonical configuration loader.

Spec section 28 explicitly calls out repeated production incidents from
multiple conflicting .env files and stale-token restarts. This module is the
ONE place environment variables are read. Every other module imports
`settings` from here — nothing else calls os.getenv directly.

Startup validation (validate()) is called by start_nifty.sh / main.py before
the server accepts traffic, and fails loudly rather than booting in a broken
half-configured state.
"""
from __future__ import annotations
import os
import sys
from dataclasses import dataclass, field
from app.agents.alignment import DEFAULT_WEIGHTS

REQUIRED_LIVE_VARS = ["KITE_API_KEY", "KITE_API_SECRET", "KITE_ACCESS_TOKEN"]


@dataclass
class Settings:
    trading_mode: str = os.getenv("TRADING_MODE", "mock")  # "mock" | "live"
    kite_api_key: str | None = os.getenv("KITE_API_KEY")
    kite_api_secret: str | None = os.getenv("KITE_API_SECRET")
    kite_access_token: str | None = os.getenv("KITE_ACCESS_TOKEN")
    admin_token: str | None = os.getenv("ADMIN_TOKEN")
    app_access_token: str | None = os.getenv("APP_ACCESS_TOKEN")
    require_https: bool = os.getenv("REQUIRE_HTTPS", "false").lower() in ("1", "true", "yes", "on")
    live_orders_enabled: bool = os.getenv("LIVE_ORDERS_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    execution_preview_ttl_sec: int = int(os.getenv("EXECUTION_PREVIEW_TTL_SEC", "120"))
    app_timezone: str = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
    nifty_lot_size: int = int(os.getenv("NIFTY_LOT_SIZE", "75"))

    max_trades_per_day: int = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    daily_loss_limit: float = float(os.getenv("DAILY_LOSS_LIMIT", "5000"))
    max_consecutive_losses: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2"))
    risk_cooldown_minutes: int = int(os.getenv("RISK_COOLDOWN_MINUTES", "15"))
    max_capital_utilization_pct: float = float(os.getenv("MAX_CAPITAL_UTILIZATION_PCT", "80"))
    max_data_age_sec: float = float(os.getenv("MAX_DATA_AGE_SEC", "10"))
    vix_spike_threshold: float = float(os.getenv("VIX_SPIKE_THRESHOLD", "22"))
    min_risk_reward: float = float(os.getenv("MIN_RISK_REWARD", "1.5"))
    paper_capital: float = float(os.getenv("PAPER_CAPITAL", "10000"))
    max_risk_per_trade_pct: float = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "2"))
    paper_slippage_rupees: float = float(os.getenv("PAPER_SLIPPAGE_RUPEES", "0.5"))
    paper_cost_rate: float = float(os.getenv("PAPER_COST_RATE", "0.0015"))
    min_agent_coverage: float = float(os.getenv("MIN_AGENT_COVERAGE", "0.70"))
    max_agent_disagreement: float = float(os.getenv("MAX_AGENT_DISAGREEMENT", "0.45"))

    # Restart-safe automated paper monitoring. This never places broker orders.
    paper_auto_monitor_enabled: bool = os.getenv("PAPER_AUTO_MONITOR_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    paper_monitor_interval_sec: float = float(os.getenv("PAPER_MONITOR_INTERVAL_SEC", "5"))
    paper_eod_exit_time: str = os.getenv("PAPER_EOD_EXIT_TIME", "15:20")
    paper_notification_path: str = os.getenv("PAPER_NOTIFICATION_PATH", "./data/paper_notifications.jsonl")

    market_data_supervisor_enabled: bool = os.getenv("MARKET_DATA_SUPERVISOR_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    market_data_poll_interval_sec: float = float(os.getenv("MARKET_DATA_POLL_INTERVAL_SEC", "3"))
    market_data_state_path: str = os.getenv("MARKET_DATA_STATE_PATH", "./data/market_data_state.json")
    market_open_time: str = os.getenv("MARKET_OPEN_TIME", "09:15")
    market_close_time: str = os.getenv("MARKET_CLOSE_TIME", "15:30")
    market_holidays: str = os.getenv("MARKET_HOLIDAYS", "")
    feed_alert_log_path: str = os.getenv("FEED_ALERT_LOG_PATH", "./data/feed_alerts.jsonl")
    tick_bridge_history_path: str = os.getenv("TICK_BRIDGE_HISTORY_PATH", "./data/tick_bridge.jsonl")
    token_warn_age_sec: float = float(os.getenv("TOKEN_WARN_AGE_SEC", "3600"))
    token_block_age_sec: float = float(os.getenv("TOKEN_BLOCK_AGE_SEC", "43200"))
    kite_websocket_requested: bool = os.getenv("KITE_WEBSOCKET_REQUESTED", "false").lower() in ("1", "true", "yes", "on")
    instrument_sync_interval_hours: int = int(os.getenv("INSTRUMENT_SYNC_INTERVAL_HOURS", "12"))
    websocket_batch_size: int = int(os.getenv("WEBSOCKET_BATCH_SIZE", "200"))
    websocket_queue_size: int = int(os.getenv("WEBSOCKET_QUEUE_SIZE", "2000"))
    websocket_heartbeat_timeout_sec: float = float(os.getenv("WEBSOCKET_HEARTBEAT_TIMEOUT_SEC", "20"))
    websocket_reconnect_base_sec: float = float(os.getenv("WEBSOCKET_RECONNECT_BASE_SEC", "2"))
    websocket_reconnect_max_sec: float = float(os.getenv("WEBSOCKET_RECONNECT_MAX_SEC", "60"))
    websocket_subscription_refresh_sec: float = float(os.getenv("WEBSOCKET_SUBSCRIPTION_REFRESH_SEC", "900"))
    websocket_atm_range: int = int(os.getenv("WEBSOCKET_ATM_RANGE", "8"))
    runtime_notification_path: str = os.getenv("RUNTIME_NOTIFICATION_PATH", "./data/runtime_notifications.jsonl")
    notification_outbox_path: str = os.getenv("NOTIFICATION_OUTBOX_PATH", "./data/notification_outbox.jsonl")
    notification_webhook_url: str | None = os.getenv("NOTIFICATION_WEBHOOK_URL")
    notification_timeout_sec: float = float(os.getenv("NOTIFICATION_TIMEOUT_SEC", "5"))
    notification_smtp_host: str | None = os.getenv("NOTIFICATION_SMTP_HOST")
    notification_smtp_port: int = int(os.getenv("NOTIFICATION_SMTP_PORT", "587"))
    notification_smtp_username: str | None = os.getenv("NOTIFICATION_SMTP_USERNAME")
    notification_smtp_password: str | None = os.getenv("NOTIFICATION_SMTP_PASSWORD")
    notification_smtp_from: str | None = os.getenv("NOTIFICATION_SMTP_FROM")
    notification_smtp_to: str | None = os.getenv("NOTIFICATION_SMTP_TO")
    notification_smtp_to_info: str | None = os.getenv("NOTIFICATION_SMTP_TO_INFO")
    notification_smtp_to_warning: str | None = os.getenv("NOTIFICATION_SMTP_TO_WARNING")
    notification_smtp_to_critical: str | None = os.getenv("NOTIFICATION_SMTP_TO_CRITICAL")
    notification_smtp_to_broker: str | None = os.getenv("NOTIFICATION_SMTP_TO_BROKER")
    notification_smtp_to_infrastructure: str | None = os.getenv("NOTIFICATION_SMTP_TO_INFRASTRUCTURE")
    notification_smtp_to_trading: str | None = os.getenv("NOTIFICATION_SMTP_TO_TRADING")
    notification_whatsapp_enabled: bool = os.getenv("NOTIFICATION_WHATSAPP_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    notification_whatsapp_api_url: str | None = os.getenv("NOTIFICATION_WHATSAPP_API_URL")
    notification_whatsapp_token: str | None = os.getenv("NOTIFICATION_WHATSAPP_TOKEN")
    notification_whatsapp_to: str | None = os.getenv("NOTIFICATION_WHATSAPP_TO")
    notification_smtp_use_tls: bool = os.getenv("NOTIFICATION_SMTP_USE_TLS", "true").lower() in ("1", "true", "yes", "on")
    greeks_validation_history_path: str = os.getenv("GREEKS_VALIDATION_HISTORY_PATH", "./data/greeks_validation_history.jsonl")
    market_calendar_path: str = os.getenv("MARKET_CALENDAR_PATH", "./data/nse_holidays.json")
    market_calendar_source_url: str | None = os.getenv("MARKET_CALENDAR_SOURCE_URL")
    market_calendar_source_format: str = os.getenv("MARKET_CALENDAR_SOURCE_FORMAT", "auto")
    notification_dispatch_enabled: bool = os.getenv("NOTIFICATION_DISPATCH_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    notification_dispatch_interval_sec: float = float(os.getenv("NOTIFICATION_DISPATCH_INTERVAL_SEC", "60"))
    notification_retry_base_sec: float = float(os.getenv("NOTIFICATION_RETRY_BASE_SEC", "60"))
    notification_retry_max_sec: float = float(os.getenv("NOTIFICATION_RETRY_MAX_SEC", "3600"))
    notification_escalate_after_sec: float = float(os.getenv("NOTIFICATION_ESCALATE_AFTER_SEC", "900"))
    notification_max_attempts: int = int(os.getenv("NOTIFICATION_MAX_ATTEMPTS", "8"))
    operational_digest_path: str = os.getenv("OPERATIONAL_DIGEST_PATH", "./data/operational_digests.jsonl")
    daily_digest_enabled: bool = os.getenv("DAILY_DIGEST_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    daily_digest_time: str = os.getenv("DAILY_DIGEST_TIME", "16:00")
    daily_digest_poll_interval_sec: float = float(os.getenv("DAILY_DIGEST_POLL_INTERVAL_SEC", "60"))
    daily_digest_enqueue: bool = os.getenv("DAILY_DIGEST_ENQUEUE", "true").lower() in ("1", "true", "yes", "on")
    live_session_validation_path: str = os.getenv("LIVE_SESSION_VALIDATION_PATH", "./data/live_session_validation.jsonl")
    live_session_min_samples: int = int(os.getenv("LIVE_SESSION_MIN_SAMPLES", "20"))
    live_session_min_ready_ratio: float = float(os.getenv("LIVE_SESSION_MIN_READY_RATIO", "0.95"))
    live_session_max_feed_age_sec: float = float(os.getenv("LIVE_SESSION_MAX_FEED_AGE_SEC", "10"))
    live_session_max_error_ratio: float = float(os.getenv("LIVE_SESSION_MAX_ERROR_RATIO", "0.05"))
    live_session_auto_record_enabled: bool = os.getenv("LIVE_SESSION_AUTO_RECORD_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    live_session_auto_record_interval_sec: float = float(os.getenv("LIVE_SESSION_AUTO_RECORD_INTERVAL_SEC", "30"))
    live_session_cert_min_sessions: int = int(os.getenv("LIVE_SESSION_CERT_MIN_SESSIONS", "5"))
    live_session_cert_min_ready_session_ratio: float = float(os.getenv("LIVE_SESSION_CERT_MIN_READY_SESSION_RATIO", "0.80"))
    live_session_cert_min_average_ready_ratio: float = float(os.getenv("LIVE_SESSION_CERT_MIN_AVERAGE_READY_RATIO", "0.95"))
    live_session_cert_min_average_websocket_ratio: float = float(os.getenv("LIVE_SESSION_CERT_MIN_AVERAGE_WEBSOCKET_RATIO", "0.80"))
    live_session_cert_max_average_error_ratio: float = float(os.getenv("LIVE_SESSION_CERT_MAX_AVERAGE_ERROR_RATIO", "0.05"))
    live_session_cert_max_average_feed_age_sec: float = float(os.getenv("LIVE_SESSION_CERT_MAX_AVERAGE_FEED_AGE_SEC", "10"))
    live_session_cert_eod_enabled: bool = os.getenv("LIVE_SESSION_CERT_EOD_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    live_session_cert_eod_time: str = os.getenv("LIVE_SESSION_CERT_EOD_TIME", "16:15")
    live_session_cert_eod_poll_interval_sec: float = float(os.getenv("LIVE_SESSION_CERT_EOD_POLL_INTERVAL_SEC", "60"))

    poll_interval_sec: float = float(os.getenv("POLL_INTERVAL_SEC", "3"))
    cors_origins: list[str] = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", "http://localhost:5173"
    ).split(","))

    agent_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    audit_log_path: str = os.getenv("AUDIT_LOG_PATH", "./data/audit_log.jsonl")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_json: bool = os.getenv("LOG_JSON", "true").lower() in ("1", "true", "yes", "on")
    log_file_path: str | None = os.getenv("LOG_FILE_PATH", "./data/vstradingai.jsonl")

    def is_live(self) -> bool:
        return self.trading_mode.lower() == "live"


settings = Settings()


class ConfigError(Exception):
    pass


def validate(settings_obj: Settings = settings) -> list[str]:
    """Returns list of problems (empty = OK). Does not raise, so callers
    (API health route, startup script) can report ALL problems at once
    rather than failing on the first one."""
    problems = []

    if settings_obj.trading_mode not in ("mock", "live"):
        problems.append(f"TRADING_MODE must be 'mock' or 'live', got '{settings_obj.trading_mode}'")

    if settings_obj.is_live():
        for var in REQUIRED_LIVE_VARS:
            if not getattr(settings_obj, var.lower(), None):
                problems.append(f"Missing required env var for live mode: {var}")

    if abs(sum(settings_obj.agent_weights.values()) - 1.0) > 0.01:
        problems.append(
            f"Agent weights must sum to 1.0, got {sum(settings_obj.agent_weights.values()):.3f}"
        )

    if settings_obj.max_trades_per_day < 1:
        problems.append("MAX_TRADES_PER_DAY must be >= 1")
    if settings_obj.daily_loss_limit <= 0:
        problems.append("DAILY_LOSS_LIMIT must be > 0")
    if settings_obj.max_consecutive_losses < 1:
        problems.append("MAX_CONSECUTIVE_LOSSES must be >= 1")
    if settings_obj.risk_cooldown_minutes < 0:
        problems.append("RISK_COOLDOWN_MINUTES must be >= 0")
    if not 1 <= settings_obj.max_capital_utilization_pct <= 100:
        problems.append("MAX_CAPITAL_UTILIZATION_PCT must be between 1 and 100")
    if settings_obj.poll_interval_sec < 1:
        problems.append("POLL_INTERVAL_SEC must be >= 1")
    if settings_obj.market_data_poll_interval_sec < 1:
        problems.append("MARKET_DATA_POLL_INTERVAL_SEC must be >= 1")
    if settings_obj.instrument_sync_interval_hours < 1:
        problems.append("INSTRUMENT_SYNC_INTERVAL_HOURS must be >= 1")
    if settings_obj.websocket_batch_size < 1:
        problems.append("WEBSOCKET_BATCH_SIZE must be >= 1")
    if settings_obj.websocket_queue_size < settings_obj.websocket_batch_size:
        problems.append("WEBSOCKET_QUEUE_SIZE must be >= WEBSOCKET_BATCH_SIZE")
    if settings_obj.websocket_heartbeat_timeout_sec < 5:
        problems.append("WEBSOCKET_HEARTBEAT_TIMEOUT_SEC must be >= 5")
    if settings_obj.websocket_reconnect_base_sec < 1:
        problems.append("WEBSOCKET_RECONNECT_BASE_SEC must be >= 1")
    if settings_obj.websocket_reconnect_max_sec < settings_obj.websocket_reconnect_base_sec:
        problems.append("WEBSOCKET_RECONNECT_MAX_SEC must be >= WEBSOCKET_RECONNECT_BASE_SEC")
    if settings_obj.websocket_subscription_refresh_sec < 30:
        problems.append("WEBSOCKET_SUBSCRIPTION_REFRESH_SEC must be >= 30")
    if settings_obj.notification_timeout_sec < 1:
        problems.append("NOTIFICATION_TIMEOUT_SEC must be >= 1")
    if not 1 <= settings_obj.notification_smtp_port <= 65535:
        problems.append("NOTIFICATION_SMTP_PORT must be between 1 and 65535")
    if settings_obj.notification_dispatch_interval_sec < 10:
        problems.append("NOTIFICATION_DISPATCH_INTERVAL_SEC must be >= 10")
    if settings_obj.notification_retry_base_sec < 10:
        problems.append("NOTIFICATION_RETRY_BASE_SEC must be >= 10")
    if settings_obj.notification_retry_max_sec < settings_obj.notification_retry_base_sec:
        problems.append("NOTIFICATION_RETRY_MAX_SEC must be >= NOTIFICATION_RETRY_BASE_SEC")
    if settings_obj.daily_digest_poll_interval_sec < 10:
        problems.append("DAILY_DIGEST_POLL_INTERVAL_SEC must be >= 10")
    try:
        hh, mm = [int(x) for x in settings_obj.daily_digest_time.split(":", 1)]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except Exception:
        problems.append("DAILY_DIGEST_TIME must use HH:MM 24-hour format")
    if settings_obj.notification_escalate_after_sec < 60:
        problems.append("NOTIFICATION_ESCALATE_AFTER_SEC must be >= 60")
    if settings_obj.notification_max_attempts < 1:
        problems.append("NOTIFICATION_MAX_ATTEMPTS must be >= 1")
    if not 2 <= settings_obj.websocket_atm_range <= 20:
        problems.append("WEBSOCKET_ATM_RANGE must be between 2 and 20")
    if settings_obj.paper_capital <= 0:
        problems.append("PAPER_CAPITAL must be > 0")
    if not 0 < settings_obj.max_risk_per_trade_pct <= 10:
        problems.append("MAX_RISK_PER_TRADE_PCT must be between 0 and 10")
    if settings_obj.paper_slippage_rupees < 0:
        problems.append("PAPER_SLIPPAGE_RUPEES must be >= 0")
    if settings_obj.paper_cost_rate < 0:
        problems.append("PAPER_COST_RATE must be >= 0")
    if not 0.5 <= settings_obj.min_agent_coverage <= 1.0:
        problems.append("MIN_AGENT_COVERAGE must be between 0.5 and 1.0")
    if not 0.0 <= settings_obj.max_agent_disagreement <= 1.0:
        problems.append("MAX_AGENT_DISAGREEMENT must be between 0.0 and 1.0")
    if settings_obj.paper_monitor_interval_sec < 1:
        problems.append("PAPER_MONITOR_INTERVAL_SEC must be >= 1")
    try:
        hh, mm = [int(x) for x in settings_obj.paper_eod_exit_time.split(":", 1)]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except (ValueError, TypeError):
        problems.append("PAPER_EOD_EXIT_TIME must be HH:MM")
    if settings_obj.nifty_lot_size <= 0:
        problems.append("NIFTY_LOT_SIZE must be > 0")
    if settings_obj.log_level.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        problems.append("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    if settings_obj.is_live() and not settings_obj.admin_token:
        problems.append("ADMIN_TOKEN is required in live mode for protected position endpoints")
    if settings_obj.execution_preview_ttl_sec < 30:
        problems.append("EXECUTION_PREVIEW_TTL_SEC must be >= 30")
    if settings_obj.live_orders_enabled and not settings_obj.is_live():
        problems.append("LIVE_ORDERS_ENABLED requires TRADING_MODE=live")

    return problems


def validate_or_exit() -> None:
    problems = validate()
    if problems:
        print("CONFIG VALIDATION FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    validate_or_exit()
    print(f"Config OK. TRADING_MODE={settings.trading_mode}")
