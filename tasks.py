from pathlib import Path
from typing import Optional

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import task

ROOT_PATH = Path(__file__).parent

SRC_PATH = ROOT_PATH / "crypto_dot_com"
TEST_PATH = ROOT_PATH / "tests"

_PATHS = (SRC_PATH, TEST_PATH)


def run_autoformat(ctx: Context, path: Path):

    with ctx.cd(ROOT_PATH):
        path = path.relative_to(ROOT_PATH)

        ctx.run(
            f"autoflake -r --in-place --remove-all-unused-imports  {path}",
            pty=True,
            echo=True,
        )

        ctx.run(f"isort {path} ", pty=True, echo=True)

        ctx.run(f"black {path}", pty=True, echo=True)

        print("Finished running autoformat!")


@task
def autoformat(ctx: Context) -> None:
    for path in _PATHS:
        run_autoformat(ctx, path)


def run_linters(
    ctx: Context, path: Path, exclude: Optional[list[str]] = None
) -> None:

    with ctx.cd(ROOT_PATH):
        print(f"\U000027A1 Running code quality checks on {path.name}")
        path = path.relative_to(ROOT_PATH)
        ctx.run(
            f"autoflake -cr --remove-all-unused-imports {path} --quiet",
            hide="out",
            echo=True,
        )
        ctx.run(
            f"isort --check --diff {path} ",
            pty=True,
            echo=True,
        )
        ctx.run("mypy --version", pty=True, echo=True)
        ctx.run(f"mypy  {path}", pty=True, echo=True)
        ctx.run(f"flake8  {path}", pty=True, echo=True)
        ctx.run(f"black --check {path}", pty=True, echo=True)
        print("Finished linting!")


@task
def lint(ctx: Context) -> None:
    for path in _PATHS:
        run_linters(ctx, path)


@task
def test(ctx: Context) -> None:
    ctx.run("pytest tests")


@task
def build(ctx: Context) -> None:
    ctx.run("python3.12 setup.py sdist bdist_wheel")
    print("Finished build!")


@task
def deploy(ctx: Context) -> None:
    ctx.run("python3.12 -m twine upload dist/*")
    print("Finished deploy!")


@task
def freeze(ctx: Context) -> None:
    ctx.run("pip freeze > requirements_lock.txt")
    print("Freezed python packages")


@task
def install(ctx: Context) -> None:
    ctx.run("python3.12 -m pip install pip-tools")
    # ctx.run("python3.12 -m pip-compile requirements.in")
    # ctx.run("python3.12 -m pip-compile requirements_dev.in")
    ctx.run("python3.12 -m pip install -r requirements.txt")
    ctx.run("python3.12 -m pip install -r requirements_dev.txt")
    ctx.run("python3.12 -m pip freeze > requirements_lock.txt")
    print("Installed python packages and freezed!")


@task
def tag(ctx: Context) -> None:
    import crypto_dot_com

    ctx.run(f"git tag v{crypto_dot_com.__version__}")
    ctx.run("git push --tags")


ns = Collection()
ns.add_task(autoformat)
ns.add_task(lint)
ns.add_task(test)
ns.add_task(build)
ns.add_task(deploy)
ns.add_task(install)
ns.add_task(tag)
