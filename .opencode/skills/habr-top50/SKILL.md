---
name: habr-top50
description: Роутер по ТОП-50 скиллам для ИИ-агентов. Загрузи меня на старте сессии и подбери внешний скилл под задачу пользователя.
---

# Роутер скиллов (ТОП-50, Habr 1078034)

Источник: https://habr.com/ru/articles/1078034/ — подборка 50 популярных скиллов
для ИИ-агентов. Владелец явно разрешил использовать этот материал, но это НЕ
отменяет проверку: команды установки (`npx skills add ...`) скачивают и
выполняют сторонний код — НЕ запускай их без явного согласия пользователя и
без ревью репозитория (лицензия, мейнтейненс, supply-chain риск).

## Как меня использовать

1. На старте сессии загрузи этот файл и держи таблицу в уме.
2. Под задачу пользователя выбери 1–3 подходящих скилла из таблицы.
3. Предложи пользователю установить выбранное (покажи команду, сам не запускай).
4. После установки работай по инструкции установленного скилла.

## Быстрый роутинг по типу задачи

- Не знаешь какой скилл нужен → `find-skills`
- Сырая идея, проверка замысла → `grill-me`, `brainstorming`
- План vs реальность (код/доки) → `grill-with-docs`
- Разбить большую работу → `wayfinder`, `to-tickets`
- Идея → ТЗ → задачи → `to-spec`, `to-tickets`
- План разработки перед кодом → `writing-plans`
- Выполнить готовый план → `implement`, `executing-plans`
- Изучить кодбазу перед задачей → `research`
- Архитектура/структура → `improve-codebase-architecture`, `codebase-design`, `domain-modeling`
- Баг вернулся/непонятен → `diagnosing-bugs`, `systematic-debugging`
- Ревью перед мержем → `code-review`
- Git-конфликт → `resolving-merge-conflicts`
- Важная функция, регрессии → `tdd`
- Довести задачу до конца → `verification-before-completion`
- Раздать подзадачи субагентам → `subagent-driven-development`
- Сохранить контекст между чатами → `handoff`
- Разобрать входящую ошибку → `triage`
- Браузерные действия → `agent-browser`, `browser-use`
- Новый MCP-сервер → `mcp-builder`
- Новый скилл → `skill-creator`
- Документы/таблицы → `pptx`, `pdf`, `docx`, `xlsx`, `doc-coauthoring`, `theme-factory`
- Дизайн → `frontend-design`, `web-design-guidelines`, `design-taste-frontend`, `impeccable`, `ui-ux-pro-max`, `brandkit`, `image-to-code`, `shadcn`
- Тексты/SEO → `copywriting`, `seo-audit`
- Проверка веба → `webapp-testing`
- База Supabase → `supabase-postgres-best-practices`
- Калькуляторы/дашборды → `web-artifacts-builder`
- Лишний код/усложнения → `ponytail`
- Обучение → `teach`

## Полный реестр

