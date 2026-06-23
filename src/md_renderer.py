import base64
import textwrap
import urllib.parse

from mistune import HTMLRenderer, create_markdown


class CustomListRenderer(HTMLRenderer):
    def list_item(self, text, checked=None):
        text_list = text.split("\n")
        parts = []
        for line in text_list:
            if "<code>" in line:
                line = line.replace("<code>", "<inline_code>").replace(
                    "</code>", "</inline_code>"
                )
            parts.append(line)
        if checked is not None:
            checkbox = (
                f'<input type="checkbox" disabled{" checked" if checked else ""}>'
            )
            return f'<li class="task-list-item">{checkbox} {"<br>".join(parts)}</li>'
        return f'<li>{"<br>".join(parts)}</li>'

    def block_code(self, code, info=None):
        code = textwrap.dedent(code)
        code_lines = code.rstrip().split("\n")
        raw_code = "\n".join(code_lines)
        code_content = raw_code.replace("<", "&lt;").replace(">", "&gt;")
        b64 = base64.b64encode(raw_code.encode("utf-8")).decode("ascii")
        encoded = urllib.parse.quote(b64, safe="")
        copy_link = f'<a href="copy:///{encoded}" class="copy-button">Copy</a>'
        table = f'\n<table class="code-block">\n<tr><td>'
        table += (
            f"{copy_link}<pre><code>{code_content}</code></pre></td></tr>\n</table>\n"
        )
        return table

    def block_quote(self, text):
        return f"<inline_code>{text}</inline_code>"


markdown = create_markdown(
    renderer=CustomListRenderer(), plugins=["table", "task_lists"]
)
