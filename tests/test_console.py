from tg_vacancy_bot.console import write_stdout


def test_write_stdout_handles_unicode(capsys) -> None:
    write_stdout("💼 Вакансия")

    assert "Вакансия" in capsys.readouterr().out
