# FAIR Wizard → RDF → GitHub proxy

Takes JSON (e.g. from the FAIR Wizard), renders it into RDF Turtle with a
Jinja2 template, and commits the `.ttl` file to a GitHub repo.

## 1. Install

```bash
git clone https://github.com/saracuriel/FDP-DataService-records/
cd FDP-DataService-records
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure GitHub access

1. Create a GitHub **personal access token**:
   Settings → Developer settings → Personal access tokens →
   Fine-grained token → give it **Contents: Read and write** on the target repo only.
2. Copy `.env.example` to `.env` and fill in `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`.
   `.env` is just read by `python-dotenv` at startup — never commit it.

## 3. Run it

```bash
uvicorn main:app --reload --port 8001
```

Open **http://127.0.0.1:8001/docs** — FastAPI's auto-generated Swagger UI.
This is your test client; no need to write curl commands or a frontend.

## 4. Test the template first (no GitHub involved)

In `/docs`, expand `POST /render/turtle`, click "Try it out", and paste JSON like:

```json
{
  "record_id": "my-tool-001",
  "category": "software",
  "title": "My Awesome Tool",
  "description": "A tool that does FAIR things.",
  "creators": ["Ada Lovelace", "Alan Turing"],
  "keywords": ["fair", "metadata", "rdf"],
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "created_date": "2026-08-06"
}
```

Execute — you get back plain-text Turtle. Check it looks right before touching GitHub.

## 5. Push to GitHub

Same payload, but call `POST /push` instead. On success you get back the
commit URL and file URL so you can click straight through to the new file
in your repo.

## 6. Adapting the template to your real FAIR Wizard export

Open `templates/record.ttl.jinja2`. Every `{{ field }}` there must exist as a
key in the JSON you send in (the service uses `StrictUndefined`, so it fails
loudly — not silently — if a field is missing, which is what you want while debugging).

Steps to adapt:

1. Export a real sample JSON from the FAIR Wizard.
2. Compare its field names against the template's `{{ ... }}` placeholders.
3. Rename placeholders to match, or rename keys in a small pre-processing
   step in `services/template_service.py` before calling `template.render()`.
4. Add/remove RDF predicates in the template to match whatever schema your
   GitHub repo's records are expected to follow (DCAT, schema.org, your own
   ontology, etc.).
5. Re-test with `/render/turtle` until the output is exactly the RDF shape you want.

## How the GitHub path/filename is decided

`main.py`'s `_extract_record_info()` looks for a `dcterms:identifier` triple
whose subject is a URI shaped like:

```
https://example.org/records/<category>/<record_id>
```

and uses `<category>/<record_id>.ttl` as the path in the repo. If your
records don't naturally have that shape, you can instead pass `record_id`
and `category` explicitly in the JSON and build the GitHub path from those
directly — happy to adjust the code for that if it fits your case better.

## Project structure

```
fair-proxy/
├── main.py                       # FastAPI app: /, /render/turtle, /push
├── services/
│   └── template_service.py       # loads + renders the Jinja2 template
├── templates/
│   └── record.ttl.jinja2         # ← edit this to match your JSON schema
├── requirements.txt
├── .env.example
└── README.md
```
