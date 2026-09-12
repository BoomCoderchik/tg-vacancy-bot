# План единой фильтрации вакансий для Telegram-канала

## Выбор специальности и грейда (обновлено 2026-09-11)

Фильтр больше не захардкожен на Junior Frontend/Fullstack. Активный фильтр —
глобальный (один `TARGET_CHAT_ID`): несколько специальностей + несколько
грейдов, хранится в SQLite (`vacancy_filters`, одна строка `id=1`,
списки в `specialties_json`/`grades_json`, миграция v5), дефолт —
`frontend_fullstack`/`junior`.

- Команда `/filters` (только `OPERATOR_USER_IDS`): шаг 1 — специальности
  (`frontend`, `backend`, `fullstack`, `frontend_fullstack`, `mobile`, `qa`,
  `devops`, `data`, `design`), шаг 2 — грейды (`intern`, `junior`, `middle`,
  `senior`, `lead`). Кнопки-тогглы: выбранные помечены ✅, выбор можно
  менять до нажатия «Далее»; дальше — подтверждение «Применить».
- Пост проходит, если совпала хотя бы одна выбранная специальность и хотя бы
  один выбранный грейд без конфликтующего сениорити у роли.
- `/start` у оператора сразу открывает панель выбора специальностей.
- `/status` показывает активный фильтр (`Vacancy filter: Backend • Middle`).
- Реализация: `evaluate_vacancy_policy(text, specialty, grade)` и
  `filter_it_vacancies(vacancies, specialty, grade)` в
  `tg_vacancy_bot/sources/filters.py`; старые вызовы с одним аргументом
  работают как раньше (дефолт junior frontend/fullstack).
- Фильтр применяется везде: ручной intake (`intake.py`, `bot.py`), фоновый
  поллинг (`source_polling.py`), `poll-once` и `preview-sources` (`app.py`).
- Кнопка «Откликнуться» больше не прикрепляется к публикуемым карточкам
  (`source_polling.py`, `publisher.py`, `bot.py`); очередь заявок и `/profile`
  продолжают работать для ранее созданных колбэков.

## Действующая политика (обновлено 2026-08-25)

Канал публикует только посты, где реально ищут Junior-разработчиков
Fullstack/Frontend. Единая проверка реализована в
`tg_vacancy_bot/sources/filters.py` (`evaluate_vacancy_policy`) и применяется
ко всем путям публикации: source-адаптерам, пересланным сообщениям, режиму
`copy`, фоновому поллингу и командам предпросмотра.

Пост проходит публикацию только при выполнении всех условий:

| Условие | Примеры сигналов |
| --- | --- |
| Сигнал найма | `hiring`, `looking for`, `join our team`, `open role`, `ищем`, `нанимаем`, `вакансия`, `в команду` |
| Явная роль Frontend/Fullstack | `frontend`, `front-end`, `фронтенд`, `fullstack`, `full-stack`, `фулстек` |
| Уровень junior или входной | `junior`, `джуниор`, `intern`, `trainee`, `стажер`, `стажировка`, `entry-level`, `без опыта` |

Пост отклоняется с диагностической причиной, если:

- роль Frontend/Fullstack не найдена (`no_frontend_fullstack_role`);
- нет маркера уровня junior/entry (`no_junior_level_evidence`);
- к роли напрямую прикреплен не-junior уровень: `senior`, `middle`, `lead`,
  `сеньор`, `мидл`, `ведущий` и т.п. (`non_junior_seniority_for_role`);
- текст рекламирует курсы, bootcamp или наставничество вместо работы
  (`excluded_context`);
- отсутствует сигнал найма (`no_hiring_intent`).

Backend-only, mobile, QA, DevOps, data-, design- и менеджерские роли больше не
публикуются: они не проходят проверку роли.

## Сохраненные продуктовые ограничения

- Публикуются internships, trainee и стажировки, если сама роль —
  frontend/fullstack.
- Форматы занятости freelance, contract, part-time и unpaid разрешены.
- Нет фильтров по стране, формату office/hybrid/remote, зарплате, языку,
  гражданству или разрешению на работу.
- Посты «Senior/Middle + джунам тут не место», а также смешанные объявления
  «Junior & Middle» отклоняются консервативно: точность важнее полноты.

## Автогенерация discovery-запросов из фильтра

Discovery-запросы LinkedIn-источников строятся из активного `VacancyFilter`
(`tg_vacancy_bot/sources/filter_queries.py`): один интент на
(specialty × язык en/ru), site-scope и hiring-intent переиспользуются из
`linkedin_search_profile.py`, Apify-запросы — plain-text строго ≤85 символов,
guest-ключи — plain-lowercase. `frontend_fullstack` раскрывается в
`frontend`+`fullstack`. Хуки в `source_polling.poll_sources_once`,
`app.poll_once`, `app.preview_sources` и `diagnose-linkedin` применяют
`apply_filter_queries()` до `build_adapters`. Ручные `LINKEDIN_*`-запросы в
`.env` имеют приоритет: поле со значением ≠ дефолта `Settings` не
перетирается (headless — только если raw пуст).

## Поисковые профили источников

Дефолтные запросы всех LinkedIn-источников сужены до junior-формулировок:

- `LINKEDIN_POST_SEARCH_QUERY` и fallback в GitHub Actions workflow — явные
  `"junior frontend developer"` / `"junior fullstack developer"` варианты;
- `LINKEDIN_POST_SCRAPER_QUERY` — три ветки (en-hiring, en-looking, ru) с
  junior-ролями;
- `LINKEDIN_POST_APIFY_SEARCH_QUERIES` — только junior FE/FS запросы;
- встроенный headless-профиль (`DEFAULT_SEARCH_INTENTS`) — 4 интента:
  frontend/fullstack × en/ru.

## Тестовая стратегия

- `tests/test_vacancy_policy.py` — параметризованная матрица принимаемых и
  отклоняемых постов с проверкой диагностических причин.
- `tests/test_intake.py` — ручной intake применяет ту же политику.
- `tests/test_sources.py::test_filter_it_vacancies_*` — общий фильтр
  source-пути принимает только junior FE/FS.
