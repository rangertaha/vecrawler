# vecrawler

A generic web scraper for experimenting with **vector-based, RAG-like decision
making during the crawl**. The aim is to let embeddings guide the crawler at
runtime — scoring and prioritizing which links to follow by semantic relevance
rather than fixed rules alone.

It pairs [Scrapy](https://scrapy.org/) with
[Django](https://www.djangoproject.com/) as the foundation: crawlers are
configured entirely from the Django admin — domains, link-following rules,
throttling, and per-site LLM models — and a single generic spider turns each
configuration into a live crawl. Scraped pages are parsed into structured
records by a local [Ollama](https://ollama.com/) model and stored back in the
database, building the corpus that the vector-guided crawling logic draws on.

> **Status:** experimental / work in progress. The crawl, config, and LLM
> parsing foundation is in place; the vector-based crawl decisioning is the
> active area of exploration.

## Features

- **No-code crawler configuration.** Define a crawler, its allowed domains,
  seed URLs, and `CrawlSpider` link rules as rows in the admin — no spider code
  per site.
- **One generic spider.** `GenericSpider` reads a `Crawler` row and builds its
  `allowed_domains`, `start_urls`, `LinkExtractor` rules, and throttling at
  runtime.
- **LLM page parsing.** Each scraped page is sent to a local Ollama model that
  returns structured JSON (title, summary, image, topics). If Ollama is
  unreachable, the raw scraped fields are saved anyway.
- **Selector-based extraction.** Define extraction templates with CSS / XPath /
  regex properties to pull fields out of pages deterministically.
- **Built-in politeness.** Rotating User-Agents, AutoThrottle, randomized
  concurrency, RFC2616 HTTP caching, and `robots.txt` obedience are on by
  default.
- **Pipelines.** Items are cleaned, de-duplicated by URL, and persisted through
  a configurable Scrapy item pipeline.
- **CSV export.** Every crawl also writes a timestamped CSV to `output/`.

## Architecture

```
Django admin  ──►  Crawler config (Crawler, Domain, Rule, Item, Prop)
                          │
                          ▼
              runcrawler / scrapy crawl generic
                          │
                          ▼
                   GenericSpider  ──►  CleanFields ─► Duplicates ─► ItemSaver
                  (Scrapy crawl)                                       │
                                                          Ollama parse ┤
                                                                       ▼
                                                            item.Item (DB) + CSV
```

### Django apps

| App        | Purpose |
|------------|---------|
| `crawler`  | Crawler configuration: `Crawler`, `Domain`, `Rule`, and the extraction-template models `Item` (MPTT tree) + `Prop`. |
| `item`     | Scraped records — `Item.properties` is a JSON blob of extracted + LLM-parsed fields. |
| `pipeline` | `Pipeline` / `Transform` definitions for ordered post-processing steps. |

### Scrapy item pipeline

1. `CleanFieldsPipeline` — strips whitespace from string fields.
2. `DuplicatesPipeline` — drops items whose `url` was already seen this run.
3. `ItemSaverPipeline` — parses page content with Ollama and saves an `item.Item`.

### Project layout

```
vecrawler/
├── config/         # Django project (settings, urls, asgi/wsgi)
├── crawler/        # Crawler/Domain/Rule/Item/Prop models + runcrawler, createmetadata
├── item/           # Scraped records (item.Item)
├── pipeline/       # Pipeline/Transform post-processing definitions
├── vecrawler/      # Scrapy project — generic spider, pipelines, middlewares, settings
├── output/         # Timestamped CSV exports
├── manage.py       # Django entry point
└── scrapy.cfg      # Scrapy entry point
```

### Tech stack

| Area              | Current                          | Planned                          |
|-------------------|----------------------------------|----------------------------------|
| Crawling          | Scrapy                           | —                                |
| Config / admin    | Django + django-mptt             | —                                |
| Page parsing      | Ollama (local LLM)               | template-driven prompts          |
| Storage           | SQLite (Django ORM)              | —                                |
| LLM / embeddings  | scikit-learn                     | sentence-transformers (vectors)  |
| Task queue        | —                                | Celery + Redis                   |
| Search / analytics| —                                | Elasticsearch                    |

See the [Roadmap](#roadmap) for the planned work.

## Requirements

- Python 3.x
- [Ollama](https://ollama.com/) running locally (optional — crawls still save
  raw data without it)
- Dependencies in [`requirements.txt`](requirements.txt) (Django 5.2, Scrapy
  2.13, django-mptt, scikit-learn, etc.)

## Installation

```bash
git clone https://github.com/Rangertaha/vecrawler.git
cd vecrawler

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
```

## Usage

### 1. Configure a crawler

Start the admin and create a `Crawler` with at least one enabled `Domain`:

```bash
python manage.py runserver
# open http://127.0.0.1:8000/admin/
```

Optionally seed common web-metadata extraction templates (Open Graph, Twitter
Cards, schema.org, etc.):

```bash
python manage.py createmetadata
```

### 2. Run a crawl

```bash
# By crawler slug or name
python manage.py runcrawler my-site

# Override the seed URL without editing the config
python manage.py runcrawler my-site --start-url https://example.com/section

# Override any Scrapy setting (repeatable)
python manage.py runcrawler my-site -s CLOSESPIDER_ITEMCOUNT=20
```

Or invoke the spider directly through Scrapy:

```bash
scrapy crawl generic -a config=my-site
scrapy crawl generic -a config=my-site -a start_url=https://example.com/x
```

Results are written to the database (`item.Item`) and to a timestamped CSV in
`output/`.

### Ollama configuration

The page parser is configured per-crawler (the `Crawler.ollama_model` field) and
falls back to environment variables:

| Variable       | Default                  | Description                  |
|----------------|--------------------------|------------------------------|
| `OLLAMA_HOST`  | `http://localhost:11434` | Ollama API base URL          |
| `OLLAMA_MODEL` | `llama3.2`               | Model used to parse pages    |

## Roadmap

- [ ] Vector-based, RAG-like link prioritization during the crawl.
- [ ] Integrate **Redis** and **Celery** to distribute crawls and run
  post-processing (parsing, embedding, pipeline transforms) as async tasks.
- [ ] Build out the **Ollama parser** — drive prompts from the per-`Item` /
  `Prop` extraction templates instead of a single fixed prompt and hardcoded
  output keys.
- [ ] Integrate **Elasticsearch** for querying and analyzing scraped data.
- [ ] Improve the **data-cleaning pipeline** — go beyond whitespace stripping
  (normalize/validate fields, strip boilerplate, dedupe across runs).

## License

[MIT](LICENSE) © Rangertaha