| # | Скилл | Что делает | Установка |
|---|-------|-----------|-----------|
| 1 | `find-skills` | Ищет и устанавливает навык под задачу | `npx skills add https://github.com/vercel-labs/skills -skill find-skills` |
| 2 | `grill-me` | Вопросы, слабые места идеи | `npx skills add https://github.com/mattpocock/skills -skill grill-me` |
| 3 | `grill-with-docs` | Сверяет план с кодом и доками | `npx skills add https://github.com/mattpocock/skills -skill grill-with-docs` |
| 4 | `improve-codebase-architecture` | Архпроблемы, упрощение кода | `npx skills add https://github.com/mattpocock/skills -skill improve-codebase-architecture` |
| 5 | `frontend-design` | Интерфейс + код страницы | `npx skills add https://github.com/anthropics/skills -skill frontend-design` |
| 6 | `tdd` | Сначала тест, потом функция | `npx skills add https://github.com/mattpocock/skills -skill tdd` |
| 7 | `agent-browser` | Браузер: клики, формы, сбор данных | `npx skills add https://github.com/vercel-labs/agent-browser -skill agent-browser` |
| 8 | `handoff` | Сохраняет контекст для следующего агента | `npx skills add https://github.com/mattpocock/skills -skill handoff` |
| 9 | `triage` | Разбор ошибки, следующий шаг | `npx skills add https://github.com/mattpocock/skills -skill triage` |
| 10 | `prototype` | Быстрый прототип идеи | `npx skills add https://github.com/mattpocock/skills -skill prototype` |
| 11 | `vercel-react-best-practices` | Аудит React/Next.js по правилам Vercel | `npx skills add https://github.com/vercel-labs/agent-skills -skill vercel-react-best-practices` |
| 12 | `web-design-guidelines` | UX/мобилка/доступность сайта | `npx skills add https://github.com/vercel-labs/agent-skills -skill web-design-guidelines` |
| 13 | `teach` | Объясняет тему по шагам | `npx skills add https://github.com/mattpocock/skills -skill teach` |
| 14 | `domain-modeling` | Объекты продукта, связи, правила | `npx skills add https://github.com/mattpocock/skills -skill domain-modeling` |
| 15 | `codebase-design` | Делит кодбазу на понятные части | `npx skills add https://github.com/mattpocock/skills -skill codebase-design` |
| 16 | `diagnosing-bugs` | Причина ошибки через гипотезы | `npx skills add https://github.com/mattpocock/skills -skill diagnosing-bugs` |
| 17 | `implement` | Выполняет готовый план | `npx skills add https://github.com/mattpocock/skills -skill implement` |
| 18 | `code-review` | Ошибки и риски в диффе | `npx skills add https://github.com/mattpocock/skills -skill code-review` |
| 19 | `wayfinder` | Делит большой проект на задачи | `npx skills add https://github.com/mattpocock/skills -skill wayfinder` |
| 20 | `design-taste-frontend` | Цвета/шрифты/отступы/композиция | `npx skills add https://github.com/leonxlnx/taste-skill -skill design-taste-frontend` |
| 21 | `research` | Изучает код и доки перед решением | `npx skills add https://github.com/mattpocock/skills -skill research` |
| 22 | `to-spec` | Идея → точное ТЗ | `npx skills add https://github.com/mattpocock/skills -skill to-spec` |
| 23 | `to-tickets` | ТЗ → задачи для команды | `npx skills add https://github.com/mattpocock/skills -skill to-tickets` |
| 24 | `resolving-merge-conflicts` | Решение Git-конфликтов | `npx skills add https://github.com/mattpocock/skills -skill resolving-merge-conflicts` |
| 25 | `supabase-postgres-best-practices` | Запросы и права в Supabase | `npx skills add https://github.com/supabase/agent-skills -skill supabase-postgres-best-practices` |
| 26 | `skill-creator` | Создает новый скилл | `npx skills add https://github.com/anthropics/skills -skill skill-creator` |
| 27 | `brainstorming` | Идея → рабочая концепция | `npx skills add https://github.com/obra/superpowers -skill brainstorming` |
| 28 | `ui-ux-pro-max` | Стиль, цвета, шрифты, UI-кит | `npx skills add https://github.com/nextlevelbuilder/ui-ux-pro-max-skill -skill ui-ux-pro-max` |
| 29 | `brandkit` | Единые правила бренда | `npx skills add https://github.com/leonxlnx/taste-skill -skill brandkit` |
| 30 | `impeccable` | Точечные визуальные правки | `npx skills add https://github.com/pbakaus/impeccable -skill impeccable` |
| 31 | `image-to-code` | Скриншот/макет → код | `npx skills add https://github.com/leonxlnx/taste-skill -skill image-to-code` |
| 32 | `systematic-debugging` | Сбой по плану, без гаданий | `npx skills add https://github.com/obra/superpowers -skill systematic-debugging` |
| 33 | `writing-plans` | Пошаговый план с файлами | `npx skills add https://github.com/obra/superpowers -skill writing-plans` |
| 34 | `pptx` | Презентации PowerPoint | `npx skills add https://github.com/anthropics/skills -skill pptx` |
| 35 | `executing-plans` | План частями с проверкой | `npx skills add https://github.com/obra/superpowers -skill executing-plans` |
| 36 | `seo-audit` | Технические и контентные ошибки SEO | `npx skills add https://github.com/coreyhaines31/marketingskills -skill seo-audit` |
| 37 | `verification-before-completion` | Проверка перед «готово» | `npx skills add https://github.com/obra/superpowers -skill verification-before-completion` |
| 38 | `subagent-driven-development` | Подзадачи субагентам | `npx skills add https://github.com/obra/superpowers -skill subagent-driven-development` |
| 39 | `copywriting` | Тексты для сайтов/писем/рекламы | `npx skills add https://github.com/coreyhaines31/marketingskills -skill copywriting` |
| 40 | `pdf` | Чтение/создание/проверка PDF | `npx skills add https://github.com/anthropics/skills -skill pdf` |
| 41 | `docx` | Документы Word | `npx skills add https://github.com/anthropics/skills -skill docx` |
| 42 | `xlsx` | Excel: данные/формулы/диаграммы | `npx skills add https://github.com/anthropics/skills -skill xlsx` |
| 43 | `webapp-testing` | Сценарии сайта, скриншоты | `npx skills add https://github.com/anthropics/skills -skill webapp-testing` |
| 44 | `mcp-builder` | Создает MCP-сервер | `npx skills add https://github.com/anthropics/skills -skill mcp-builder` |
| 45 | `web-artifacts-builder` | Калькуляторы/дашборды/формы | `npx skills add https://github.com/anthropics/skills -skill web-artifacts-builder` |
| 46 | `browser-use` | Управление сайтами через браузер | `npx skills add https://github.com/browser-use/browser-use -skill browser-use` |
| 47 | `theme-factory` | Одна тема на документы/слайды/сайты | `npx skills add https://github.com/anthropics/skills -skill theme-factory` |
| 48 | `doc-coauthoring` | Структура документа, улучшение черновика | `npx skills add https://github.com/anthropics/skills -skill doc-coauthoring` |
| 49 | `ponytail` | Режет лишний код и усложнения | `npx skills add https://github.com/dietrichgebert/ponytail -skill ponytail` |
| 50 | `shadcn` | Формы/меню/таблицы из shadcn/ui | `npx skills add https://github.com/shadcn-ui/ui -skill shadcn` |

Примечание: позиции 46–50 восстановлены из хвоста статьи; перед
использованием сверь команду установки с таблицей/репозиторием из статьи.
