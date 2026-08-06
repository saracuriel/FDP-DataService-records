"""
FAIR Wizard → RDF → GitHub proxy
─────────────────────────────────
Takes a JSON document (e.g. exported from the FAIR Wizard), renders it into
an RDF Turtle file using a Jinja2 template, and commits that file to a GitHub
repository.

Run locally:
    uvicorn main:app --reload --port 8001

Then open http://127.0.0.1:8001/docs to test interactively.
"""

import base64
import os
import re
import traceback
from urllib.parse import urlparse

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException

load_dotenv()  # reads a local .env file, if present, into os.environ
from fastapi.responses import JSONResponse, PlainTextResponse
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS

from services.template_service import render_turtle_template

app = FastAPI(
    title="FAIR Wizard → GitHub proxy",
    description="Converts FAIR Wizard JSON into RDF (Turtle) and pushes it to GitHub.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# ═══════════════════════════════════════════════════════════════════
# Environment configuration
# ═══════════════════════════════════════════════════════════════════
# These are read from environment variables so secrets never live in code.
# See .env.example for the full list and how to set them locally.

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")          # a GitHub personal access token
GITHUB_OWNER = os.getenv("GITHUB_OWNER")          # e.g. "your-github-username-or-org"
GITHUB_REPO = os.getenv("GITHUB_REPO")            # e.g. "my-metadata-records"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")


# ═══════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════
@app.get("/", summary="Health check")
async def health_check():
    return {"status": "ok", "message": "API is running. See /docs for interactive documentation."}


# ═══════════════════════════════════════════════════════════════════
# Helper: pull record_id + category out of the rendered RDF
# ═══════════════════════════════════════════════════════════════════
def _extract_record_info(rdf_text: str):
    """
    Parses the rendered Turtle and figures out what filename/folder to use
    in GitHub, based on the dcterms:identifier URI.

    Expects an identifier shaped like:
        https://example.org/records/<category>/<record_id>
    """
    g = Graph()
    try:
        g.parse(data=rdf_text, format="turtle")
    except Exception as e:
        raise HTTPException(400, f"Invalid RDF produced by template: {e}")

    uri_candidate = None
    for s, _, _ in g.triples((None, DCTERMS.identifier, None)):
        if isinstance(s, URIRef):
            uri_candidate = str(s)
            break

    if uri_candidate is None:
        raise HTTPException(400, "No dcterms:identifier subject URI found in the rendered RDF.")

    path_parts = [p for p in urlparse(uri_candidate).path.split("/") if p]
    if len(path_parts) < 2:
        raise HTTPException(400, f"URI '{uri_candidate}' doesn't have a /category/record_id structure.")

    filename = path_parts[-1]
    category = path_parts[-2]
    record_id = re.sub(r"\.ttl$", "", filename, flags=re.IGNORECASE)
    return record_id, category, uri_candidate


# ═══════════════════════════════════════════════════════════════════
# Helper: commit (create or update) the file in GitHub
# ═══════════════════════════════════════════════════════════════════
async def commit_rdf_to_github(client: httpx.AsyncClient, rdf_text: str):
    if not all([GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO]):
        raise HTTPException(500, "GitHub configuration missing. Set GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO.")

    record_id, category, uri_candidate = _extract_record_info(rdf_text)
    path = f"{category.rstrip('/')}/{record_id}.ttl"
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    try:
        # Check if the file already exists (need its sha to update it)
        sha = None
        pre = await client.get(url, headers=headers)
        if pre.status_code == 200:
            sha = pre.json().get("sha")
        elif pre.status_code not in (404,):
            raise HTTPException(500, f"GitHub preflight failed: {pre.text}")

        payload = {
            "message": f"Add/update RDF record '{record_id}' in '{category}'.",
            "content": base64.b64encode(rdf_text.encode()).decode(),
            "branch": GITHUB_BRANCH,
            **({"sha": sha} if sha else {}),
        }

        put = await client.put(url, headers=headers, json=payload)
        put.raise_for_status()
        commit_data = put.json()

        return {
            "status": "success",
            "action": "update" if sha else "create",
            "record_id": record_id,
            "category": category,
            "identifier": uri_candidate,
            "commit_url": commit_data.get("commit", {}).get("html_url"),
            "file_url": commit_data.get("content", {}).get("html_url"),
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(500, f"GitHub request failed: {e.response.text}")
    except httpx.HTTPError as e:
        raise HTTPException(500, f"GitHub request failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# Endpoint 1 — render only (great for testing the template quickly)
# ═══════════════════════════════════════════════════════════════════
@app.post(
    "/render/turtle",
    summary="Render JSON → Turtle (no GitHub push)",
    response_class=PlainTextResponse,
)
async def render_turtle(input_json: dict = Body(...)):
    """
    Use this endpoint while you're building/debugging your Jinja2 template.
    It just returns the RDF text so you can eyeball it before anything
    touches GitHub.
    """
    rdf_text = render_turtle_template(input_json)
    return PlainTextResponse(content=rdf_text, media_type="text/turtle")


# ═══════════════════════════════════════════════════════════════════
# Endpoint 2 — render + push to GitHub
# ═══════════════════════════════════════════════════════════════════
@app.post("/push", summary="Render JSON → Turtle → push to GitHub")
async def push_record(input_json: dict = Body(...)):
    """
    Full flow: takes FAIR Wizard JSON, renders it to Turtle, and commits
    the resulting .ttl file to the configured GitHub repository.
    """
    try:
        rdf_text = render_turtle_template(input_json)
        async with httpx.AsyncClient(timeout=20.0) as client:
            result = await commit_rdf_to_github(client, rdf_text)
        return JSONResponse(content=result, status_code=200)

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"status": "error", "message": e.detail})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Unexpected internal error: {e}"},
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
