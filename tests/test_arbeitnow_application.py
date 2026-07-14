from tg_vacancy_bot.arbeitnow_application import build_arbeitnow_application_plan, is_arbeitnow_url
from tg_vacancy_bot.models import OperatorProfile


def test_arbeitnow_plan_uses_verified_apply_url_and_profile_fields(tmp_path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"pdf")
    profile = OperatorProfile(
        operator_user_id=42,
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+123",
        extra_fields={"personal_url": "https://example.com", "cover_letter": "Hello"},
    )

    plan = build_arbeitnow_application_plan("https://www.arbeitnow.com/jobs/example", profile, resume)

    assert plan.application_url == "https://www.arbeitnow.com/jobs/example/apply"
    assert plan.first_name == "Ada"
    assert plan.last_name == "Lovelace"
    assert plan.missing_fields == ()
    assert plan.resume_path == resume


def test_arbeitnow_plan_requires_name_email_and_existing_resume(tmp_path) -> None:
    plan = build_arbeitnow_application_plan(
        "https://arbeitnow.com/jobs/example", OperatorProfile(operator_user_id=42, full_name="Ada"), tmp_path / "missing.pdf"
    )

    assert plan.missing_fields == ("full_name", "email", "resume")


def test_arbeitnow_domain_check_rejects_lookalikes() -> None:
    assert is_arbeitnow_url("https://www.arbeitnow.com/jobs/example") is True
    assert is_arbeitnow_url("https://arbeitnow.example.com/jobs/example") is False
