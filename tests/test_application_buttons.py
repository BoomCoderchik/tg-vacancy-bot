from tg_vacancy_bot.application_buttons import application_button, application_callback_data
from tg_vacancy_bot.models import Vacancy


def test_application_button_uses_short_fingerprint_without_url() -> None:
    vacancy = Vacancy(
        title="Python Engineer",
        description="Remote backend role",
        source="Test",
        url="https://example.com/jobs/42?private=value",
    )

    callback_data = application_callback_data(vacancy)
    button = application_button(vacancy).inline_keyboard[0][0]

    assert button.text == "Откликнуться"
    assert button.callback_data == callback_data
    assert callback_data.startswith("apply:")
    assert len(callback_data) == len("apply:") + 32
    assert vacancy.url not in callback_data


def test_application_button_discloses_scheduled_queue_delay() -> None:
    vacancy = Vacancy(title="Python Engineer", description="Backend", source="Test")

    button = application_button(vacancy, queued=True).inline_keyboard[0][0]

    assert button.text == "Откликнуться (очередь)"
