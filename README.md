# 1С: Адаптер Kafka — Тесты

Репозиторий содержит UI- и unit-тесты для проекта **1С: Адаптер Kafka**.

Тесты проверяют два уровня:

- UI-тесты проверяют поведение через интерфейс пользователя.
- Unit-тесты проверяют прикладную логику адаптера.

## Инструменты

- [Vanessa Automation](https://pr-mex.github.io/vanessa-automation/) - UI-тесты в каталоге `ui`.
- [YAXUNIT](https://bia-technologies.github.io/yaxunit/) - unit-тесты прикладной логики.

## Структура

- `ui` - сценарии UI-тестов Vanessa Automation.
- `unit` - локальный EDT-проект для разработки unit-тестов.
- `create_test_edt.py` - локальная сборка EDT-проекта из base, adapter, examples и YAXUNIT.
- `create_test_edt.sh` - быстрый запуск локальной сборки EDT-проекта.
