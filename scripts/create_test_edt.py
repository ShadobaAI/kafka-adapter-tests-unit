#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создание тестового EDT-проекта из base + adapter + examples + YAXUNIT.

В отличие от create_test_cf.py этот скрипт работает не с XML-выгрузкой
Конфигуратора 1С, а с исходниками EDT-проекта. CFE-проекты сначала приводятся
к виду CF-проекта, после чего их metadata сливается с base.
"""
from __future__ import annotations

import argparse
import copy
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree


EDT_PROJECT_ENTRIES = (".project", ".settings", "DT-INF", "src")
CLEAN_OUTPUT_ENTRIES = (*EDT_PROJECT_ENTRIES, ".cache")
CONFIGURATION_MDO = Path("src") / "Configuration" / "Configuration.mdo"
UPDATE_DB_MODULE_NAME = "ОбновлениеИнформационнойБазыKafka"
UPDATE_DB_MODULE_PATH = Path("src") / "CommonModules" / UPDATE_DB_MODULE_NAME
UPDATE_DB_MODULE_SOURCE = UPDATE_DB_MODULE_PATH / "Module.bsl"
UPDATE_HANDLERS_PROCEDURE = "ПриДобавленииОбработчиковОбновления"
EXAMPLES_UPDATE_HANDLERS_PROCEDURE = f"кфк_т_{UPDATE_HANDLERS_PROCEDURE}"
OVERRIDABLE_COMMANDS_MODULE_NAME = "ПодключаемыеКомандыПереопределяемый"
OVERRIDABLE_COMMANDS_MODULE_PATH = Path("src") / "CommonModules" / OVERRIDABLE_COMMANDS_MODULE_NAME
OVERRIDABLE_COMMANDS_MODULE_SOURCE = OVERRIDABLE_COMMANDS_MODULE_PATH / "Module.bsl"
OVERRIDABLE_COMMANDS_PROCEDURE = "ПриОпределенииКомандПодключенныхКОбъекту"
EXAMPLES_OVERRIDABLE_COMMANDS_PROCEDURE = f"кфк_т_{OVERRIDABLE_COMMANDS_PROCEDURE}"
APPLICATION_MODULE_PATHS = (
    Path("src") / "Configuration" / "ManagedApplicationModule.bsl",
    Path("src") / "Configuration" / "OrdinaryApplicationModule.bsl",
)

EXTENSION_TAGS = (
    "objectBelonging",
    "extension",
    "keepMappingToExtendedConfigurationObjectsByIDs",
    "namePrefix",
    "configurationExtensionPurpose",
    "configurationExtensionCompatibilityMode",
)

# В EDT Configuration.mdo содержит ссылки на объекты верхнего уровня.
# Служебные свойства конфигурации, язык и параметры расширения не переносим.
MERGED_CONFIGURATION_TAGS = frozenset(
    {
        "subsystems",
        "commonPictures",
        "roles",
        "commonTemplates",
        "commonModules",
        "eventSubscriptions",
        "scheduledJobs",
        "functionalOptions",
        "definedTypes",
        "constants",
        "commonForms",
        "catalogs",
        "documents",
        "enums",
        "dataProcessors",
        "informationRegisters",
        "accumulationRegisters",
        "xDTOPackages",
        "reports",
        "commandGroups",
        "commonAttributes",
        "commonCommands",
        "exchangePlans",
        "sessionParameters",
        "settingsStorages",
        "styleItems",
        "webServices",
    }
)


class ScriptError(RuntimeError):
    pass


@dataclass(frozen=True)
class Options:
    output_dir: Path
    base_project: Path
    adapter_project: Path
    examples_project: Path
    yaxunit_project: Path


@dataclass(frozen=True)
class MergeStats:
    copied_files: int
    configuration_nodes: int
    update_handler_lines: int = 0


@dataclass(frozen=True)
class BslMethod:
    name: str
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class ApplicationModuleMergeStats:
    copied_modules: int
    variable_declarations: int
    methods: int


class RussianArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", help="показать эту справку.")

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "Использование:").replace("options:", "Параметры:")

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "Использование:")

    def error(self, message: str) -> None:
        message = message.replace("unrecognized arguments:", "неизвестные параметры:")
        message = message.replace("expected one argument", "ожидалось одно значение")
        message = message.replace("the following arguments are required:", "обязательные параметры:")
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: ошибка: {message}\n")


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = RussianArgumentParser(
        description=(
            "Создает EDT-проект тестовой конфигурации из base, adapter, examples и YAXUNIT. "
            "CFE-проекты предварительно конвертируются в формат CF-проекта."
        )
    )
    parser.add_argument("-o", "--output", dest="output_dir", type=Path, required=True, help="каталог результата.")
    parser.add_argument("-b", "--base", dest="base_project", type=Path, required=True, help="EDT-проект base (CF).")
    parser.add_argument(
        "-a",
        "--adapter",
        dest="adapter_project",
        type=Path,
        required=True,
        help="EDT-проект adapter (CFE).",
    )
    parser.add_argument(
        "-e",
        "--examples",
        dest="examples_project",
        type=Path,
        required=True,
        help="EDT-проект examples (CFE).",
    )
    parser.add_argument(
        "-y",
        "--yaxunit",
        dest="yaxunit_project",
        type=Path,
        required=True,
        help="EDT-проект YAXUNIT (CFE).",
    )
    return parser


def absolute(path: Path, base_dir: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def parse_options(argv: list[str] | None) -> Options:
    parser = build_parser()
    args = parser.parse_args(argv)
    workdir = Path.cwd().resolve()
    return Options(
        output_dir=absolute(args.output_dir, workdir),
        base_project=absolute(args.base_project, workdir),
        adapter_project=absolute(args.adapter_project, workdir),
        examples_project=absolute(args.examples_project, workdir),
        yaxunit_project=absolute(args.yaxunit_project, workdir),
    )


def require_project(path: Path, description: str) -> None:
    if not path.is_dir():
        raise ScriptError(f"{description} не найден: {path}")
    for entry in (".project", "DT-INF", "src"):
        if not (path / entry).exists():
            raise ScriptError(f"{description} не похож на EDT-проект, отсутствует {entry}: {path}")
    if not (path / CONFIGURATION_MDO).is_file():
        raise ScriptError(f"{description} не содержит {CONFIGURATION_MDO}: {path}")


def ensure_safe_output(options: Options) -> None:
    # Скрипт удаляет управляемые элементы EDT-проекта внутри результата.
    # Поэтому запрещаем пересечение результата с любым исходным проектом.
    output = options.output_dir.resolve()
    if output == Path(output.anchor) or output.parent == output:
        raise ScriptError(f"Небезопасный каталог результата: {output}")

    for source in (
        options.base_project,
        options.adapter_project,
        options.examples_project,
        options.yaxunit_project,
    ):
        resolved = source.resolve()
        if output == resolved or output in resolved.parents or resolved in output.parents:
            raise ScriptError(f"Каталог результата не должен пересекаться с исходным проектом: {resolved}")


def validate_options(options: Options) -> None:
    require_project(options.base_project, "Проект base")
    require_project(options.adapter_project, "Проект adapter")
    require_project(options.examples_project, "Проект examples")
    require_project(options.yaxunit_project, "Проект YAXUNIT")
    ensure_safe_output(options)


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def reset_output_project_entries(path: Path) -> None:
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    # Не удаляем весь --output: там могут быть README, настройки IDE или
    # служебные файлы репозитория тестов. Чистим только то, что копируем сами.
    for entry in CLEAN_OUTPUT_ENTRIES:
        target = resolved / entry
        if target.exists():
            print(f"Удаление: {target}")
            remove_path(target)


def copy_project_entries(source: Path, target: Path) -> int:
    # Копируем только стандартные корневые элементы EDT-проекта.
    # Документация, CI и прочие файлы исходных репозиториев в результат не нужны.
    copied_files = 0
    for entry in EDT_PROJECT_ENTRIES:
        src = source / entry
        dst = target / entry
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied_files += count_files(src)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied_files += 1
    return copied_files


def count_files(path: Path) -> int:
    if path.is_file():
        return 1
    if not path.is_dir():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def patch_file(path: Path, transform: Callable[[str], str]) -> None:
    content = path.read_text(encoding="utf-8")
    patched = transform(content)
    if patched != content:
        path.write_text(patched, encoding="utf-8")


def remove_extension_tags(content: str) -> str:
    # EDT хранит признаки расширения в *.mdo. Для объединения с base эти
    # признаки нужно убрать, чтобы проект стал обычной конфигурацией.
    for tag in EXTENSION_TAGS:
        content = re.sub(rf"\s*<{tag}\b[^>]*/>", "", content)
        content = re.sub(rf"\s*<{tag}\b[^>]*>.*?</{tag}>", "", content, flags=re.DOTALL)
    return content


def convert_cfe_project_to_cf(project_dir: Path) -> None:
    # Локальная версия логики из tools/.github/scripts/patch_mdo.py:
    # меняем nature проекта, убираем Base-Project и extension-теги.
    print(f"Конвертация CFE -> CF: {project_dir}")
    project_file = project_dir / ".project"
    patch_file(project_file, lambda content: content.replace("V8ExtensionNature", "V8ConfigurationNature"))

    pmf_file = project_dir / "DT-INF" / "PROJECT.PMF"
    if pmf_file.is_file():
        patch_file(
            pmf_file,
            lambda content: "".join(line for line in content.splitlines(keepends=True) if "Base-Project" not in line),
        )

    for metadata_file in project_dir.rglob("*.mdo"):
        patch_file(metadata_file, remove_extension_tags)


def copy_tree_contents(source: Path, target: Path, excluded_relative_roots: frozenset[Path] = frozenset()) -> int:
    # Копируем дерево src, пропуская корни, которые сливаются специальной логикой.
    copied_files = 0
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if any(relative == excluded or excluded in relative.parents for excluded in excluded_relative_roots):
            continue
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
        copied_files += 1
    return copied_files


def collect_namespaces(xml_source: Path) -> list[tuple[str, str]]:
    namespaces: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, namespace in ElementTree.iterparse(str(xml_source), events=("start-ns",)):
        if namespace not in seen:
            seen.add(namespace)
            namespaces.append(namespace)
    return namespaces


def register_namespaces(*xml_sources: Path) -> None:
    for xml_source in xml_sources:
        for prefix, uri in collect_namespaces(xml_source):
            ElementTree.register_namespace(prefix, uri)


def element_local_name(element: ElementTree.Element) -> str:
    if element.tag.startswith("{"):
        return element.tag.rsplit("}", maxsplit=1)[1]
    return element.tag


def should_merge_configuration_node(
    element: ElementTree.Element,
    excluded_refs: frozenset[tuple[str, str]],
) -> bool:
    local_name = element_local_name(element)
    if local_name not in MERGED_CONFIGURATION_TAGS:
        return False
    text = (element.text or "").strip()
    return (local_name, text) not in excluded_refs


def existing_configuration_keys(root: ElementTree.Element) -> set[tuple[str, str, tuple[tuple[str, str], ...]]]:
    keys: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    for element in root:
        local_name = element_local_name(element)
        text = (element.text or "").strip()
        attributes = tuple(sorted(element.attrib.items()))
        keys.add((local_name, text, attributes))
    return keys


def merge_configuration_mdo(
    source_project: Path,
    target_project: Path,
    excluded_refs: frozenset[tuple[str, str]] = frozenset(),
) -> int:
    # Файлы объектов уже скопированы в src. Здесь добавляем ссылки на эти
    # объекты в целевой src/Configuration/Configuration.mdo.
    source_path = source_project / CONFIGURATION_MDO
    target_path = target_project / CONFIGURATION_MDO
    register_namespaces(target_path, source_path)

    target_tree = ElementTree.parse(target_path)
    source_tree = ElementTree.parse(source_path)
    target_root = target_tree.getroot()
    known_keys = existing_configuration_keys(target_root)

    added_count = 0
    for source_child in source_tree.getroot():
        if not should_merge_configuration_node(source_child, excluded_refs):
            continue

        local_name = element_local_name(source_child)
        text = (source_child.text or "").strip()
        attributes = tuple(sorted(source_child.attrib.items()))
        key = (local_name, text, attributes)
        if key in known_keys:
            continue

        target_root.append(copy.deepcopy(source_child))
        known_keys.add(key)
        added_count += 1

    ElementTree.indent(target_tree, space="  ")
    target_tree.write(target_path, encoding="UTF-8", xml_declaration=True)
    return added_count


def is_procedure_start(line: str, procedure_name: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("Процедура ") and f" {procedure_name}(" in f" {stripped}"


def procedure_bounds(lines: list[str], procedure_name: str) -> tuple[int, int]:
    start_index = None
    for index, line in enumerate(lines):
        if is_procedure_start(line, procedure_name):
            start_index = index
            break

    if start_index is None:
        raise ScriptError(f"Процедура не найдена: {procedure_name}")

    for index in range(start_index + 1, len(lines)):
        if lines[index].strip().lower() == "конецпроцедуры":
            return start_index, index

    raise ScriptError(f"Конец процедуры не найден: {procedure_name}")


def trimmed_body(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and lines[start].strip() == "":
        start += 1
    while end > start and lines[end - 1].strip() == "":
        end -= 1
    return lines[start:end]


def procedure_body(lines: list[str], procedure_name: str) -> list[str]:
    start_index, end_index = procedure_bounds(lines, procedure_name)
    return trimmed_body(lines[start_index + 1 : end_index])


def insert_before_procedure_end(lines: list[str], procedure_name: str, inserted_lines: list[str]) -> None:
    start_index, end_index = procedure_bounds(lines, procedure_name)
    while end_index > start_index + 1 and lines[end_index - 1].strip() == "":
        del lines[end_index - 1]
        end_index -= 1
    lines[end_index:end_index] = ["", *inserted_lines, ""]


def detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def is_region_start(line: str, region_name: str) -> bool:
    # Ниже небольшой BSL-парсер для слияния модулей приложения YAXUNIT.
    # Полный парсер здесь не нужен: достаточно областей, переменных и методов.
    return line.strip().lower() == f"#область {region_name}".lower()


def is_region_end(line: str) -> bool:
    return line.strip().lower() == "#конецобласти"


def region_bounds(lines: list[str], region_name: str) -> tuple[int, int] | None:
    for start_index, line in enumerate(lines):
        if not is_region_start(line, region_name):
            continue
        for end_index in range(start_index + 1, len(lines)):
            if is_region_end(lines[end_index]):
                return start_index, end_index
        raise ScriptError(f"Конец области не найден: {region_name}")
    return None


def bsl_method_start(line: str) -> tuple[str, str] | None:
    stripped = line.lstrip()
    keyword_by_kind = {
        "процедура": "procedure",
        "procedure": "procedure",
        "функция": "function",
        "function": "function",
    }
    for keyword, kind in keyword_by_kind.items():
        prefix = f"{keyword} "
        if not stripped.lower().startswith(prefix):
            continue
        name = stripped[len(prefix) :].lstrip().split("(", maxsplit=1)[0].strip()
        if name:
            return name, kind
    return None


def is_bsl_method_end(line: str, kind: str) -> bool:
    stripped = line.strip().lower()
    if kind == "procedure":
        return stripped in {"конецпроцедуры", "endprocedure"}
    if kind == "function":
        return stripped in {"конецфункции", "endfunction"}
    return False


def iter_bsl_methods(lines: list[str]) -> list[BslMethod]:
    methods: list[BslMethod] = []
    index = 0
    while index < len(lines):
        method_start = bsl_method_start(lines[index])
        if method_start is None:
            index += 1
            continue
        name, kind = method_start
        for end_index in range(index + 1, len(lines)):
            if is_bsl_method_end(lines[end_index], kind):
                methods.append(BslMethod(name=name, kind=kind, start=index, end=end_index))
                index = end_index + 1
                break
        else:
            raise ScriptError(f"Конец метода не найден: {name}")
    return methods


def bsl_method_bounds(lines: list[str], method_name: str) -> BslMethod:
    normalized_name = method_name.lower()
    for method in iter_bsl_methods(lines):
        if method.name.lower() == normalized_name:
            return method
    raise ScriptError(f"Метод не найден: {method_name}")


def bsl_method_body_start(lines: list[str], method: BslMethod) -> int:
    if ")" in lines[method.start]:
        return method.start + 1
    for index in range(method.start + 1, method.end):
        if ")" in lines[index]:
            return index + 1
    return method.start + 1


def bsl_method_body(lines: list[str], method: BslMethod) -> list[str]:
    return trimmed_body(lines[bsl_method_body_start(lines, method) : method.end])


def variable_names(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    lower = stripped.lower()
    if lower.startswith("перем "):
        declaration = stripped[len("Перем ") :]
    elif lower.startswith("var "):
        declaration = stripped[len("Var ") :]
    else:
        return ()

    declaration = declaration.split("//", maxsplit=1)[0].replace(";", " ")
    names: list[str] = []
    for part in declaration.split(","):
        words = part.strip().split()
        if words and words[0].lower() not in {"экспорт", "export"}:
            names.append(words[0])
    return tuple(names)


def variable_declaration_blocks(lines: list[str]) -> list[tuple[tuple[str, ...], list[str]]]:
    bounds = region_bounds(lines, "ОписаниеПеременных")
    if bounds is None:
        return []

    _, region_end = bounds
    blocks: list[tuple[tuple[str, ...], list[str]]] = []
    index = bounds[0] + 1
    while index < region_end:
        names = variable_names(lines[index])
        if not names:
            index += 1
            continue
        block_end = index + 1
        while (
            block_end < region_end
            and lines[block_end].startswith((" ", "\t"))
            and lines[block_end].lstrip().startswith("//")
        ):
            block_end += 1
        blocks.append((names, lines[index:block_end]))
        index = block_end
    return blocks


def all_variable_names(lines: list[str]) -> set[str]:
    result: set[str] = set()
    for line in lines:
        result.update(name.lower() for name in variable_names(line))
    return result


def ensure_variables_region(lines: list[str]) -> tuple[int, int]:
    bounds = region_bounds(lines, "ОписаниеПеременных")
    if bounds is not None:
        return bounds

    insertion_index = 0
    while (
        insertion_index < len(lines)
        and (lines[insertion_index].strip() == "" or lines[insertion_index].lstrip().startswith("//"))
    ):
        insertion_index += 1

    lines[insertion_index:insertion_index] = [
        "#Область ОписаниеПеременных",
        "",
        "#КонецОбласти",
        "",
    ]
    return insertion_index, insertion_index + 2


def insert_missing_variable_declarations(target_lines: list[str], source_lines: list[str]) -> int:
    existing_names = all_variable_names(target_lines)
    inserted_lines: list[str] = []
    inserted_count = 0
    for names, block in variable_declaration_blocks(source_lines):
        missing_names = [name for name in names if name.lower() not in existing_names]
        if not missing_names:
            continue
        inserted_lines.extend(block)
        inserted_count += len(missing_names)
        existing_names.update(name.lower() for name in names)

    if not inserted_lines:
        return 0

    _, region_end = ensure_variables_region(target_lines)
    if region_end > 0 and target_lines[region_end - 1].strip() != "":
        inserted_lines = ["", *inserted_lines]
    if inserted_lines[-1].strip() != "":
        inserted_lines.append("")
    target_lines[region_end:region_end] = inserted_lines
    return inserted_count


def append_bsl_method(target_lines: list[str], method_lines: list[str]) -> None:
    while target_lines and target_lines[-1].strip() == "":
        target_lines.pop()
    target_lines.extend(["", *method_lines])


def merge_bsl_methods(target_lines: list[str], source_lines: list[str]) -> int:
    merged_count = 0
    for source_method in iter_bsl_methods(source_lines):
        source_body = bsl_method_body(source_lines, source_method)
        if not source_body:
            continue

        try:
            target_method = bsl_method_bounds(target_lines, source_method.name)
        except ScriptError:
            append_bsl_method(target_lines, source_lines[source_method.start : source_method.end + 1])
            merged_count += 1
            continue

        while target_method.end > target_method.start + 1 and target_lines[target_method.end - 1].strip() == "":
            del target_lines[target_method.end - 1]
            target_method = bsl_method_bounds(target_lines, source_method.name)

        target_lines[target_method.end : target_method.end] = ["", *source_body, ""]
        merged_count += 1
    return merged_count


def merge_application_module(source_path: Path, target_path: Path) -> ApplicationModuleMergeStats:
    source_text = source_path.read_text(encoding="utf-8-sig")
    if not target_path.is_file():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        return ApplicationModuleMergeStats(copied_modules=1, variable_declarations=0, methods=0)

    target_text = target_path.read_text(encoding="utf-8-sig")
    source_lines = source_text.splitlines()
    target_lines = target_text.splitlines()
    variable_declarations = insert_missing_variable_declarations(target_lines, source_lines)
    methods = merge_bsl_methods(target_lines, source_lines)

    if variable_declarations or methods:
        newline = detect_newline(target_text)
        target_path.write_text(newline.join(target_lines) + newline, encoding="utf-8")

    return ApplicationModuleMergeStats(
        copied_modules=0,
        variable_declarations=variable_declarations,
        methods=methods,
    )


def merge_application_modules(source_project: Path, target_project: Path) -> ApplicationModuleMergeStats:
    # YAXUNIT может добавлять код в модули приложения. Их нельзя заменить целиком:
    # нужно сохранить base-код и добавить отсутствующие переменные/методы.
    copied_modules = 0
    variable_declarations = 0
    methods = 0
    for module_path in APPLICATION_MODULE_PATHS:
        source_path = source_project / module_path
        if not source_path.is_file():
            continue
        stats = merge_application_module(source_path, target_project / module_path)
        copied_modules += stats.copied_modules
        variable_declarations += stats.variable_declarations
        methods += stats.methods
    return ApplicationModuleMergeStats(
        copied_modules=copied_modules,
        variable_declarations=variable_declarations,
        methods=methods,
    )


def merge_update_handlers_procedure(source_project: Path, target_project: Path) -> int:
    # Examples содержит свой модуль обновления. Сам модуль не копируем,
    # а добавляем тело тестовой процедуры в общий модуль обновления adapter.
    source_path = source_project / UPDATE_DB_MODULE_SOURCE
    target_path = target_project / UPDATE_DB_MODULE_SOURCE
    if not source_path.is_file():
        raise ScriptError(f"Модуль обновления examples не найден: {source_path}")
    if not target_path.is_file():
        raise ScriptError(f"Целевой модуль обновления не найден: {target_path}")

    source_text = source_path.read_text(encoding="utf-8-sig")
    source_body = procedure_body(source_text.splitlines(), EXAMPLES_UPDATE_HANDLERS_PROCEDURE)
    if not source_body:
        return 0

    target_text = target_path.read_text(encoding="utf-8-sig")
    target_lines = target_text.splitlines()
    insert_before_procedure_end(target_lines, UPDATE_HANDLERS_PROCEDURE, source_body)
    newline = detect_newline(target_text)
    target_path.write_text(newline.join(target_lines) + newline, encoding="utf-8")
    return len(source_body)


def merge_overridable_commands_procedure(source_project: Path, target_project: Path) -> int:
    # Examples содержит свой модуль переопределения команд. Сам модуль не копируем,
    # а добавляем тело тестовой процедуры в одноименную base-процедуру.
    source_path = source_project / OVERRIDABLE_COMMANDS_MODULE_SOURCE
    target_path = target_project / OVERRIDABLE_COMMANDS_MODULE_SOURCE
    if not source_path.is_file():
        raise ScriptError(f"Модуль ПодключаемыеКомандыПереопределяемый examples не найден: {source_path}")
    if not target_path.is_file():
        raise ScriptError(f"Целевой модуль ПодключаемыеКомандыПереопределяемый не найден: {target_path}")

    source_text = source_path.read_text(encoding="utf-8-sig")
    source_body = procedure_body(source_text.splitlines(), EXAMPLES_OVERRIDABLE_COMMANDS_PROCEDURE)
    if not source_body:
        return 0

    target_text = target_path.read_text(encoding="utf-8-sig")
    target_lines = target_text.splitlines()
    insert_before_procedure_end(target_lines, OVERRIDABLE_COMMANDS_PROCEDURE, source_body)
    newline = detect_newline(target_text)
    target_path.write_text(newline.join(target_lines) + newline, encoding="utf-8")
    return len(source_body)


def merge_cf_project(
    source_project: Path,
    target_project: Path,
    excluded_src_roots: frozenset[Path] = frozenset(),
    excluded_configuration_refs: frozenset[tuple[str, str]] = frozenset(),
) -> MergeStats:
    # Каталог src/Configuration не копируем поверх base: там лежат модули
    # приложения и интерфейс. Configuration.mdo сливается отдельно.
    src_exclusions = frozenset({Path("Configuration"), *excluded_src_roots})
    copied_files = copy_tree_contents(source_project / "src", target_project / "src", src_exclusions)
    configuration_nodes = merge_configuration_mdo(source_project, target_project, excluded_configuration_refs)
    return MergeStats(copied_files=copied_files, configuration_nodes=configuration_nodes)


def prepare_converted_project(source_project: Path, temp_root: Path, name: str) -> Path:
    converted = temp_root / name
    copy_project_entries(source_project, converted)
    convert_cfe_project_to_cf(converted)
    return converted


def build_test_edt_project(options: Options) -> None:
    validate_options(options)
    reset_output_project_entries(options.output_dir)

    # Base является каркасом проекта. Остальные проекты накладываются на него.
    base_files = copy_project_entries(options.base_project, options.output_dir)
    print(f"Base copied: {base_files} files")

    with tempfile.TemporaryDirectory(prefix="create_test_edt_") as temp_dir_name:
        temp_root = Path(temp_dir_name)

        adapter = prepare_converted_project(options.adapter_project, temp_root, "adapter")
        adapter_stats = merge_cf_project(
            adapter,
            options.output_dir,
            excluded_src_roots=frozenset({Path("Catalogs") / "Пользователи"}),
        )
        print(
            "Adapter merged: "
            f"{adapter_stats.copied_files} files, {adapter_stats.configuration_nodes} Configuration.mdo nodes"
        )

        examples = prepare_converted_project(options.examples_project, temp_root, "examples")
        examples_stats = merge_cf_project(
            examples,
            options.output_dir,
            excluded_src_roots=frozenset(
                {
                    UPDATE_DB_MODULE_PATH.relative_to("src"),
                    OVERRIDABLE_COMMANDS_MODULE_PATH.relative_to("src"),
                }
            ),
            excluded_configuration_refs=frozenset(
                {
                    ("commonModules", f"CommonModule.{UPDATE_DB_MODULE_NAME}"),
                    ("commonModules", f"CommonModule.{OVERRIDABLE_COMMANDS_MODULE_NAME}"),
                }
            ),
        )
        update_handler_lines = merge_update_handlers_procedure(examples, options.output_dir)
        overridable_commands_lines = merge_overridable_commands_procedure(examples, options.output_dir)
        print(
            "Examples merged: "
            f"{examples_stats.copied_files} files, {examples_stats.configuration_nodes} Configuration.mdo nodes, "
            f"{update_handler_lines} update handler lines, "
            f"{overridable_commands_lines} overridable command lines"
        )

        yaxunit = prepare_converted_project(options.yaxunit_project, temp_root, "yaxunit")
        yaxunit_stats = merge_cf_project(yaxunit, options.output_dir)
        yaxunit_application_modules = merge_application_modules(yaxunit, options.output_dir)
        print(
            "YAXUNIT merged: "
            f"{yaxunit_stats.copied_files} files, {yaxunit_stats.configuration_nodes} Configuration.mdo nodes, "
            f"{yaxunit_application_modules.copied_modules} app modules copied, "
            f"{yaxunit_application_modules.variable_declarations} app variables, "
            f"{yaxunit_application_modules.methods} app methods"
        )

    print(f"Done: {options.output_dir}")


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    try:
        options = parse_options(argv)
        build_test_edt_project(options)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
