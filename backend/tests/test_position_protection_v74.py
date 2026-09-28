from app.position_protection import validate_protection_plan


def _setup(**overrides):
    setup = {
        "entry_low": 95, "entry_high": 105, "stop_loss": 85,
        "target_1": 125, "target_2": 145, "risk_reward": 2.0,
        "explanation": "Exit if the approved market structure is invalidated.",
    }
    setup.update(overrides)
    return setup


def test_complete_protection_plan_is_approved():
    result = validate_protection_plan(_setup(), {"stop_loss": 85})
    assert result["approved"] is True
    assert result["policy"]["stop_may_widen"] is False
    assert result["policy"]["average_down"] is False


def test_missing_or_wide_stop_is_blocked():
    result = validate_protection_plan(_setup(stop_loss=106), {})
    assert "INVALID_HARD_STOP_OR_ENTRY_RANGE" in result["blockers"]


def test_invalid_targets_and_low_risk_reward_are_blocked():
    result = validate_protection_plan(_setup(target_1=100, target_2=99, risk_reward=1.0), {})
    assert "INVALID_TARGET_LADDER" in result["blockers"]
    assert "RISK_REWARD_BELOW_MINIMUM" in result["blockers"]


def test_order_cannot_override_or_widen_approved_stop():
    result = validate_protection_plan(_setup(), {"stop_loss": 90})
    assert "STOP_OVERRIDE_FORBIDDEN" in result["blockers"]


def test_invalidation_rationale_is_mandatory():
    result = validate_protection_plan(_setup(explanation=""), {})
    assert "INVALIDATION_RATIONALE_MISSING" in result["blockers"]
