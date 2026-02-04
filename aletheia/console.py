from rich.console import Console

_console_wrapper = None


class _ConsoleWrapper:
    def __init__(self, output_functions: bool = True):
        self.output_functions = output_functions
        self._console = None

    def get_console(self) -> Console:
        if self._console is None:
            self._console = Console()
        return self._console

    def get_output_functions(self) -> bool:
        return self.output_functions

    def disable_output_functions(self) -> None:
        self.output_functions = False


def get_console_wrapper(output_functions: bool = True) -> _ConsoleWrapper:
    global _console_wrapper
    if _console_wrapper is None:
        _console_wrapper = _ConsoleWrapper(output_functions)

    return _console_wrapper
