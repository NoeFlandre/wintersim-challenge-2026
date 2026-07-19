# wintersim-challenge-2026

Initial project setup for the WinterSim Challenge 2026.

## Links

- GitHub repo: [NoeFlandre/wintersim-challenge-2026](https://github.com/NoeFlandre/wintersim-challenge-2026)
- Hugging Face bucket: [NoeFlandre/wintersim-challenge-2026](https://huggingface.co/buckets/NoeFlandre/wintersim-challenge-2026)
  - Hub path: `hf://buckets/NoeFlandre/wintersim-challenge-2026`

## Syncing the data folder with the bucket

The local `./data` directory is synced to the Hugging Face bucket with the
`huggingface_hub` CLI:

```bash
hf sync ./data hf://buckets/NoeFlandre/wintersim-challenge-2026
```

Run this from the project root to push or pull the latest contents of the
`./data` folder to the bucket.

## Local development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.
Pinned to Python 3.12 (see `.python-version`).

```bash
uv sync          # install dependencies into .venv
uv run python    # run python inside the project environment
```
