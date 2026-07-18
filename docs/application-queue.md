# Очередь откликов без постоянно работающего сервера

## Что делает режим

Когда локальный бот выключен, Telegram хранит нажатие `Откликнуться` как
необработанный callback. Плановый GitHub Actions runner раз в 15 минут запускает
`tg-vacancy-bot process-applications-once`, забирает накопленные callback и сообщения,
проверяет Telegram ID оператора, отправляет личное сообщение о подготовленном
отклике, временно скачивает резюме из Telegram, запускает Playwright и
отправляет фактический результат в личный чат.

GitHub Actions runner является одноразовым: после выполнения он удаляется.
Обычная задержка составляет от 0 до 15 минут, но GitHub может задержать
scheduled workflow. Telegram хранит необработанные updates не более 24 часов.

## Граница автоматической отправки

`Отклик отправлен` показывается только после доказанного состояния успеха.
Автоматическая финальная отправка разрешена только когда одновременно выполнены
все условия:

- исходная вакансия относится к `arbeitnow.com`;
- на исходной странице присутствует ровно одна inline-форма `#form_job_application`;
- форма содержит проверенные поля `first_name`, `last_name`, `email`,
  `cv_or_resume`, согласие `terms` и кнопку `button_send_application`;
- нет login, CAPTCHA или 2FA;
- после клика форма исчезла и появился видимый `div_success_message` с известным
  текстом успеха.

Ссылка `company portal` может перенаправлять на JOIN, но адаптер её не открывает:
он работает с inline-формой на исходной странице вакансии. Если inline-формы нет,
её контракт изменился или обнаружены login/CAPTCHA/2FA, обработка завершается
статусом `manual_required`. Это не считается отправленным откликом.

## Первичная настройка

1. В GitHub откройте `Settings -> Secrets and variables -> Actions`.
2. Добавьте обязательные repository secrets:

   - `TELEGRAM_BOT_TOKEN`;
   - `TARGET_CHAT_ID`;
   - `OPERATOR_USER_IDS` — ровно один Telegram ID;
   - `APPLICATION_QUEUE_ENABLED=true`;
   - `APPLICATION_AUTO_SUBMIT=true`;
   - `APPLICATION_ALLOWED_DOMAINS=arbeitnow.com`;
   - `APPLICATION_QUEUE_PROFILE_FULL_NAME`;
   - `APPLICATION_QUEUE_PROFILE_EMAIL`.

3. При необходимости добавьте:

   - `APPLICATION_QUEUE_PROFILE_PHONE`;
   - `APPLICATION_QUEUE_PROFILE_PERSONAL_URL`;
   - `APPLICATION_QUEUE_PROFILE_COVER_LETTER`.

4. Остановите локальный бот. Нельзя одновременно использовать long polling и
   пакетный `getUpdates` для одного Telegram bot token: один процесс может забрать
   update раньше другого.
5. В личном чате отправьте боту резюме как PDF/DOCX-документ с подписью
   `/queue_resume`. Команда должна быть подписью прикреплённого документа, а не
   отдельным сообщением.
6. Дождитесь ближайшего запуска Actions и личного подтверждения, что резюме
   сохранено. При замене резюме повторите шаг 5 — GitHub secrets менять не нужно.
7. В GitHub Actions вручную запустите `Scheduled vacancy source polling` и
   проверьте шаги `Diagnose application queue without consuming updates` и
   `Process queued application clicks`.

`APPLICATION_QUEUE_RESUME_FILE_ID` и `APPLICATION_QUEUE_RESUME_FILE_NAME`
поддерживаются как необязательный резервный способ первоначальной настройки.
Для обычного использования они не нужны.

## Использование

1. Один раз отправьте или обновите резюме командой-подписью `/queue_resume`.
2. Нажмите `Откликнуться` под опубликованной карточкой.
3. Дождитесь следующего запуска GitHub Actions.
4. Получите личное сообщение `Отклик подготовлен`, когда runner заберёт callback.
5. Получите постоянное личное сообщение с фактическим результатом.

Короткий Telegram-индикатор после нажатия может завершиться таймаутом до запуска
Actions. Это ожидаемо: мгновенный `answerCallbackQuery` без webhook невозможен.
Сам callback остаётся в очереди Telegram. Если callback ещё можно подтвердить,
runner также покажет короткое нижнее уведомление `Отклик подготовлен`; если
Telegram уже считает callback слишком старым, личное сообщение всё равно будет
отправлено.

## Состояние и защита от дублей

SQLite из `data/vacancies.sqlite3` восстанавливается через GitHub Actions cache и
содержит опубликованные vacancy fingerprints и статусы откликов. Повторное
нажатие не создаёт вторую заявку. Перед финальным кликом статус меняется на
`submitting`. Если runner остановился после этого момента, автоматический повтор
блокируется и пользователю отправляется `manual_required`, потому что нельзя
надёжно доказать, успела ли внешняя форма принять первый запрос.

Actions cache сохраняет только Telegram `file_id` и исходное имя резюме, но не
содержимое документа. Runner загружает файл через Telegram `getFile` во временный
каталог и удаляет вместе с runner. GitHub secrets и содержимое резюме не выводятся
в лог.

## Ручная проверка

Локально команду можно проверить без обработки очереди, пока режим выключен:

```powershell
tg-vacancy-bot process-applications-once
```

Ожидаемый вывод:

```text
Application queue is disabled.
```

Безопасная диагностика настроенной очереди не забирает Telegram updates:

```powershell
tg-vacancy-bot diagnose-application-queue
```

Она показывает публичную идентичность бота и канала, число ожидающих updates,
наличие резюме в очереди и только агрегированные счётчики SQLite. Токен, данные
профиля и Telegram `file_id` в вывод не попадают. Если scheduled runner постоянно
показывает `Pending Telegram updates: 0` после кликов и отправки `/queue_resume`,
проверьте, не использует ли тот же bot token другой процесс `run`, `run-web`,
systemd, Docker или другой workflow.

Для настоящей проверки используйте `workflow_dispatch`, реальную тестовую
вакансию и тестовый профиль. Не выполняйте smoke-тест финальной отправки на
вакансию, на которую вы не собираетесь реально откликаться.
