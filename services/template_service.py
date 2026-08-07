
"""
Loads the Jinja2 template and renders it with the incoming JSON as context.
"""
 
import os
import re
from jinja2 import Environment, FileSystemLoader
 
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
 
# Where the pushed .ttl files will actually be reachable once GitHub Pages
# is serving this repo. Falls back to the OSTrails default inside the
# template itself if this isn't set.
PAGES_BASE_URL = os.getenv("PAGES_BASE_URL")
 
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=False,
    lstrip_blocks=True,
    # The template uses {% do ... %} (e.g. to append to keyword_labels).
    # That tag only exists if this extension is enabled.
    extensions=["jinja2.ext.do"],
)
 
 
def _format_turtle(rendered: str) -> str:
    """
    Cleans up the raw Jinja2 output into consistently formatted Turtle:
      - every predicate line indented 4 spaces
      - every subject line (starts with '<') flush left
      - exactly one blank line inserted before each new subject block
      - no blank lines left behind by empty optional fields
      - @prefix lines untouched, flush left
    """
    lines = [line.strip() for line in rendered.split("\n")]
    lines = [line for line in lines if line != ""]  # drop all blank lines first
 
    out_lines = []
    seen_first_subject = False
    for line in lines:
        is_prefix_line = line.startswith("@prefix")
        is_subject_line = line.startswith("<") and not is_prefix_line
 
        if is_subject_line:
            if seen_first_subject:
                out_lines.append("")  # exactly one blank line before a new subject block
            seen_first_subject = True
            out_lines.append(line)
        elif is_prefix_line:
            out_lines.append(line)
        else:
            out_lines.append("    " + line)  # predicate/continuation line
 
    return "\n".join(out_lines).strip() + "\n"
 
 
def render_turtle_template(data: dict) -> str:
    """
    Renders templates/record.ttl.jinja2, passing the whole FAIR Wizard
    payload in as a single `GeneralMap` variable (matching what
    _mapping.json.j2 and record.ttl.jinja2 expect: map.GeneralMap.<field>),
    plus base_url so identifiers/landing pages point at wherever this repo
    is actually served from.
 
    Raw Jinja2 output has inconsistent indentation and stray blank lines
    (left behind whenever an optional field is empty for a given record),
    so _format_turtle() normalizes it afterward rather than hand-editing
    every {% if %}/{% endif %} pair in the template.
    """
    template = env.get_template("record.ttl.jinja2")
    kwargs = {"GeneralMap": data}
    rendered = template.render(**kwargs)
    return _format_turtle(rendered)