# 1С: Адаптер Kafka — Unit-Тесты

![Платформа](https://img.shields.io/badge/1С-8.3.21+-blue)
![EDT](https://img.shields.io/badge/EDT-2025.2+-blue)

Набор unit-тестов для проверки поведения [1С: Адаптер Kafka](https://github.com/ShadobaAI/kafka-adapter).

## Назначение

Репозиторий содержит модульные тесты и входит в локальный EDT workspace из четырёх проектов:

- `../base` — базовая конфигурация, собранная из `adapter/base` и `adapter/adapter`;
- `../examples` — расширение с тестовыми данными и примерами;
- `../unit` — это расширение с модульными тестами адаптера;
- `../yaxunit` — отдельный checkout ядра [YAxUnit](https://github.com/bia-technologies/yaxunit).

Скрипты `create_test_edt.py` и `create_test_edt.sh` пересобирают только `../base` из `adapter/base` и `adapter/adapter`. Расширения `examples`, `unit` и `yaxunit` остаются самостоятельными проектами EDT.

> Репозиторий предназначен только для разработки и проверки изменений адаптера. В промышленную эксплуатацию не поставляется.

## Инструменты

- [YAxUnit](https://bia-technologies.github.io/yaxunit/) — unit-тесты прикладной логики 1С.

## Лицензия

Проект распространяется под лицензией [Apache License 2.0](LICENSE).

**Разрешается:** использование, модификация и распространение — в том числе в коммерческих проектах — без ограничений.
