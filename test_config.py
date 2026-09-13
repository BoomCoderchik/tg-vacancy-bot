from tg_vacancy_bot.config import get_settings
s = get_settings()
print('LOCALIZE_DESCRIPTIONS:', s.localize_descriptions)
print('LOCALIZATION_PROVIDER:', s.localization_provider)
print('localization_api_key:', repr(s.localization_api_key))
print('openai_api_key:', repr(s.openai_api_key))
print('groq_api_key:', repr(s.groq_api_key))