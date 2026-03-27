# Autopilot — Autonomous AI Programmer Platform

> Платформа управления автономными AI-программистами с ротацией аккаунтов, критик-лупом и Kanban-дашбордом.

## Обзор

Autopilot — standalone CLI-инструмент, построенный поверх [Ralph](https://github.com/iannuttall/ralph). Позволяет запускать несколько AI-агентов параллельно на разных проектах, с автоматической ротацией 20 аккаунтов OpenAI Plus, двухступенчатой проверкой качества (auto-gates + Codex-критик) и эскалационной цепочкой при застревании.

**Ключевая идея:** ты пишешь спеку (или брейнштормишь с intake-агентом), запускаешь autopilot, идёшь спать. Утром — готовые stories, прошедшие ревью критика.

## Архитектура

### Три слоя

```
Dashboard (Next.js)          <- визуальное управление
    | REST API + SSE
    v
Sidecar (Python/FastAPI)     <- мозги: ротация, критик, dispatcher
    | запускает и контролирует
    v
Ralph instances               <- движок лупа (по одному на story)
    | вызывает
    v
codex exec --full-auto        <- агент пишет код
```

### Поток данных

1. PRD создаётся (вручную, через `ralph prd`, или через intake-агента в дашборде)
2. Dispatcher назначает аккаунты на проект и запускает Ralph
3. Ralph крутит луп: story -> `codex exec --full-auto` -> коммит
4. Сайдкар запускает объективные гейты (build/test/lint)
5. Если гейты прошли — запускает Codex-критика на другом аккаунте
6. Критик APPROVED -> следующий story. NEEDS_WORK -> retry с фидбеком
7. Дашборд показывает всё в реальном времени через SSE
8. Если агент застрял -> эскалация по провайдерам -> уведомление человеку

## Account Manager

### Структура профилей

```
~/.autopilot/
  profiles/
    codex/
      acc1/
        auth.json
        config.toml
      acc2/
      ...acc14/
    claude/
      acc1/
        home/
      acc2/
    gemini/
      acc1/
        home/
      acc2/
  projects.yaml
  config.yaml
  state.db
```

### Настройка

```bash
autopilot login codex   # интерактивный сбор профилей
                        # "Залогинься в Codex в браузере, жду..."
                        # детектит ~/.codex/auth.json
                        # копирует в profiles/codex/accN/
                        # "Аккаунт N сохранён. Ещё один? (y/n)"
```

### Распределение аккаунтов

```yaml
# ~/.autopilot/config.yaml
accounts:
  total: 20
  allocation:
    intake: 1
    workers: 14
    critics: 5
```

### Ротация

- Round-robin внутри пула
- Rate limit -> cooldown с экспоненциальным бэкоффом
- Аккаунт освобождается -> возвращается в пул
- Переключение через `CODEX_HOME` env var (для Claude -- `HOME`)

## Loop Engine

### Ralph как ядро

Каждый story выполняется через `ralph build 1`. Сайдкар подставляет `CODEX_HOME` перед запуском. Ralph формирует промпт из кастомного шаблона и вызывает `codex exec --full-auto`.

### Контекст между итерациями (Ralph-стиль: файлы = память)

Каждая итерация — чистый `codex exec`. Контекст передаётся через файлы:

```
.ralph/
  progress.md          <- что сделано (Codex обновляет)
  guardrails.md        <- грабли, не повторять (Codex обновляет)
  critic-feedback.md   <- фидбек критика (сайдкар пишет)
  activity.log         <- лог итераций (Ralph пишет)
```

### Промпт-шаблон воркера

```markdown
## Контекст
Ты автономный программист. Работаешь над проектом в текущей папке.

## Перед началом
1. Прочитай .ralph/progress.md — что уже сделано
2. Прочитай .ralph/guardrails.md — ошибки, которые НЕ повторять
3. Прочитай PRD — найди story со статусом "open"

## Твоя задача
Реализуй ОДИН story. Не больше.

## Когда закончил
1. Убедись что билд проходит
2. Убедись что тесты зелёные
3. Обнови .ralph/progress.md — что сделал, какие решения принял
4. Если наступил на грабли — запиши в .ralph/guardrails.md
5. Закоммить ВСЁ одним коммитом с внятным сообщением
6. Отметь story как done
```

### Промпт-шаблон retry (после фидбека критика)

```markdown
## Контекст
Критик НЕ одобрил твою предыдущую работу.

## Перед началом
1. Прочитай .ralph/critic-feedback.md — что именно не так
2. Прочитай .ralph/guardrails.md

## Твоя задача
Исправь замечания критика по story #{id}. Ничего нового не добавляй.
```

## Critic Engine

### Двухступенчатая проверка

```
Коммит воркера
  |
  v
Ступень 1: Auto-gates (без агента, просто команды)
  build ok?  test ok?  lint ok?
  |
  все ок? --нет--> сразу retry с логом ошибки (не тратим аккаунт критика)
  |
  да
  |
  v
Ступень 2: Codex-критик (другой аккаунт)
  "Ревьюни этот diff"
  |
  APPROVED? --да--> следующий story
  |
  нет
  |
  v
critic-feedback.md -> retry воркера
```

### Auto-gates конфигурируются на проект

```yaml
gates:
  - name: build
    cmd: "npm run build"
    required: true
  - name: test
    cmd: "npm test"
    required: true
  - name: lint
    cmd: "npm run lint"
    required: false   # warning, не блокирует
```

### Промпт критика

```markdown
Ты код-ревьюер. Твоя задача — оценить последний коммит.

## Задание из PRD
{story.title}: {story.description}

## Diff
{git diff HEAD~1}

## Проверь
1. Код решает задачу из story?
2. Нет очевидных багов?
3. Нет хардкода секретов?
4. Код читаемый?

## Формат ответа
Если всё ок:
APPROVED

Если есть проблемы:
NEEDS_WORK
- Проблема 1: ...
- Проблема 2: ...
```

### Детекция застревания (Stuck Detector)

| Сигнал | Что значит |
|--------|-----------|
| Критик 3 раза подряд с одним и тем же замечанием | Агент не понимает фидбек |
| `git diff` между итерациями пустой | Агент ничего не делает |
| Одна и та же ошибка билда 3 раза | Агент не может починить |
| Таймаут (`codex exec` не завершился за 30 мин, настраивается) | Агент завис |

## Эскалационная цепочка

Когда агент застрял — не сразу человеку. Сначала пробуем других.

**3 попытки на каждом провайдере перед переходом к следующему.**

```
Codex застрял (3 попытки)
  -> другой Codex-аккаунт (свежий контекст, тот же промпт)
    -> Claude (другой провайдер, 3 попытки)
      -> Gemini (третий провайдер, 3 попытки)
        -> ВСЕ не справились -> уведомление человеку (Telegram)
```

### Обогащённый контекст при смене провайдера

```markdown
## Контекст
Предыдущие агенты не справились с этой задачей.

## Что уже пробовали
1. Codex (3 итерации): {краткое описание проблемы}
2. Claude (3 итерации): {краткое описание проблемы}

## Фидбек критика
{последний critic-feedback.md}

## Guardrails
{guardrails.md}

## Твоя задача
Реализуй story #{id} другим подходом.
```

### Параллельная работа во время эскалации

Story #3 застрял -> эскалация. Story #4 не зависит от #3 -> другой воркер берёт его. Story #5 зависит от #3 -> ждёт. Dispatcher читает зависимости из PRD.

## Dispatcher (мульти-проект)

### Конфиг проектов

```yaml
# ~/.autopilot/projects.yaml
projects:
  - name: "uptime-monitor"
    path: "/Users/martin/uptime-monitor"
    prd: ".agents/tasks/prd-uptime.json"
    priority: high
    gates:
      - cmd: "npm run build"
      - cmd: "npm test"
    providers: [codex, claude]

  - name: "telegram-bot"
    path: "/Users/martin/tg-bot"
    prd: ".agents/tasks/prd-bot.json"
    priority: normal
    gates:
      - cmd: "python -m pytest"
      - cmd: "ruff check ."
    providers: [codex]
```

### Приоритеты

| Приоритет | Воркеров | Логика |
|-----------|----------|--------|
| `high` | 4-5 | Первый в очереди на свободные аккаунты |
| `normal` | 3 | Стандартное распределение |
| `low` | 1-2 | Работает на остатках |

### Динамическая балансировка

- Проект закончился -> его аккаунты уходят в общий пул
- Проекту нужно больше ресурсов -> dispatcher перекидывает свободные
- Аккаунт на кулдауне -> может временно помочь другому проекту

### Параллельные stories в одном проекте (git worktrees)

Два воркера на одном проекте работают в разных worktrees:

```
/Users/martin/uptime-monitor/           <- основная ветка
/Users/martin/uptime-monitor-story-3/   <- worktree для story #3
```

После завершения — merge в основную ветку.

## Dashboard

### Технология

Next.js + Tailwind + shadcn/ui. Отдельный проект внутри autopilot/, stateless — всё читает из сайдкар-API.

### Экраны

**Главный — Kanban по проектам:** карточки stories с агентами, статусами, временем. Live updates через SSE.

**Детали story:** timeline итераций, фидбек критика, действия (пауза, переназначение, пропуск, добавить указание агенту).

**"Добавить указание":** текст дописывается в `guardrails.md`, следующая итерация агент прочитает.

**Здоровье системы:** аккаунты active/cooldown, проекты, stories, аптайм.

### Intake-чат

Боковая панель или отдельная страница. Intake-агент (Codex на выделенном аккаунте) задаёт уточняющие вопросы, генерирует PRD, показывает тебе. Кнопка "Запустить" -> stories уходят в работу.

## Фазы реализации

### Фаза 1: CLI-ядро (MVP)

Один проект, Ralph-луп с ротацией аккаунтов и критиком. CLI only.

```bash
autopilot login codex
autopilot init ~/my-project
autopilot run ~/my-project
autopilot status
```

Компоненты: `autopilot login`, `autopilot run`, Account Manager, Critic Runner, Stuck Detector, `autopilot status` (терминал).

**Результат:** запускаешь перед сном, утром stories сделаны.

### Фаза 2: Мульти-проект + эскалация

- `projects.yaml`, Dispatcher, приоритеты
- Git worktrees для параллельных stories
- Эскалационная цепочка: Codex -> Claude -> Gemini -> человек
- Telegram-нотификации
- Мульти-провайдер: `autopilot login claude`, `autopilot login gemini`

### Фаза 3: Dashboard

- Next.js Kanban-доска
- SSE live updates
- Действия из UI: пауза, переназначение, пропуск, указания
- История итераций и фидбека

### Фаза 4: Intake-агент

- Чат в дашборде для создания проектов
- Уточняющие вопросы, автогенерация PRD
- Кнопка "Запустить" из чата

## Структура проекта

```
autopilot/
  cli/                    # CLI-команды (Typer)
    login.py
    run.py
    status.py
    init.py
  core/                   # Бизнес-логика
    account_manager.py    # Профили, ротация, cooldown
    loop_runner.py        # Запуск Ralph + env подстановка
    critic.py             # Auto-gates + Codex-критик
    stuck_detector.py     # Детекция застревания
    dispatcher.py         # Мульти-проект (фаза 2)
    escalation.py         # Цепочка провайдеров (фаза 2)
    notifier.py           # Telegram (фаза 2)
  api/                    # FastAPI для дашборда (фаза 3)
    main.py
    routes.py
    sse.py
  dashboard/              # Next.js (фаза 3)
  templates/              # Кастомные Ralph-шаблоны
    worker-prompt.md
    retry-prompt.md
    critic-prompt.md
  pyproject.toml
  README.md
```

## Где что хранится

| Что | Где | Кто управляет |
|-----|-----|---------------|
| Progress, guardrails, логи | `.ralph/` в каждом проекте | Ralph + Codex |
| Профили аккаунтов | `~/.autopilot/profiles/` | Сайдкар |
| Проекты, назначения, метрики | `~/.autopilot/state.db` (SQLite) | Сайдкар |
| Конфиг проектов | `~/.autopilot/projects.yaml` | Пользователь |
| PRD | `.agents/tasks/` в каждом проекте | Ralph / Intake-агент |
| Critic feedback | `.ralph/critic-feedback.md` | Сайдкар |
