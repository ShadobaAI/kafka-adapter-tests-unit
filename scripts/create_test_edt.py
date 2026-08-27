#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создание тестового EDT-проекта из base + adapter.

В отличие от create_test_cf.py этот скрипт работает не с XML-выгрузкой
Конфигуратора 1С, а с исходниками EDT-проекта. CFE-проект adapter сначала
приводится к виду CF-проекта, после чего его metadata сливается с base.
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


@dataclass(frozen=True)
class MergeStats:
    copied_files: int
    configuration_nodes: int


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
            "Создает EDT-проект тестовой конфигурации из base и adapter. "
            "CFE-проект adapter предварительно конвертируется в формат CF-проекта."
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

    for source in (options.base_project, options.adapter_project):
        resolved = source.resolve()
        if output == resolved or output in resolved.parents or resolved in output.parents:
            raise ScriptError(f"Каталог результата не должен пересекаться с исходным проектом: {resolved}")


def validate_options(options: Options) -> None:
    require_project(options.base_project, "Проект base")
    require_project(options.adapter_project, "Проект adapter")
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

    # Base является каркасом проекта, поверх которого накладывается adapter.
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
