"""정적 검사 — 프로그램을 실행하지 않고 소스 코드의 '구조'가 명세대로인지 확인한다.

ast 모듈로 소스를 문법 트리로 읽어서 import, 클래스, 데코레이터, 타입 힌트를 센다.
대괄호 번호는 project.md 의 조항 번호다.
"""

import argparse
import ast
import dataclasses
import inspect
import sys
import unittest
from collections.abc import Iterator

from helpers import ROOT
from budget_app import models, storage
from budget_app.cli import build_parser

PACKAGE = ROOT / "budget_app"
SOURCES = {path.stem: path.read_text(encoding="utf-8") for path in sorted(PACKAGE.glob("*.py"))}
TREES = {name: ast.parse(source) for name, source in SOURCES.items()}

# 계층 규칙: 각 모듈이 import 해도 되는 budget_app 안의 모듈 (위 → 아래로만)
ALLOWED_IMPORTS = {
    "errors": set(),
    "models": {"errors"},
    "storage": {"errors", "models"},
    "formatter": {"models"},
    "decorators": {"errors", "formatter"},
    "services": {"errors", "models", "storage", "decorators"},
    "cli": {"errors", "models", "services", "formatter", "decorators"},
    "__main__": {"cli"},
    "__init__": set(),
}


def imported_modules(tree: ast.Module) -> set[str]:
    """import 문에 나온 모듈 이름 전체. 예: {'json', 'budget_app.models'}"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(("." * node.level) + (node.module or ""))
    return names


def functions(tree: ast.Module) -> Iterator[ast.FunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            yield node


def decorator_names(function: ast.FunctionDef) -> list[str]:
    return [ast.unparse(decorator) for decorator in function.decorator_list]


def all_parsers(parser: argparse.ArgumentParser) -> Iterator[argparse.ArgumentParser]:
    """최상위 파서와 모든 하위 명령 파서."""
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                yield from all_parsers(child)


class ConstraintTests(unittest.TestCase):
    def test_only_standard_library(self) -> None:
        """[7] 표준 라이브러리만 사용 (pip install 이 필요한 외부 라이브러리 금지)"""
        for name, tree in TREES.items():
            for module in imported_modules(tree):
                top = module.split(".")[0]
                with self.subTest(file=f"{name}.py", module=module):
                    self.assertTrue(top == "budget_app" or top in sys.stdlib_module_names)
        self.assertFalse((ROOT / "requirements.txt").exists())

    def test_source_is_python_3_10_syntax(self) -> None:
        """[6] Python 3.10 문법으로 읽힌다"""
        for name, source in SOURCES.items():
            with self.subTest(file=f"{name}.py"):
                ast.parse(source, feature_version=(3, 10))

    def test_options_are_double_dash_only(self) -> None:
        """[4.1][7] 옵션 표기는 -- 로 통일"""
        parsers = list(all_parsers(build_parser()))
        self.assertEqual(len(parsers), 22)  # 최상위 1 + 명령·하위 명령 21
        for parser in parsers:
            options = [option for action in parser._actions for option in action.option_strings]
            with self.subTest(prog=parser.prog):
                self.assertIn("--help", options)
                self.assertTrue(all(option.startswith("--") for option in options), msg=options)

    def test_every_leaf_command_has_a_handler(self) -> None:
        """[4.1] 실행되는 명령마다 처리 함수가 연결되어 있다"""
        for parser in all_parsers(build_parser()):
            has_children = any(isinstance(a, argparse._SubParsersAction) for a in parser._actions)
            with self.subTest(prog=parser.prog):
                self.assertEqual(parser.get_default("handler") is None, has_children)

    def test_no_traceback_printing(self) -> None:
        """[7] 스택트레이스 출력 금지 — traceback 모듈을 쓰지 않는다"""
        for name, tree in TREES.items():
            self.assertNotIn("traceback", imported_modules(tree), msg=name)


class StructureTests(unittest.TestCase):
    def test_at_least_three_modules(self) -> None:
        """[4.14] 한 파일에 몰지 않고 최소 3개 이상 모듈로 분리 (CLI / 서비스 / 저장소 / 모델)"""
        for name in ["cli", "services", "storage", "models"]:
            self.assertIn(name, SOURCES)
            self.assertGreater(len(list(functions(TREES[name]))), 3, msg=name)
        self.assertGreaterEqual(len(SOURCES), 3)

    def test_layers_depend_downward_only(self) -> None:
        """[4.14] 계층 책임 분리 — 아래 계층은 위 계층을 import 하지 않는다"""
        for name, tree in TREES.items():
            inside = {m.removeprefix("budget_app.") for m in imported_modules(tree) if m.startswith("budget_app.")}
            with self.subTest(file=f"{name}.py"):
                self.assertLessEqual(inside, ALLOWED_IMPORTS[name], msg=f"허용되지 않은 import: {inside - ALLOWED_IMPORTS[name]}")
        self.assertNotIn("budget_app.storage", imported_modules(TREES["cli"]))  # CLI 는 저장소를 모른다

    def test_only_cli_talks_to_the_user(self) -> None:
        """[4.14] input() 은 CLI 에만 있고, 모델·저장소·서비스는 화면에 출력하지 않는다"""
        def calls(tree: ast.Module, function_name: str) -> int:
            return sum(
                1 for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function_name
            )

        for name in ["models", "storage", "services", "errors"]:
            with self.subTest(file=f"{name}.py"):
                self.assertEqual(calls(TREES[name], "print"), 0)
                self.assertEqual(calls(TREES[name], "input"), 0)
        for name in SOURCES:
            if name != "cli":
                self.assertEqual(calls(TREES[name], "input"), 0, msg=name)
        self.assertGreater(calls(TREES["cli"], "input"), 0)

    def test_only_storage_opens_files(self) -> None:
        """[4.14] 데이터 파일을 여는 코드는 저장소 계층에만 있다"""
        for name, tree in TREES.items():
            opens = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and (getattr(node.func, "id", "") == "open" or getattr(node.func, "attr", "") == "open")
            ]
            if name == "decorators":  # 출력을 버리는 곳(os.devnull)을 여는 한 번뿐
                self.assertEqual([ast.unparse(node) for node in opens], ["os.open(os.devnull, os.O_WRONLY)"])
            elif name != "storage":
                self.assertEqual(opens, [], msg=name)

    def test_at_least_two_classes_and_dataclass(self) -> None:
        """[4.2] dataclass 로 데이터 모델을 정의하고, 클래스를 2개 이상 사용한다"""
        classes = [node.name for tree in TREES.values() for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        self.assertGreaterEqual(len(classes), 2)
        for name in ["Transaction", "TransactionRepository", "TransactionService", "CategoryService", "BudgetService"]:
            self.assertIn(name, classes)
        for model in (models.Transaction, models.Category, models.Budget):
            self.assertTrue(dataclasses.is_dataclass(model))

    def test_three_storage_files_are_separate_repositories(self) -> None:
        """[4.3] transactions / categories / budgets 를 서로 다른 파일로 저장한다"""
        services_source = SOURCES["services"]
        for file_name in ["transactions.jsonl", "categories.jsonl", "budgets.jsonl"]:
            self.assertIn(file_name, services_source)


class TechniqueTests(unittest.TestCase):
    def test_generator_is_used_for_reading(self) -> None:
        """[4.5] 읽기는 yield 기반 제너레이터"""
        self.assertTrue(inspect.isgeneratorfunction(storage.JsonlRepository.stream))
        self.assertTrue(inspect.isgeneratorfunction(storage.read_csv_rows))

    def test_nothing_reads_a_whole_file_at_once(self) -> None:
        """[4.5] readlines() / read() / json.load() 처럼 파일 전체를 읽는 호출이 없다"""
        for name, tree in TREES.items():
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                with self.subTest(file=f"{name}.py", line=node.lineno):
                    self.assertNotIn(node.func.attr, {"readlines", "read_text", "read_bytes", "load"})
                    if node.func.attr == "read":  # file.read(1) 처럼 크기를 정한 읽기만 허용
                        self.assertEqual(len(node.args), 1)

    def test_decorators_are_defined_and_applied(self) -> None:
        """[4.12] 데코레이터를 1개 이상 구현하고 실제로 적용한다"""
        defined = {function.name for function in functions(TREES["decorators"])}
        self.assertLessEqual({"handle_errors", "log_command", "measure_time"}, defined)

        cli_functions = {function.name: decorator_names(function) for function in functions(TREES["cli"])}
        commands = [name for name in cli_functions if name.startswith("cmd_")]
        self.assertEqual(len(commands), 18)
        for name in commands:
            self.assertEqual(cli_functions[name], ["log_command"], msg=name)
        self.assertEqual(cli_functions["main"], ["handle_errors"])

        timed = [f.name for f in functions(TREES["services"]) if "measure_time" in decorator_names(f)]
        self.assertEqual(sorted(timed), ["export_csv", "import_csv", "list_recent", "search", "summarize"])

    def test_decorators_use_functools_wraps(self) -> None:
        """[4.12] 데코레이터 3개 모두 functools.wraps 를 쓴다"""
        wrappers = [f for f in functions(TREES["decorators"]) if f.name == "wrapper"]
        self.assertEqual(len(wrappers), 3)
        for wrapper in wrappers:
            self.assertEqual(decorator_names(wrapper), ["functools.wraps(func)"])

    def test_every_function_has_type_hints(self) -> None:
        """[3] 타입 힌트 — 모든 함수의 매개변수와 반환값에 타입이 적혀 있다"""
        total = 0
        for name, tree in TREES.items():
            for function in functions(tree):
                total += 1
                arguments = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
                arguments += [a for a in (function.args.vararg, function.args.kwarg) if a is not None]
                missing = [a.arg for a in arguments if a.annotation is None and a.arg not in ("self", "cls")]
                with self.subTest(function=f"{name}.{function.name}"):
                    self.assertEqual(missing, [])
                    self.assertIsNotNone(function.returns)
        self.assertGreater(total, 80)


class ReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_required_sections(self) -> None:
        """[2-10] README 에 실행 방법, 저장 파일 위치/형식, 주요 명령 예시, import/export CSV 스키마가 있다"""
        for heading in ["## 실행 방법", "## 저장 파일 위치와 형식", "## 주요 명령 예시", "## import/export CSV 스키마"]:
            self.assertIn(heading, self.readme)
        for text in ["python -m budget_app", "transactions.jsonl", "categories.jsonl", "budgets.jsonl",
                     "date,type,category,amount,memo,tags", "--data-dir", "UTF-8"]:
            self.assertIn(text, self.readme)

    def test_fixed_choices_are_documented(self) -> None:
        """[4.6][4.3] update 방식(옵션)과 카테고리가 비었을 때의 동작을 문서에 고정했다"""
        self.assertIn("update", self.readme)
        self.assertIn("옵션 기반", self.readme)
        self.assertIn("category add", self.readme)
        self.assertIn("JSONL", self.readme)

    def test_every_command_appears_in_readme(self) -> None:
        """[2-10] README 의 명령 예시에 모든 명령이 나온다"""
        for command in ["add", "list", "search", "summary", "budget set", "category add", "category list",
                        "category remove", "update", "delete", "import", "export", "backup", "recurring"]:
            self.assertIn(f"python -m budget_app {command}", self.readme, msg=command)


if __name__ == "__main__":
    unittest.main()
