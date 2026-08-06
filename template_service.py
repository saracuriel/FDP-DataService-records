"""
Loads the Jinja2 template and renders it with the incoming JSON as context.
"""

import os
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    # StrictUndefined makes the template fail loudly if the JSON is missing
    # a field the template expects, instead of silently rendering "None".
    undefined=StrictUndefined,
)


def render_turtle_template(data: dict) -> str:
    """
    Renders templates/record.ttl.jinja2 using `data` as the context.
    """
    template = env.get_template("record.ttl.jinja2")
    return template.render(**data)
