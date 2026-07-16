# Очередь откликов без постоянно работающего сервера

## Что делает режим

Когда локальный бот выключен, Telegram хранит нажатие `Откликнуться` как
необработанный callback. Плановый GitHub Actions runner раз в 15 минут запускает
`tg-vacancy-bot process-applications-once`, забирает накопленные callback,
проверяет Telegram ID оператора, временно скачивает резюме из Telegram,
запускает Playwright и отправляет результат в личный чат.

GitHub Actions runner является одноразовым: после выполнения он удаляется.
Обычная задержка составляет от 0 до 15 минут, но GitHub может задержать
scheduled workflow. Telegram хранит необработанные updates не более 24 часов.

## Граница автоматической отправки

`Отклик отправлен` показывается только после доказанного состояния успеха.
Автоматическая финальная отправка разрешена только когда одновременно выполнены
все условия:

- исходная вакансия относится к `arbeitnow.com`;
- конечная форма после перехода остаётся на `arbeitnow.com`;
- присутствует ровно один проверенный набор полей и одна submit-кнопка;
- нет login, CAPTCHA или 2FA;
- после клика форма исчезла и появилась известная страница успеха.

Свежие вакансии Arbeitnow часто перенаправляют на JOIN. JOIN запрашивает email
authentication и reCAPTCHA, поэтому такой сценарий не обходится и завершается
статусом `manual_required` со ссылкой на вакансию. Это не считается отправленным
откликом.

## Первичная настройка

1. Временно запустите локального бота и откройте личный чат с ним.
2. Выполните `/profile`, заполните имя и email, затем загрузите PDF/DOCX-резюме.
3. Выполните `/queue_resume_id` и скопируйте выданный Telegram `file_id`.
4. В GitHub откройте `Settings -> Secrets and variables -> Actions`.
5. Добавьте обязательные repository secrets:

   - `TELEGRAM_BOT_TOKEN`;
   - `TARGET_CHAT_ID`;
   - `OPERATOR_USER_IDS` — ровно один Telegram ID;
   - `APPLICATION_QUEUE_ENABLED=true`;
   - `APPLICATION_AUTO_SUBMIT=true`;
   - `APPLICATION_ALLOWED_DOMAINS=arbeitnow.com`;
   - `APPLICATION_QUEUE_PROFILE_FULL_NAME`;
   - `APPLICATION_QUEUE_PROFILE_EMAIL`;
   - `APPLICATION_QUEUE_RESUME_FILE_ID` — значение из `/queue_resume_id`;
   - `APPLICATION_QUEUE_RESUME_FILE_NAME` — имя с расширением `.pdf` или `.docx`.

6. При необходимости добавьте:

   - `APPLICATION_QUEUE_PROFILE_PHONE`;
   - `APPLICATION_QUEUE_PROFILE_PERSONAL_URL`;
   - `APPLICATION_QUEUE_PROFILE_COVER_LETTER`.

7. Остановите локальный бот. Нельзя одновременно использовать long polling и
   пакетный `getUpdates` для одного Telegram bot token: один процесс может забрать
   update раньше другого.
8. В GitHub Actions вручную запустите `Scheduled vacancy source polling` и
   проверьте шаг `Process queued application clicks`.

## Использование

1. Нажмите `Откликнуться` под опубликованной карточкой.
2. Дождитесь следующего запуска GitHub Actions.
3. Получите постоянное личное сообщение с фактическим результатом.

Короткий Telegram-индикатор после нажатия может завершиться таймаутом до запуска
Actions. Это ожидаемо: мгновенный `answerCallbackQuery` без webhook невозможен.
Сам callback остаётся в очереди Telegram.

## Состояние и защита от дублей

SQLite из `data/vacancies.sqlite3` восстанавливается через GitHub Actions cache и
содержит опубликованные vacancy fingerprints и статусы откликов. Повторное
нажатие не создаёт вторую заявку. Перед финальным кликом статус меняется на
`submitting`. Если runner остановился после этого момента, автоматический повтор
блокируется и пользователю отправляется `manual_required`, потому что нельзя
надёжно доказать, успела ли внешняя форма принять первый запрос.

Резюме не сохраняется в Actions cache. Runner загружает его через Telegram
`getFile` во временный каталог и удаляет вместе с runner. GitHub secrets и
содержимое резюме не выводятся в лог.

## Ручная проверка

Локально команду можно проверить без обработки очереди, пока режим выключен:

```powershell
tg-vacancy-bot process-applications-once
```

Ожидаемый вывод:

```text
Application queue is disabled.
```

Для настоящей проверки используйте `workflow_dispatch`, реальную тестовую
вакансию и тестовый профиль. Не выполняйте smoke-тест финальной отправки на
вакансию, на которую вы не собираетесь реально откликаться.
