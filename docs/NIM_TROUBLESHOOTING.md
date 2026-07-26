# Local NIM Troubleshooting

Run:

```sh
python3 scripts/verify_runtime.py
```

If NIM shows `URLError`, check:

- The container is running.
- `.env` has `NVIDIA_NIM_BASE_URL=http://127.0.0.1:8001/v1` when Docker maps `-p 8001:8000`.
- `.env` has `NVIDIA_NIM_MODEL=nemotron-3-nano-omni-30b-a3b-reasoning`.
- `.env` has `NVIDIA_NIM_API_KEY` or `NGC_API_KEY`.
- Port `8001` is not already used by another service.

Quick probe:

```sh
curl "$NVIDIA_NIM_BASE_URL/models" -H "Authorization: Bearer $NVIDIA_NIM_API_KEY"
```
