# План единой фильтрации вакансий для Telegram-канала

## Цель

Свести фильтрацию вакансий к одной понятной политике: в канал попадают в
первую очередь реальные вакансии по разработке, а роли без непосредственного
кодинга, обучение, продажи, поддержку и эксплуатацию не пропускаем.

Этот файл является рабочей спецификацией. После согласования всех правил и
реализации его ключевые положения нужно перенести в `docs/architecture.md`.

## Уже согласованная матрица категорий

| Категория | Политика |
| --- | --- |
| Backend | Публиковать все уровни и стеки, если это разработка |
| Frontend | Публиковать все уровни и стеки, если это разработка |
| Fullstack | Публиковать все уровни и стеки, если это разработка |
| Mobile: iOS, Android, Flutter, React Native | Публиковать |
| GameDev: Unity, Unreal, gameplay, game tools, game backend | Публиковать при явной разработке |
| Embedded, firmware, IoT, robotics | Не публиковать |
| ML/LLM/AI Engineer | Публиковать |
| Data Analyst, BI и обычные data-роли | Не публиковать |
| DevOps, SRE, Cloud, Platform, Infrastructure | Не публиковать |
| QA | Только Automation QA и автоматизация; manual QA и SDET исключить |
| Security | Только DevSecOps; AppSec и остальные security-роли исключить |
| Database, DBA, SQL administration | Не публиковать |
| Blockchain/Web3/Crypto | Публиковать при явной разработке |
| 1C, SAP, ERP, CRM, Salesforce и другие enterprise-платформы | Только явные developer/programmer-роли |
| Software Architect, Technical Lead | Публиковать |
| Solution Architect, Engineering Manager | Не публиковать |
| Network, SysAdmin, Linux/Unix Administrator, IT Support | Не публиковать |
| UI/UX | Оставить только UI/UX-роли |
| Product Designer, Graphic Designer, Web Designer и прочий дизайн | Не публиковать |
| Technical PM, технический Product/Project Manager | Не публиковать |
| Обычный Product Manager, Project Manager, Business Analyst, Product Owner, Scrum Master | Не публиковать |
| Technical Writer, Implementation Engineer, Solutions Consultant, Technical Support | Не публиковать |

Публикуются все уровни, включая internships, trainee и стажировки. Разрешены
любые форматы занятости: freelance, contract, part-time и unpaid. Фильтр не
ограничивает вакансии по стране, географии, часовому поясу, формату office/
hybrid/remote, зарплате, языку, гражданству или разрешению на работу.

## Проблемы текущей реализации

- `tg_vacancy_bot/sources/filters.py` проверяет объединённый текст названия и
  описания. Поэтому слово вроде `developer` в описании вакансии Product Manager
  может дать ложное совпадение.
- Текущий allowlist смешивает разработку с `designer`, `design`, AI и LLM.
- Фильтр построен на подстроках и не разделяет роль, стек, обязанности и
  рекламный текст.
- Один и тот же общий фильтр используется для внешних источников и для
  входящих/пересланных Telegram-сообщений. Это правильно как архитектурная
  идея, но политика должна быть единой и тестируемой.
- Тесты сейчас закрепляют старое поведение: Product Designer и LLM проходят,
  QA и DevOps не проходят. Их нужно заменить на утверждённую матрицу.

## План изменений

### 1. Единый классификатор роли

- Заменить широкий набор положительных подстрок на структурированную политику
  категорий и явных role patterns.
- Приоритетно анализировать название вакансии и роль, а описание использовать
  для подтверждения обязанностей и выявления запрещённого контекста.
- Нормализовать регистр, дефисы, пробелы, slash-варианты и русские/английские
  названия ролей.
- Не считать упоминание технологии, продукта или слова `developer` в тексте
  вакансии достаточным доказательством нужной роли.
- Разделить решения как минимум на `allowed`, `rejected` и диагностическую
  причину отказа, чтобы можно было понять, почему вакансия не опубликована.

### 2. Правила исключений

- Исключать обучение, курсы, bootcamp, стажёрские программы без реальной
  вакансии, продажи, marketing, recruitment, HR, support, customer success,
  административные и офисные роли.
- Исключать роли, где разработка указана только как часть описания компании,
  продукта или команды.
- Technical PM, технические Product/Project Manager и Engineering Manager не
  пропускать, даже если в описании есть технический контекст.
