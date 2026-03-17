import io
import contextlib
import pytest
from archetypeai.utils import ArgParser


def test_argparser_missing_required_arg():
    """
    Ensures that missing required args are correctly reported
    """
    parser = ArgParser()
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2
    assert "the following arguments are required" in stderr.getvalue()

def test_argparser_supports_argumentParser_arguments():
    """
    Ensures that you can pass ArgsParser the same arguments as ArgumentParser supports, and they
    are handled correctly. Technically, this test only valid 2 of ArguemntParser, but this should
    be enough to ensure things work as expected since we use `*args` and `**kwargs` to pass the
    arguments.
    """
    # Test an argument by position (the first argument is `prog`, the name of the pogram)
    parser = ArgParser("MyTestProgram")
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2
    assert "usage: MyTestProgram" in stderr.getvalue()

    # Test an argument by keyword
    parser = ArgParser(usage="A custom usage message")
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2
    assert "usage: A custom usage message" in stderr.getvalue()
