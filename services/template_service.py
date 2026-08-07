"""
Loads the Jinja2 template and renders it with the incoming JSON as context.
"""

import os
import re
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=False,
    lstrip_blocks=True,
    extensions=["jinja2.ext.do"],
)


def render_turtle_template(data: dict) -> str:
    """
    Renders templates/record.ttl.jinja2, passing the whole FAIR Wizard
    payload in as a single `GeneralMap` variable (matching what
    _mapping.json.j2 and record.ttl.jinja2 expect: map.GeneralMap.<field>),
    plus base_url so identifiers/landing pages point at wherever this repo
    is actually served from.
 
    trim_blocks=False keeps each triple on its own line (instead of gluing
    them together), but as a side effect leaves a blank line behind every
    time an optional field (License, VersionNotes, etc.) is empty for this
    record. We collapse those blank lines here rather than hand-editing
    every {% if %}/{% endif %} pair in the template.
    """
    template = env.get_template("record.ttl.jinja2")
    kwargs = {"GeneralMap": data}
    rendered = template.render(**kwargs)
 
    # Collapse any run of blank/whitespace-only lines down to nothing,
    # leaving a single newline between real content lines.
    rendered = re.sub(r"\n[ \t]*\n+", "\n", rendered)
    return rendered.strip() + "\n"
