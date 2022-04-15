import ast
import importlib.metadata
import pathlib
import sys
import textwrap
from functools import lru_cache
from importlib.machinery import EXTENSION_SUFFIXES, SOURCE_SUFFIXES
from logging import getLogger
from modulefinder import ModuleFinder
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pkg_resources import Environment

logger = getLogger(__name__)


class FutureImportFinder(ast.NodeVisitor):
    """Find the bottom of future statement.

    Note:
        A future statement must appear near the top of the module.
        see: https://docs.python.org/3/reference/simple_stmts.html#future
    """

    def __init__(self) -> None:
        self.last_future = 0

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module == "__future__":
            if node.end_lineno is None:
                end = node.lineno
            else:
                end = node.end_lineno

            self.last_future = max(self.last_future, end)

    @classmethod
    def search_insert_point(cls, code: str) -> int:
        tree = ast.parse(code)
        visitor = cls()
        visitor.visit(tree)
        return visitor.last_future


@lru_cache(maxsize=1)
def get_package_info() -> Tuple[Dict[str, str], Dict[str, Optional[str]]]:
    """Get the relationship between module and package.

    Note:
        Some modules have a different module name than the package name
        (e.g. scikit-learn <-> sklearn). The package name is needed to
        get the package metadata, but usually you can't get the package
        name from the module name. Therefore, check the module name
        included in all installed packages.
    """
    module_to_pkg_name: Dict[str, str] = dict()
    pkg_license: Dict[str, Optional[str]] = dict()
    for pkg_name, env in Environment()._distmap.items():  # type: ignore
        for dist in env:
            try:
                pkg_license[pkg_name] = dist._provider.get_metadata("LICENSE")
            except Exception:
                pkg_license[pkg_name] = None
            try:
                for top in dist._provider.get_metadata_lines("top_level.txt"):
                    module_to_pkg_name[top] = pkg_name
            except Exception:
                pass
    return module_to_pkg_name, pkg_license


def make_metadata(package: str) -> Optional[str]:
    module_to_pkg_name, pkg_license = get_package_info()
    res = []
    if package in module_to_pkg_name:
        pkg_name = module_to_pkg_name[package]
        meta = importlib.metadata.metadata(pkg_name)
        res.append(f'# {meta["Name"]}\n')
        for field in ["Version", "Author", "Home-page", "License"]:
            if field in meta:
                res.append(f"#   {field:<9s}: {meta[field]}\n")
        if meta["License"] not in {"CC0"}:
            license_text = pkg_license[pkg_name]
            if license_text is not None:
                res.append("#\n")
                for line in license_text.splitlines():
                    res.append(f"#   {line}\n")
        return "".join(res)
    else:
        return None


IMPORT_CYTHON = """\
import numpy as np
from Cython.Build import cythonize
from setuptools import Extension, setup

"""
BUILD_CYTHON = """\
extensions = Extension(
    "*",
    ["./**/*.pyx"],
    include_dirs=[np.get_include()],
    extra_compile_args=["-O3"],
)
setup(
    ext_modules=cythonize([extensions]),
    script_args=["build_ext", "--inplace"],
)

"""

# These modules cannot be analyzed by modulefinder due to an error.
EXCLUDE_MODULES = ["networkx", "numba", "sklearn"]


def expand(src: pathlib.Path, expand_modules: List[str]) -> str:
    """Expand modules.

    Args:
        source (Path): source to expand
        expand (List[str]): List of expand module names.

    Returns:
        str: expanded code

    Note:
        This module is intended to be used in competition programming.
    """
    finder = ModuleFinder(excludes=EXCLUDE_MODULES)
    finder.run_script(str(src))

    header = 'import sys\n\nif sys.argv[-1] == "ONLINE_JUDGE":\n'
    result = ["import textwrap\nimport pathlib\n\n"]
    cython_import_flg = False
    bundled_pkg = set()

    for name, module in finder.modules.items():
        top_package = name.split(".")[0]
        if top_package in expand_modules:
            if module.__file__ is None:
                continue
            file = Path(module.__file__)
            bundled_pkg.add(top_package)

            if file.suffix in SOURCE_SUFFIXES:
                pass
            elif file.suffix in EXTENSION_SUFFIXES:
                cython_import_flg = True
                file = file.with_name(file.stem.split(".")[0] + ".pyx")
                if not file.exists():
                    logger.error("Faild to find pyx file.")
                    sys.exit(1)
            else:
                logger.error(f"Unknown filetype: {file}")
                sys.exit(1)

            for site in sys.path:
                try:
                    relative_path = file.relative_to(site)
                    break
                except ValueError:
                    pass
            else:
                logger.error("failed to resolve path")

            logger.info(f"load `{name}` form {file}")
            code = file.read_text()
            code = code.replace("\\", "\\\\").replace('"""', '\\"""')
            result.append(
                f'file = pathlib.Path("{relative_path}")\n'
                "file.parent.mkdir(parents=True, exist_ok=True)\n"
                'code = """\\\n'
                f'{code}"""\n'
                "file.write_text(textwrap.dedent(code))\n\n"
            )

    if cython_import_flg:
        logger.info("add setup for cythonize")
        result[0] += IMPORT_CYTHON
        result.append(BUILD_CYTHON)
    bundled = header + textwrap.indent("".join(result), "    ")

    code = src.read_text()
    code_lines = code.splitlines(keepends=True)
    insert_point = FutureImportFinder.search_insert_point(code)
    if len(result) > 1:
        if insert_point != 0:
            bundled = "\n" + bundled
        code_lines.insert(insert_point, bundled)

    infomations: List[str] = []
    for top_package in sorted(list(bundled_pkg)):
        info = make_metadata(top_package)
        if info is not None:
            if not infomations:
                infomations.append("\n\n# package infomations\n")
                infomations.append("# " + "-" * 77 + "\n")
            infomations.append(info)
            infomations.append("# " + "-" * 77 + "\n")

    return "".join(code_lines + infomations)
