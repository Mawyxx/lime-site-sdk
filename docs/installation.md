# Installation

## Requirements

- Python **3.10** or newer
- A running asyncio event loop when constructing `LimeSite`

## PyPI

```bash
pip install lime-sites-sdk
```

## Latest from GitHub

```bash
pip install git+https://github.com/Mawyxx/lime-site-sdk.git
```

## Development install

```bash
git clone https://github.com/Mawyxx/lime-site-sdk.git
cd lime-site-sdk
pip install -e ".[dev]"
```

Build documentation locally:

```bash
pip install -r docs/requirements.txt && pip install .
mkdocs serve -f docs/mkdocs.yml
```
