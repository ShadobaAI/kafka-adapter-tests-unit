# Базовый EDT-проект для unit-тестов

Этот каталог содержит сгенерированный EDT-проект тестовой конфигурации.
Он создается скриптом [`create_test_edt.sh`](../../create_test_edt.sh) и используется как рабочая база для unit-тестов.

В основе проекта лежит [`kafka-adapter-base`](https://github.com/ShadobaAI/kafka-adapter-base).
Поверх него добавляются объекты из [`kafka-adapter`](https://github.com/ShadobaAI/kafka-adapter), [`kafka-adapter-examples`](https://github.com/ShadobaAI/kafka-adapter-examples) и [`YAXUNIT`](https://github.com/bia-technologies/yaxunit).

Служебные каталоги `.settings`, `DT-INF` и `src` являются частью стандартной структуры EDT-проекта.
