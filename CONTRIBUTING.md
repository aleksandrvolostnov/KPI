# Правила внесения изменений (Contributing)

Проект находится в активной разработке. **Планируется** внедрение Git Flow и Conventional Commits, как описано ниже.

## Планируемая модель ветвления (Git Flow)

- `main` – стабильная версия, только релизные теги.
- `develop` – основная ветка разработки.
- `feature/*` – новые функции (создаются от `develop`, сливаются обратно).
- `release/*` – подготовка релизов (финальные правки).
- `hotfix/*` – срочные исправления багов в `main`.

## Планируемый формат коммитов (Conventional Commits)

Сообщение коммита должно иметь структуру:

```
<type>(<scope>): <subject>
```

### Типы (`type`)

- `feat` – новая функциональность
- `fix` – исправление ошибки
- `docs` – документация
- `style` – форматирование кода
- `refactor` – рефакторинг
- `perf` – улучшение производительности
- `test` – тесты
- `chore` – зависимости, CI/CD, конфиги
- `revert` – отмена изменений

### Примеры

```
feat(kanban): add WIP limit validation
fix(chat): fix file upload in group chat
docs(readme): update installation guide
chore(ci): add flake8 to GitHub Actions
```

Для breaking change используйте `!`:

```
feat(api)!: change response format for tasks
```

## Планируемый рабочий процесс

1. Создать ветку `feature/` от `develop`.
2. Делать коммиты с осмысленными типами.
3. Открыть Pull Request в `develop`.
4. После ревью и успешного CI – слить PR.
5. Для релиза создать ветку `release/vX.Y.Z` от `develop`, затем слить в `main` с тегом `vX.Y.Z`.
6. Срочные исправления – через `hotfix/` от `main`.

## Инструменты (в будущем)

Планируется добавить `commitlint` и pre-commit хуки для автоматической проверки формата коммитов.

---
