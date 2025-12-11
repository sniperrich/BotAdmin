
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

    def _key(self, scope, name):
        return (scope, name)

    def _noop(self, op_name):
        def handler(*args, **kwargs):
            print(f"[db:{op_name}] 未实现的操作，参数: args={{args}}, kwargs={{kwargs}}")
            return None
        return handler

    def get(self, scope, name, default=None):
        return self._store.get(self._key(scope, name), default)

    def set(self, scope, name, value):
        self._store[self._key(scope, name)] = value
        return value

    def delete(self, scope, name):
        return self._store.pop(self._key(scope, name), None) is not None

    def incr(self, scope, name, amount=1):
        key = self._key(scope, name)
        current = self._store.get(key, 0)
        try:
            current = int(current)
        except (TypeError, ValueError):
            current = 0
        current += amount
        self._store[key] = current
        return current

    def __getitem__(self, op):
        operations = {{
            "get": self.get,
            "set": self.set,
            "delete": self.delete,
            "del": self.delete,
            "incr": self.incr,
        }}
        return operations.get(op, self._noop(op))


class _SandboxLogger:
    def __init__(self, name="sandbox"):
        self.name = name

    def _emit(self, level, message, *args, **kwargs):
        if args or kwargs:
            try:
                message = message.format(*args, **kwargs)
            except Exception:
                message = f"{{message}} {{args}} {{kwargs}}"
        print(f"[{{level}}] {{message}}")

    def info(self, message, *args, **kwargs):
        self._emit("INFO", message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        self._emit("DEBUG", message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self._emit("WARN", message, *args, **kwargs)

    warn = warning

    def error(self, message, *args, **kwargs):
        self._emit("ERROR", message, *args, **kwargs)

    def exception(self, message, *args, **kwargs):
        self._emit("ERROR", message, *args, **kwargs)


class _DummyApplication:
    def __init__(self):
        self.logger = _SandboxLogger()


class _DummyContext:
    def __init__(self, args=None):
        self.args = args or []
        self.bot = _DummyBot()
        self.chat_data = {{}}
        self.user_data = {{}}
        self.application = _DummyApplication()
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

# ------------------------------------------------------------------------------
# AST Static Analysis for Pro Scripts
# ------------------------------------------------------------------------------

import ast

class SecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        self.errors.append(f"Line {node.lineno}: 'import' statements are not allowed. Please use pre-imported modules.")

    def visit_ImportFrom(self, node):
        self.errors.append(f"Line {node.lineno}: 'from ... import' statements are not allowed.")

    def visit_Call(self, node):
        # Check for dangerous function calls like eval(), exec(), open(), etc.
        if isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec", "open", "compile", "globals", "locals", "__import__", "exit", "quit", "help"):
                self.errors.append(f"Line {node.lineno}: Function '{node.func.id}()' is restricted.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # Optional: Prevent access to private attributes (starting with _)
        if node.attr.startswith("_") and not node.attr.startswith("__"): # Allow dunder methods if needed, block single underscore
             pass # Slightly too restrictive for some libraries, skipping for now unless strict mode.
        self.generic_visit(node)

def validate_script_safety(code: str) -> tuple[bool, str]:
    """
    Statically analyzes Python code to detect unsafe operations.
    Returns (is_safe, error_message).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    visitor = SecurityVisitor()
    visitor.visit(tree)

    if visitor.errors:
        return False, "\n".join(visitor.errors)
    return True, ""
