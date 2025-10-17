
import subprocess
import sys
import os
from pathlib import Path
from textwrap import dedent

# A simple and safe way to execute arbitrary python code.
# The code will be executed in a separate process with resource limits.
# The communication with the child process is done via pipes.
def execute_in_sandbox(code: str, timeout: int = 5, input_text: str = "") -> dict:
    """
    Executes Python code in a sandboxed environment using a separate process.

    Args:
        code: The Python code to execute.
        timeout: The timeout in seconds.

    Returns:
        A dictionary containing the stdout, stderr, and any errors.
    """
    # Create a temporary file to write the code to.
    # This is safer than passing the code directly to the shell.
    tmp_dir = Path("/tmp/bot_admin_sandbox")
    tmp_dir.mkdir(exist_ok=True)
    # Create a unique file for each execution
    code_file = tmp_dir / f"sandbox_code_{os.urandom(8).hex()}.py"

    # A wrapper script that will be executed in the child process.
    # It sets resource limits and then executes the user's code (supports top-level await).
    code_literal = repr(code)
    input_literal = repr(input_text)
    base_template = """
import asyncio
import ast
import inspect
import resource
import sys
try:
    resource.setrlimit(resource.RLIMIT_CPU, ({timeout}, {timeout}))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_AS, ({memory_limit}, {memory_limit}))
except (ValueError, OSError, AttributeError):
    pass

_original_input = input
def disabled_input(*args, **kwargs):
    raise RuntimeError("The input() function is disabled in the sandbox.")
__builtins__.input = disabled_input

def sandbox_print(*args, **kwargs):
    print(*args, **kwargs)

code_source = {code_literal}
namespace = {{
    "__builtins__": __builtins__,
    "__name__": "__main__",
    "sandbox_print": sandbox_print,
    "input": disabled_input,
}}


class _DummyMessage:
    def __init__(self, text: str):
        self.text = text

    async def reply_text(self, text, **kwargs):
        print(f"[reply_text] {{text}}")
        return {{"text": text, **kwargs}}

    async def reply_html(self, html, **kwargs):
        print(f"[reply_html] {{html}}")
        return {{"html": html, **kwargs}}

    async def reply_photo(self, photo, **kwargs):
        print(f"[reply_photo] {{photo}}")
        return {{"photo": photo, **kwargs}}


class _DummyBot:
    async def send_message(self, chat_id, text, **kwargs):
        print(f"[send_message -> chat {{chat_id}}] {{text}}")
        return {{"chat_id": chat_id, "text": text, **kwargs}}

    async def send_photo(self, chat_id, photo, **kwargs):
        print(f"[send_photo -> chat {{chat_id}}] {{photo}}")
        return {{"chat_id": chat_id, "photo": photo, **kwargs}}


class _FakeDB:
    def __init__(self):
        self._store = {{}}

    def __getitem__(self, op):
        if op == "get":
            def getter(scope, name, default=None):
                return self._store.get((scope, name), default)
            return getter
        if op == "set":
            def setter(scope, name, value):
                self._store[(scope, name)] = value
                return value
            return setter
        raise KeyError(op)


class _DummyContext:
    def __init__(self, args=None):
        self.args = args or []
        self.bot = _DummyBot()
        self.chat_data = {{}}
        self.user_data = {{}}
        self.application = type("App", (), {{"logger": None}})()
        self.db = _FakeDB()


def log(message: str):
    print(f"[log] {{message}}")


_raw_input = {input_literal}
_tokens = [token for token in _raw_input.strip().split() if token]
_args = _tokens[1:] if _tokens else []
_message = _DummyMessage(_raw_input)
update = type(
    "Update",
    (),
    {{
        "message": _message,
        "effective_chat": type("Chat", (), {{"id": 0}})(),
        "effective_user": type("User", (), {{"id": 0, "first_name": "Sandbox"}})(),
    }},
)()
context = _DummyContext(_args)
namespace.update(
    {{
        "update": update,
        "context": context,
        "print": sandbox_print,
        "log": log,
    }}
)

def _run_wrapped(src: str):
    lines = src.splitlines()
    if lines:
        indented = "\\n".join("    " + line for line in lines)
    else:
        indented = "    pass"
    wrapper = "async def __sandbox_entry__():\\n" + indented + "\\n"
    exec(wrapper, namespace, namespace)
    entry = namespace["__sandbox_entry__"]()
    if inspect.iscoroutine(entry):
        asyncio.run(entry)
    else:
        return entry

try:
    print("--- Sandbox execution started ---")
    flags = getattr(ast, "PyCF_ALLOW_TOP_LEVEL_AWAIT", 0)
    try:
        compiled = compile(code_source, "<sandbox>", "exec", flags=flags)
    except SyntaxError as compile_error:
        message = str(compile_error)
        if "return" in message and "function" in message:
            _run_wrapped(code_source)
        else:
            raise
    else:
        result = eval(compiled, namespace, namespace)
        if inspect.iscoroutine(result):
            asyncio.run(result)
    print("--- Sandbox execution finished ---")
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    wrapped_code = dedent(base_template).format(
        timeout=timeout,
        memory_limit=200 * 1024 * 1024,
        code_literal=code_literal,
        input_literal=input_literal,
    )

    with open(code_file, "w") as f:
        f.write(wrapped_code)

    try:
        process = subprocess.Popen(
            [sys.executable, str(code_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return {"stdout": stdout, "stderr": stderr, "error": None}
    except subprocess.TimeoutExpired:
        process.kill()
        return {"stdout": "", "stderr": "Execution timed out.", "error": "Timeout"}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "error": "Execution failed"}
    finally:
        # Clean up the temporary file
        if os.path.exists(code_file):
            os.remove(code_file)