- Technical Writer, Implementation Engineer, Solutions Consultant и Technical
  Support не пропускать, даже если в описании есть кодинг, скрипты,
  интеграции или разработка.
- Для enterprise-платформ разрешать только названия и обязанности уровня
  developer/programmer; консультирование, внедрение и сопровождение отдельно
  не пропускать.

### 3. Одинаковое применение во всех путях публикации

Проверить и покрыть одной политикой:

- source adapters через `filter_it_vacancies`;
- входящие и пересланные сообщения через `intake.py`;
- режим `FORWARDED_MODE=copy`, чтобы он не обходил allowlist;
- `poll-once` и фоновый source polling;
- `preview-message` и `preview-sources`, чтобы предпросмотр совпадал с реальной
  публикацией.

### 4. Конфигурация и наблюдаемость

- Не выносить каждую категорию в отдельную env-переменную без необходимости:
  базовая политика должна быть кодом и тестами, а не набором разрозненных
  строк в `.env`.
- Добавить безопасную диагностическую причину фильтрации в preview/logging,
  не публикуя лишний исходный текст и не раскрывая секреты.
- При необходимости добавить dry-run отчёт по источнику: получено, прошло
  фильтр, отклонено по категории, отклонено по исключению.

## Тестовая стратегия

Добавить параметризованные тесты на положительные и отрицательные примеры:

- backend/frontend/fullstack, mobile и GameDev;
- ML/LLM против Data Analyst/BI;
- Automation QA против Manual QA;
- DevSecOps против AppSec, SOC/GRC и общего security;
- blockchain developer против Web3 marketing/operations;
- enterprise developer против consultant/implementation/support;
- UI/UX против Graphic/Web Designer;
- Software Architect/Technical Lead против Solution Architect и Engineering
  Manager;
- Technical PM, технический Product/Project Manager и обычные PM-роли как
  отрицательные сценарии;
- Technical Writer/Implementation Engineer/Solutions Consultant/Technical
  Support с кодингом и без кодинга как отрицательные сценарии;
- DevOps, SRE, Cloud, DBA, SysAdmin, Network и Support как отрицательные
  сценарии;
- упоминания `developer`, стека или software только в описании нерелевантной
  роли;
- русские, английские, дефисные и slash-варианты названий;
- курсы, bootcamp, вакансии без явной роли и вакансии с запрещённым контекстом.

Отдельно подтвердить, что `filter_it_vacancies`, intake и copy mode принимают
и отклоняют один и тот же набор примеров.

## Критерии готовности

- В канале публикуются только категории из согласованной матрицы.
- Упоминание разработки или технологии в описании не протаскивает
  нерелевантную должность.
- Manual QA, SDET, DevOps/SRE/Cloud, embedded/firmware/IoT/robotics, DBA,
  SysAdmin/Network/Support, обычные и технические PM, Product/Project Manager,
  Business Analyst, общий дизайн, AppSec, Solution Architect, Engineering
  Manager, Technical Writer, Implementation Engineer, Solutions Consultant,
  Technical Support и Data Analyst не публикуются.
- UI/UX, Software Architect, Technical Lead, Automation QA и DevSecOps
  обрабатываются по согласованным специальным правилам.
- Предпросмотр и реальные source/Telegram-пути используют одинаковую политику.
- Для каждого решения есть тест, а причина фильтрации доступна для безопасной
  диагностики.
- README и `docs/architecture.md` обновлены после стабилизации поведения.
- После проверки документация и код оформлены отдельным логическим коммитом и
  отправлены в GitHub согласно `docs/git-workflow.md`.

## Итоговые продуктовые ограничения

- Публиковать internships, trainee и стажировки, если сама роль относится к
  разрешённой категории.
- Публиковать freelance, contract, part-time и unpaid-вакансии.
- Принимать вакансии со всего мира.
- Не фильтровать по формату работы: office, hybrid и remote разрешены.
- Не фильтровать по зарплате, включая отсутствие зарплаты.
- Не фильтровать по языку, гражданству или разрешению на работу.
- Публиковать Software Architect и Technical Lead; не публиковать технических
  менеджеров и руководителей вроде Technical PM, технического Product/Project
  Manager и Engineering Manager.

Дополнительных продуктовых вопросов перед реализацией фильтра не осталось.
