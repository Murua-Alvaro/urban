# Loading the historical DENUE archive

The loader treats the ZIP as immutable input. It verifies the audited byte size and SHA-256 before extraction and writes a checksum marker beside the extracted cache. Colab, local Python and CI therefore use the same acquisition logic.

Run:

```bash
python scripts/denue/load.py
```

The default source is the raw GitHub URL on `data/denue-historico`. Set `--url` only for controlled mirrors. A changed archive will fail verification until its manifest and audited constants are intentionally updated.
