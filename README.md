# AI

Some Python Scripts Related with AI — local-first tooling for running Ollama models and for keeping Python environments and packages under control on the machine that runs them.

Everything here is standard-library or thin-wrapper Python. Nothing calls a hosted API; the Ollama tools talk to a local Ollama install.

---

## Scripts

| Script | What it does |
|---|---|
| `Ollama_Model_Manager_Advanced.py` | The fuller Ollama model manager — browse, pull, inspect and remove local models |
| `ollama_model_manager.py` | The earlier, smaller version of the same tool (see *Notes*) |
| `Python_Environments.py` | Inspect and manage Python environments on the machine |
| `Python_Package_Manager_No_GUI.py` | Interactive terminal menu over `pip`: list, search, show details, and uninstall installed packages |

## Usage

Each script runs on its own:

```
python Ollama_Model_Manager_Advanced.py
python Python_Package_Manager_No_GUI.py
```

`Python_Package_Manager_No_GUI.py` presents a numbered menu and prompts before
uninstalling anything.

## Requirements

- **Python 3**
- **[Ollama](https://ollama.com/)** installed and running locally, for the two model managers
- `Python_Package_Manager_No_GUI.py` uses `pkg_resources` (from `setuptools`), which is deprecated on Python 3.12+ — it may warn or need `importlib.metadata` instead on newer interpreters

## Notes

- **Two Ollama managers are present.** `Ollama_Model_Manager_Advanced.py` (44 KB) supersedes `ollama_model_manager.py` (20 KB); the smaller one is kept as the earlier generation. Prefer the advanced one unless you specifically want the simpler tool.
- `Python_Package_Manager_No_GUI.py` **uninstalls packages from the interpreter that runs it.** Run it inside the environment you actually intend to modify, not a system Python.

## Related

- [SFT_Dataset_Generator_GUI](https://github.com/grasycho/SFT_Dataset_Generator_GUI) — builds fine-tuning datasets via local Ollama or the DeepSeek API
- [Github-Project-Inspector](https://github.com/grasycho/Github-Project-Inspector) — repository discovery with local-LLM semantic search
- [Python](https://github.com/grasycho/Python) — general-purpose Python utilities
