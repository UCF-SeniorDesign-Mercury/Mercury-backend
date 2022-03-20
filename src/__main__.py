# -*- coding: utf-8 -*-
"""
    src.__main__
    ~~~~~~~~~~~~
    Handles arguments from the cli and runs the app.
    Functions:
        main()
        test()
"""
from src import app
from os import environ
from flask.cli import FlaskGroup

try:
    import pytest

    test_present = True
except ImportError:
    test_present = False

environ["FLASK_APP"] = "src.__main__:main()"

cli = FlaskGroup()


def main():
    return app


@cli.command()
def test():
    if test_present:
        pytest.main(["--doctest-modules", "--junitxml=junit/test-results.xml"])
    else:
        print("pytest not present")


if __name__ == "__main__":
    cli()
