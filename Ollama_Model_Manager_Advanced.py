#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Ollama Model Admin GUI (Advanced, Fixed2)
# Changes in this version:
# - All subprocess.run/Popen calls use encoding="utf-8", errors="replace" to prevent Windows CP1252 UnicodeDecodeError.
# - Guard against None/empty outputs before calling .strip() in details view.
# - Minor robustness tweaks and logging.

import os
import sys
import re
import json
import time
import shutil
import queue
import platform
import tempfile
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog

import logging
LOGGER = logging.getLogger("OllamaAdmin")
LOGGER.setLevel(logging.INFO)
_console = logging.StreamHandler(stream=sys.stdout)
_console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
LOGGER.addHandler(_console)


class TkLogHandler(logging.Handler):
    def __init__(self, widget: scrolledtext.ScrolledText, level=logging.INFO):
        super().__init__(level)
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))

    def emit(self, record):
        msg = self.format(record)
        def append():
            try:
                self.widget.configure(state="normal")
                self.widget.insert(tk.END, msg + "\n")
                self.widget.see(tk.END)
                self.widget.configure(state="disabled")
            except tk.TclError:
                pass
        try:
            self.widget.after(0, append)
        except tk.TclError:
            pass


@dataclass
class OllamaModelInfo:
    name: str
    size: str
    modified: str
    id: str = ""
    family: str = ""
    quant: str = ""


class OllamaCLI:
    def __init__(self, binary_path: Optional[str] = None, timeout: int = 15):
        self.binary_path = binary_path or self._find_ollama()
        self.timeout = timeout

    @staticmethod
    def _find_ollama() -> Optional[str]:
        cmd = "ollama.exe" if sys.platform == "win32" else "ollama"
        p = shutil.which(cmd)
        if p:
            return p
        guesses = []
        if sys.platform == "win32":
            guesses = [
                Path(os.environ.get("LocalAppData", "")) / "Programs" / "Ollama" / "ollama.exe",
                Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
                Path.home() / "Ollama" / "ollama.exe",
            ]
        elif sys.platform == "darwin":
            guesses = [
                Path("/Applications/Ollama.app/Contents/MacOS/ollama"),
                Path("/opt/homebrew/bin/ollama"),
                Path("/usr/local/bin/ollama"),
            ]
        else:
            guesses = [
                Path("/usr/local/bin/ollama"),
                Path("/usr/bin/ollama"),
                Path.home() / ".local" / "bin" / "ollama",
            ]
        for g in guesses:
            if g.exists():
                return str(g)
        return None

    def ensure_available(self) -> Tuple[bool, str]:
        if not self.binary_path:
            return False, "Ollama binary not found. Install from https://ollama.com/download"
        try:
            res = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=self.timeout
            )
            if res.returncode == 0:
                return True, (res.stdout or "").strip()
            return False, (res.stderr or "Cannot execute ollama").strip()
        except Exception as e:
            return False, str(e)

    def server_running(self) -> bool:
        ok, _ = self.ensure_available()
        if not ok:
            return False
        try:
            subprocess.run(
                [self.binary_path, "list"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=5, check=True
            )
            return True
        except Exception:
            return False

    def list_models(self) -> List[OllamaModelInfo]:
        models: List[OllamaModelInfo] = []
        if not self.binary_path:
            return models
        # JSON if available
        try:
            res = subprocess.run(
                [self.binary_path, "list", "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=self.timeout, check=True
            )
            text = (res.stdout or "").strip()
            if text:
                data = json.loads(text)
                for item in data:
                    name = item.get("name", "")
                    size = item.get("size", "")
                    modified = item.get("modified", "")
                    _id = item.get("digest", "") or item.get("id", "")
                    family = name.split(":")[0] if ":" in name else name
                    quant = ""
                    if ":" in name:
                        variant = name.split(":", 1)[1]
                        m = re.search(r"q\d[^-]*", variant, flags=re.IGNORECASE)
                        if m:
                            quant = m.group(0)
                    models.append(OllamaModelInfo(name=name, size=size, modified=modified, id=_id, family=family, quant=quant))
                return models
        except Exception:
            pass
        # Fallback text parsing
        try:
            res = subprocess.run(
                [self.binary_path, "list"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=self.timeout, check=True
            )
            lines = [ln for ln in (res.stdout or "").splitlines() if ln.strip()]
            if len(lines) <= 1:
                return models
            for line in lines[1:]:
                parts = line.split()
                if len(parts) < 4:
                    continue
                name = parts[0]
                size = parts[1]
                modified = " ".join(parts[2:])
                family = name.split(":")[0] if ":" in name else name
                quant = ""
                if ":" in name:
                    variant = name.split(":", 1)[1]
                    m = re.search(r"q\d[^-]*", variant, flags=re.IGNORECASE)
                    if m:
                        quant = m.group(0)
                models.append(OllamaModelInfo(name=name, size=size, modified=modified, family=family, quant=quant))
            return models
        except Exception as e:
            LOGGER.error(f"Error listing models: {e}")
            return models

    def remove_model(self, model_name: str) -> Tuple[bool, str]:
        try:
            res = subprocess.run(
                [self.binary_path, "rm", model_name],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120
            )
            if res.returncode == 0:
                return True, (res.stdout or "Removed").strip()
            return False, (res.stderr or "Failed to remove").strip()
        except Exception as e:
            return False, str(e)

    def show_modelfile(self, model_name: str) -> Tuple[bool, Optional[str]]:
        try:
            res = subprocess.run(
                [self.binary_path, "show", model_name, "--modelfile"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30
            )
            if res.returncode == 0:
                return True, res.stdout  # may be empty string
            return False, res.stderr
        except Exception as e:
            return False, str(e)

    def show_parameters(self, model_name: str) -> Tuple[bool, Optional[str]]:
        try:
            res = subprocess.run(
                [self.binary_path, "show", model_name, "--parameters"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30
            )
            if res.returncode == 0:
                return True, res.stdout
            return False, res.stderr
        except Exception as e:
            return False, str(e)

    def pull_model(self, model_ref: str, on_progress=None) -> Tuple[bool, str]:
        try:
            proc = subprocess.Popen(
                [self.binary_path, "pull", model_ref],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1
            )
            last_percent = 0
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\r\n")
                if on_progress:
                    m = re.search(r"(\d{1,3})%\s*$", line)
                    if m:
                        try:
                            last_percent = max(last_percent, min(100, int(m.group(1))))
                        except Exception:
                            pass
                    on_progress(last_percent, line)
            code = proc.wait()
            if code == 0:
                return True, "Pull complete"
            return False, f"Pull failed (code {code})"
        except Exception as e:
            return False, str(e)

    def create_model_from_modelfile(self, name: str, modelfile_text: str, on_output=None) -> Tuple[bool, str]:
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".modelfile", encoding="utf-8") as f:
                f.write(modelfile_text)
                mf_path = f.name
            try:
                proc = subprocess.Popen(
                    [self.binary_path, "create", name, "-f", mf_path],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    bufsize=1
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    if on_output:
                        on_output(line.rstrip("\r\n"))
                code = proc.wait()
                if code == 0:
                    return True, "Model created"
                return False, f"Create failed (code {code})"
            finally:
                try:
                    os.unlink(mf_path)
                except Exception:
                    pass
        except Exception as e:
            return False, str(e)

    def run_model_once(self, model_name: str, prompt: str, on_stream=None) -> Tuple[bool, str]:
        try:
            proc = subprocess.Popen(
                [self.binary_path, "run", model_name, "--nowordwrap", prompt],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1
            )
            captured = []
            assert proc.stdout is not None
            for line in proc.stdout:
                captured.append(line)
                if on_stream:
                    on_stream(line)
            code = proc.wait()
            return (code == 0), "".join(captured)
        except Exception as e:
            return False, str(e)

    def stop_model(self, model_name: str) -> Tuple[bool, str]:
        try:
            res = subprocess.run(
                [self.binary_path, "stop", model_name],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=15
            )
            if res.returncode == 0:
                return True, (res.stdout or "Stopped").strip()
            return False, (res.stderr or "Failed to stop").strip()
        except Exception as e:
            return False, str(e)

    def prune(self) -> Tuple[bool, str]:
        try:
            proc = subprocess.Popen(
                [self.binary_path, "prune"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1
            )
            out = []
            assert proc.stdout is not None
            for line in proc.stdout:
                out.append(line)
            code = proc.wait()
            return (code == 0), "".join(out)
        except Exception as e:
            return False, str(e)


def path_to_file_uri(path_str: str) -> str:
    p = Path(path_str).resolve()
    return p.as_uri()


def is_probable_lora_safetensors(path_str: str) -> bool:
    try:
        p = Path(path_str)
        if "lora" in p.name.lower() or "adapter" in p.name.lower():
            return True
        size = p.stat().st_size
        return size < (2 * 1024 * 1024 * 1024)
    except Exception:
        return False


class ModelAdminApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ollama Model Admin (Advanced)")
        self.root.geometry("1150x840")

        self.cli = OllamaCLI()

        self.status_q = queue.Queue()
        self.progress_q = queue.Queue()
        self.log_q = queue.Queue()

        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self._start_queues_pump()
        self._startup_checks()

        self.refresh_models()

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_models = ttk.Frame(self.notebook, padding=10)
        self.tab_add = ttk.Frame(self.notebook, padding=10)
        self.tab_editor = ttk.Frame(self.notebook, padding=10)
        self.tab_logs = ttk.Frame(self.notebook, padding=10)
        self.tab_settings = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_models, text="Models")
        self.notebook.add(self.tab_add, text="Add")
        self.notebook.add(self.tab_editor, text="Modelfile Editor")
        self.notebook.add(self.tab_logs, text="Logs & Debug")
        self.notebook.add(self.tab_settings, text="Settings")

        self._build_models_tab()
        self._build_add_tab()
        self._build_editor_tab()
        self._build_logs_tab()
        self._build_settings_tab()

        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=10, pady=6)
        ttk.Progressbar(bottom, variable=self.progress_var, maximum=100).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(bottom, textvariable=self.status_var, width=60, anchor="e").pack(side=tk.RIGHT)

    def _build_models_tab(self):
        actions = ttk.Frame(self.tab_models)
        actions.pack(fill=tk.X, pady=6)
        ttk.Button(actions, text="Refresh", command=self.refresh_models).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Export Modelfile", command=self.export_modelfile_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Copy As...", command=self.copy_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Test Model", command=self.test_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Stop Model", command=self.stop_selected).pack(side=tk.LEFT, padx=4)

        columns = ("Name", "Size", "Quant", "Family", "Modified")
        self.tree = ttk.Treeview(self.tab_models, columns=columns, show="headings", height=18)
        for col, w in zip(columns, [380, 110, 90, 160, 300]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w)
        ysb = ttk.Scrollbar(self.tab_models, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        details = ttk.LabelFrame(self.tab_models, text="Details", padding=8)
        details.pack(fill=tk.BOTH, expand=True, pady=8)
        self.details_text = scrolledtext.ScrolledText(details, height=10, wrap=tk.WORD, state="disabled")
        self.details_text.pack(fill=tk.BOTH, expand=True)

    def _build_add_tab(self):
        source = ttk.LabelFrame(self.tab_add, text="Source", padding=8)
        source.pack(fill=tk.X)
        self.add_source_var = tk.StringVar(value="registry")
        ttk.Radiobutton(source, text="Ollama Registry (pull)", variable=self.add_source_var, value="registry",
                        command=self._toggle_add_panels).grid(row=0, column=0, sticky="w", padx=6)
        ttk.Radiobutton(source, text="HuggingFace (Modelfile)", variable=self.add_source_var, value="hf",
                        command=self._toggle_add_panels).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Radiobutton(source, text="Local File (GGUF / LoRA)", variable=self.add_source_var, value="local",
                        command=self._toggle_add_panels).grid(row=0, column=2, sticky="w", padx=6)

        self.add_container = ttk.Frame(self.tab_add)
        self.add_container.pack(fill=tk.BOTH, expand=True, pady=8)

        self.panel_registry = ttk.LabelFrame(self.add_container, text="Pull from Ollama Registry", padding=8)
        ttk.Label(self.panel_registry, text="Model ref (e.g. llama3:8b or mistral:instruct):").grid(row=0, column=0, sticky="w")
        self.pull_ref_var = tk.StringVar(value="llama3:8b")
        ttk.Entry(self.panel_registry, textvariable=self.pull_ref_var, width=40).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(self.panel_registry, text="Pull", command=self._pull_registry).grid(row=0, column=2, padx=6)

        self.panel_hf = ttk.LabelFrame(self.add_container, text="Create from HuggingFace Repo", padding=8)
        ttk.Label(self.panel_hf, text="HF Model ID (e.g. boun-tabi-LMG/TURNA-Enc-3-GGUF):").grid(row=0, column=0, sticky="w")
        self.hf_id_var = tk.StringVar()
        ttk.Entry(self.panel_hf, textvariable=self.hf_id_var, width=50).grid(row=0, column=1, sticky="w", padx=6, columnspan=2)
        ttk.Label(self.panel_hf, text="Base (FROM):").grid(row=1, column=0, sticky="w", pady=4)
        self.hf_base_var = tk.StringVar(value="llama3")
        base_combo = ttk.Combobox(self.panel_hf, textvariable=self.hf_base_var, width=18, state="readonly")
        base_combo["values"] = ["llama3", "llama2", "mistral", "mixtral", "phi", "gemma"]
        base_combo.grid(row=1, column=1, sticky="w")
        ttk.Label(self.panel_hf, text="New model name:").grid(row=2, column=0, sticky="w", pady=4)
        self.hf_newname_var = tk.StringVar(value="hf-model")
        ttk.Entry(self.panel_hf, textvariable=self.hf_newname_var, width=30).grid(row=2, column=1, sticky="w")
        self.hf_translation_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.panel_hf, text="Use translation-optimized template", variable=self.hf_translation_var).grid(
            row=3, column=0, columnspan=3, sticky="w"
        )
        ttk.Button(self.panel_hf, text="Generate Modelfile", command=self._hf_generate_modelfile).grid(row=4, column=0, pady=6)
        ttk.Button(self.panel_hf, text="Create Model", command=self._hf_create_model).grid(row=4, column=1, pady=6, padx=6)

        self.panel_local = ttk.LabelFrame(self.add_container, text="Create from Local File", padding=8)
        self.local_type_var = tk.StringVar(value="gguf")
        ttk.Radiobutton(self.panel_local, text="GGUF (MODEL)", variable=self.local_type_var, value="gguf").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(self.panel_local, text="SafeTensors (LoRA/ADAPTER)", variable=self.local_type_var, value="safetensors").grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(self.panel_local, text="Base (FROM):").grid(row=1, column=0, sticky="w", pady=4)
        self.local_base_var = tk.StringVar(value="llama3")
        local_base = ttk.Combobox(self.panel_local, textvariable=self.local_base_var, width=18, state="readonly")
        local_base["values"] = ["llama3", "llama2", "mistral", "mixtral", "phi", "gemma"]
        local_base.grid(row=1, column=1, sticky="w")
        ttk.Label(self.panel_local, text="Model/Adapter file:").grid(row=2, column=0, sticky="w")
        self.local_path_var = tk.StringVar()
        ttk.Entry(self.panel_local, textvariable=self.local_path_var, width=60).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Button(self.panel_local, text="Browse...", command=self._browse_local_file).grid(row=2, column=2)
        ttk.Label(self.panel_local, text="New model name:").grid(row=3, column=0, sticky="w", pady=4)
        self.local_newname_var = tk.StringVar(value="custom-model")
        ttk.Entry(self.panel_local, textvariable=self.local_newname_var, width=30).grid(row=3, column=1, sticky="w")
        ttk.Button(self.panel_local, text="Generate Modelfile", command=self._local_generate_modelfile).grid(row=4, column=0, pady=6)
        ttk.Button(self.panel_local, text="Create Model", command=self._local_create_model).grid(row=4, column=1, pady=6, padx=6)

        preview_box = ttk.LabelFrame(self.tab_add, text="Generated Modelfile Preview", padding=6)
        preview_box.pack(fill=tk.BOTH, expand=True)
        self.preview_text = scrolledtext.ScrolledText(preview_box, height=10, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        self._toggle_add_panels()

    def _build_editor_tab(self):
        ttk.Label(self.tab_editor, text="Edit a Modelfile and create a model from it").pack(anchor="w")
        self.editor_text = scrolledtext.ScrolledText(self.tab_editor, height=22, wrap=tk.WORD)
        self.editor_text.pack(fill=tk.BOTH, expand=True, pady=6)
        actions = ttk.Frame(self.tab_editor)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Load from file", command=self._editor_load_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Save to file", command=self._editor_save_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Create Model", command=self._editor_create_model).pack(side=tk.LEFT, padx=4)

    def _build_logs_tab(self):
        dbg_frame = ttk.Frame(self.tab_logs)
        dbg_frame.pack(fill=tk.X)
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            dbg_frame, text="Enable DEBUG logging (verbose)", variable=self.debug_var, command=self._toggle_debug
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(dbg_frame, text="Clear Log", command=self._clear_log).pack(side=tk.LEFT, padx=6)
        self.log_text = scrolledtext.ScrolledText(self.tab_logs, height=24, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=6)
        self.tk_log_handler = TkLogHandler(self.log_text, level=logging.INFO)
        LOGGER.addHandler(self.tk_log_handler)

    def _build_settings_tab(self):
        info = ttk.LabelFrame(self.tab_settings, text="Environment", padding=8)
        info.pack(fill=tk.X, pady=6)
        self.lbl_ollama = ttk.Label(info, text="Ollama: not found")
        self.lbl_ollama.pack(anchor="w")
        self.lbl_os = ttk.Label(info, text=f"OS: {platform.system()} {platform.release()} | Python: {platform.python_version()}")
        self.lbl_os.pack(anchor="w")
        btns = ttk.Frame(self.tab_settings)
        btns.pack(fill=tk.X, pady=8)
        ttk.Button(btns, text="Re-detect Ollama", command=self._detect_ollama).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Check Server", command=self._check_server).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Open Models Folder", command=self._open_models_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Prune Unused (cleanup)", command=self._prune_unused).pack(side=tk.LEFT, padx=4)

    def _start_queues_pump(self):
        def pump():
            try:
                while True:
                    try:
                        msg = self.status_q.get_nowait()
                        self.status_var.set(msg)
                    except queue.Empty:
                        break
                while True:
                    try:
                        prog = self.progress_q.get_nowait()
                        self.progress_var.set(prog)
                    except queue.Empty:
                        break
                while True:
                    try:
                        log = self.log_q.get_nowait()
                        LOGGER.info(log)
                    except queue.Empty:
                        break
            finally:
                self.root.after(100, pump)
        self.root.after(100, pump)

    def _startup_checks(self):
        ok, ver = self.cli.ensure_available()
        if ok:
            self.lbl_ollama.config(text=f"Ollama: {self.cli.binary_path} | {ver}")
        else:
            self.lbl_ollama.config(text=f"Ollama: NOT FOUND ({ver})")
            messagebox.showwarning("Ollama Not Found", ver)
        if not self.cli.server_running():
            messagebox.showwarning("Ollama Server", "Ollama server does not appear to be running. Start it before creating/pulling models.")

    # Models tab actions
    def refresh_models(self):
        try:
            self.status_var.set("Refreshing models...")
            self.progress_var.set(5)
        except Exception:
            pass
        try:
            self.tree.delete(*self.tree.get_children())
            self.details_text.configure(state="normal")
            self.details_text.delete(1.0, tk.END)
            self.details_text.configure(state="disabled")
        except Exception:
            pass
        def work():
            models = self.cli.list_models()
            def update():
                for m in models:
                    self.tree.insert("", "end", values=(m.name, m.size, m.quant, m.family, m.modified))
                try:
                    self.status_var.set(f"Found {len(models)} models")
                    self.progress_var.set(100 if models else 0)
                except Exception:
                    pass
            self.root.after(0, update)
        threading.Thread(target=work, daemon=True).start()

    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        model_name = self.tree.item(sel[0], "values")[0]
        self._load_model_details(model_name)

    def _load_model_details(self, model_name: str):
        self.status_var.set(f"Loading details for {model_name}...")
        def work():
            ok_mf, text_mf = self.cli.show_modelfile(model_name)
            ok_prm, text_prm = self.cli.show_parameters(model_name)
            parts = []
            if ok_mf and text_mf:
                parts.append("Modelfile:\n" + text_mf.strip())
            if ok_prm and text_prm:
                parts.append("Parameters:\n" + text_prm.strip())
            full = "\n\n".join(parts) if parts else "No details available."
            def update():
                self.details_text.configure(state="normal")
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(tk.END, full)
                self.details_text.configure(state="disabled")
                self.status_var.set("Ready")
            self.root.after(0, update)
        threading.Thread(target=work, daemon=True).start()

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Remove", "Select one or more models to remove.")
            return
        names = [self.tree.item(i, "values")[0] for i in sel]
        if not messagebox.askyesno("Confirm Delete", f"Remove {len(names)} model(s)?\n\n" + "\n".join(names)):
            return
        self.status_var.set("Removing...")
        self.progress_var.set(0)
        def work():
            total = len(names)
            for idx, name in enumerate(names, 1):
                ok, msg = self.cli.remove_model(name)
                self.log_q.put(f"Remove {name}: {'OK' if ok else 'FAIL'} - {msg}")
                pct = int((idx / total) * 100)
                self.progress_q.put(pct)
            self.root.after(0, self.refresh_models)
        threading.Thread(target=work, daemon=True).start()

    def export_modelfile_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Export", "Select a model to export its Modelfile.")
            return
        model_name = self.tree.item(sel[0], "values")[0]
        ok, modelfile = self.cli.show_modelfile(model_name)
        if not ok or not modelfile:
            messagebox.showerror("Export", f"Could not fetch Modelfile:\n{modelfile or 'No data'}")
            return
        path = filedialog.asksaveasfilename(
            title="Save Modelfile",
            defaultextension=".modelfile",
            filetypes=[("Modelfile", "*.modelfile"), ("Text", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            Path(path).write_text(modelfile, encoding="utf-8")
            messagebox.showinfo("Export", f"Saved to {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def copy_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Copy", "Select a model to copy.")
            return
        model_name = self.tree.item(sel[0], "values")[0]
        new_name = simpledialog.askstring("Copy Model", f"New name for copy of '{model_name}':", parent=self.root)
        if not new_name:
            return
        def work():
            ok, modelfile = self.cli.show_modelfile(model_name)
            if not ok or not modelfile:
                self.log_q.put(f"Export modelfile failed: {modelfile or 'No data'}")
                messagebox.showerror("Copy", f"Export failed: {modelfile or 'No data'}")
                return
            self.status_q.put(f"Creating '{new_name}'...")
            def on_out(line): self.log_q.put(line)
            ok2, msg = self.cli.create_model_from_modelfile(new_name, modelfile, on_output=on_out)
            self.log_q.put(msg)
            self.root.after(0, self.refresh_models)
        threading.Thread(target=work, daemon=True).start()

    def test_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Test", "Select a model to test.")
            return
        model_name = self.tree.item(sel[0], "values")[0]
        prompt = simpledialog.askstring("Test Model", "Enter a prompt:", initialvalue="Hello! Please introduce yourself.")
        if not prompt:
            return
        win = tk.Toplevel(self.root)
        win.title(f"Test: {model_name}")
        win.geometry("800x600")
        txt = scrolledtext.ScrolledText(win, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        status = ttk.Label(win, text="Running...")
        status.pack(side=tk.BOTTOM, pady=6)
        def work():
            def on_stream(line):
                win.after(0, lambda l=line: txt.insert(tk.END, l))
                win.after(0, lambda: txt.see(tk.END))
            ok, _ = self.cli.run_model_once(model_name, prompt, on_stream=on_stream)
            win.after(0, lambda: status.config(text="Done" if ok else "Error"))
        threading.Thread(target=work, daemon=True).start()

    def stop_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Stop", "Select a model to stop.")
            return
        model_name = self.tree.item(sel[0], "values")[0]
        self.status_var.set(f"Stopping {model_name}...")
        def work():
            ok, msg = self.cli.stop_model(model_name)
            self.log_q.put(f"stop {model_name}: {'OK' if ok else 'FAIL'} - {msg}")
            self.status_q.put("Ready")
        threading.Thread(target=work, daemon=True).start()

    def _toggle_add_panels(self):
        for w in self.add_container.winfo_children():
            w.pack_forget()
        src = self.add_source_var.get()
        if src == "registry":
            self.panel_registry.pack(fill=tk.X, pady=6)
        elif src == "hf":
            self.panel_hf.pack(fill=tk.X, pady=6)
        else:
            self.panel_local.pack(fill=tk.X, pady=6)

    def _pull_registry(self):
        ref = self.pull_ref_var.get().strip()
        if not ref:
            messagebox.showinfo("Pull", "Enter a model ref to pull.")
            return
        self.notebook.select(self.tab_logs)
        self.progress_var.set(0)
        self.status_var.set(f"Pulling {ref}...")
        def work():
            def on_progress(pct, line):
                self.progress_q.put(pct or 0)
                self.log_q.put(line)
            ok, msg = self.cli.pull_model(ref, on_progress=on_progress)
            self.log_q.put(msg)
            self.root.after(0, self.refresh_models)
            self.status_q.put("Ready")
            self.progress_q.put(100 if ok else 0)
        threading.Thread(target=work, daemon=True).start()

    def _hf_generate_modelfile(self):
        hf_id = self.hf_id_var.get().strip()
        base = self.hf_base_var.get().strip()
        if not hf_id:
            messagebox.showwarning("HF", "Enter HuggingFace model ID.")
            return
        lines = [
            f"FROM {base or 'llama3'}",
            f"HF_MODEL_ID {hf_id}",
            f"PARAMETER temperature 0.7",
            f"PARAMETER num_ctx 4096",
            'SYSTEM "You are a helpful assistant."',
        ]
        if self.hf_translation_var.get():
            lines += [
                'TEMPLATE """',
                '{{ .System }}',
                '',
                'Translate the following text to English:',
                '',
                '{{ .Prompt }}',
                '',
                'Translation:',
                '"""'
            ]
        modelfile = "\n".join(lines)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, modelfile)

    def _hf_create_model(self):
        name = self.hf_newname_var.get().strip()
        if not name:
            messagebox.showwarning("HF", "Enter a new model name.")
            return
        modelfile = self.preview_text.get(1.0, tk.END).strip()
        if not modelfile:
            self._hf_generate_modelfile()
            modelfile = self.preview_text.get(1.0, tk.END).strip()
        self.notebook.select(self.tab_logs)
        self.status_var.set(f"Creating {name}...")
        self.progress_var.set(0)
        def work():
            def on_out(line):
                self.log_q.put(line)
                m = re.search(r"(\d{1,3})%\s*$", line)
                if m:
                    try:
                        self.progress_q.put(int(m.group(1)))
                    except Exception:
                        pass
            ok, msg = self.cli.create_model_from_modelfile(name, modelfile, on_output=on_out)
            self.log_q.put(msg)
            self.root.after(0, self.refresh_models)
            self.status_q.put("Ready")
            self.progress_q.put(100 if ok else 0)
        threading.Thread(target=work, daemon=True).start()

    def _browse_local_file(self):
        t = self.local_type_var.get()
        types = [("All Files", "*.*")]
        if t == "gguf":
            types = [("GGUF Files", "*.gguf"), ("All Files", "*.*")]
        else:
            types = [("SafeTensor Files", "*.safetensors"), ("All Files", "*.*")]
        p = filedialog.askopenfilename(title=f"Select {t.upper()} file", filetypes=types)
        if p:
            self.local_path_var.set(p)
            stem = Path(p).stem
            suggestion = stem.split("-")[0].lower() or "custom-model"
            self.local_newname_var.set(suggestion)

    def _local_generate_modelfile(self):
        base = self.local_base_var.get().strip()
        path = self.local_path_var.get().strip()
        if not path:
            messagebox.showwarning("Local", "Select a file.")
            return
        try:
            file_uri = path_to_file_uri(path)
        except Exception as e:
            messagebox.showerror("Local", str(e))
            return
        lines = [f"FROM {base or 'llama3'}"]
        if self.local_type_var.get() == "gguf":
            if not path.lower().endswith(".gguf"):
                messagebox.showwarning("Local", "Selected file does not look like a GGUF model.")
            lines.append(f"MODEL {file_uri}")
        else:
            if not path.lower().endswith(".safetensors"):
                messagebox.showwarning("Local", "Selected file does not look like a .safetensors adapter.")
            if not is_probable_lora_safetensors(path):
                messagebox.showinfo(
                    "Adapter Warning",
                    "This .safetensors file may be full model weights, not a LoRA/adapter.\n"
                    "Ollama expects ADAPTER to be LoRA/adapter weights."
                )
            lines.append(f"ADAPTER {file_uri}")
        lines += [
            "PARAMETER temperature 0.7",
            "PARAMETER num_ctx 4096",
            'SYSTEM "You are a helpful assistant."'
        ]
        modelfile = "\n".join(lines)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, modelfile)

    def _local_create_model(self):
        name = self.local_newname_var.get().strip()
        if not name:
            messagebox.showwarning("Local", "Enter a new model name.")
            return
        modelfile = self.preview_text.get(1.0, tk.END).strip()
        if "ADAPTER " in modelfile and "FROM " in modelfile:
            base = ""
            for ln in modelfile.splitlines():
                if ln.startswith("FROM "):
                    base = ln.split(" ", 1)[1].strip()
                    break
            if base:
                installed = [m.name.split(":")[0] for m in self.cli.list_models()]
                if base not in installed:
                    if not messagebox.askyesno(
                        "Base Model Warning",
                        f"Base model '{base}' not found locally. Continue anyway?\n"
                        "You may need to pull/create the base before using the adapter."
                    ):
                        return
        self.notebook.select(self.tab_logs)
        self.status_var.set(f"Creating {name}...")
        self.progress_var.set(0)
        def work():
            def on_out(line):
                self.log_q.put(line)
                m = re.search(r"(\d{1,3})%\s*$", line)
                if m:
                    try:
                        self.progress_q.put(int(m.group(1)))
                    except Exception:
                        pass
            ok, msg = self.cli.create_model_from_modelfile(name, modelfile, on_output=on_out)
            self.log_q.put(msg)
            self.root.after(0, self.refresh_models)
            self.status_q.put("Ready")
            self.progress_q.put(100 if ok else 0)
        threading.Thread(target=work, daemon=True).start()

    def _editor_load_file(self):
        p = filedialog.askopenfilename(
            title="Open Modelfile",
            filetypes=[("Modelfile", "*.modelfile"), ("Text", "*.txt"), ("All files", "*.*")]
        )
        if not p:
            return
        try:
            text = Path(p).read_text(encoding="utf-8")
            self.editor_text.delete(1.0, tk.END)
            self.editor_text.insert(tk.END, text)
        except Exception as e:
            messagebox.showerror("Open", str(e))

    def _editor_save_file(self):
        p = filedialog.asksaveasfilename(
            title="Save Modelfile",
            defaultextension=".modelfile",
            filetypes=[("Modelfile", "*.modelfile"), ("Text", "*.txt"), ("All files", "*.*")]
        )
        if not p:
            return
        try:
            Path(p).write_text(self.editor_text.get(1.0, tk.END), encoding="utf-8")
            messagebox.showinfo("Save", f"Saved to {p}")
        except Exception as e:
            messagebox.showerror("Save", str(e))

    def _editor_create_model(self):
        text = self.editor_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showinfo("Create", "Editor is empty.")
            return
        name = simpledialog.askstring("Create Model", "Enter new model name:", parent=self.root)
        if not name:
            return
        self.notebook.select(self.tab_logs)
        self.status_var.set(f"Creating {name}...")
        self.progress_var.set(0)
        def work():
            def on_out(line):
                self.log_q.put(line)
                m = re.search(r"(\d{1,3})%\s*$", line)
                if m:
                    try:
                        self.progress_q.put(int(m.group(1)))
                    except Exception:
                        pass
            ok, msg = self.cli.create_model_from_modelfile(name, text, on_output=on_out)
            self.log_q.put(msg)
            self.root.after(0, self.refresh_models)
            self.status_q.put("Ready")
            self.progress_q.put(100 if ok else 0)
        threading.Thread(target=work, daemon=True).start()

    def _toggle_debug(self):
        if self.debug_var.get():
            LOGGER.setLevel(logging.DEBUG)
            self.tk_log_handler.setLevel(logging.DEBUG)
            _console.setLevel(logging.DEBUG)
            LOGGER.debug("Debug logging enabled")
        else:
            LOGGER.setLevel(logging.INFO)
            self.tk_log_handler.setLevel(logging.INFO)
            _console.setLevel(logging.INFO)
            LOGGER.info("Debug logging disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")

    def _detect_ollama(self):
        self.cli = OllamaCLI()
        ok, ver = self.cli.ensure_available()
        if ok:
            self.lbl_ollama.config(text=f"Ollama: {self.cli.binary_path} | {ver}")
        else:
            self.lbl_ollama.config(text=f"Ollama: NOT FOUND ({ver})")
            messagebox.showwarning("Ollama Not Found", ver)

    def _check_server(self):
        running = self.cli.server_running()
        messagebox.showinfo("Server", "Ollama server is running." if running else "Ollama server not running.")

    def _open_models_folder(self):
        if sys.platform == "win32":
            path = Path(os.environ.get("LocalAppData", "")) / "Ollama" / "models"
        elif sys.platform == "darwin":
            path = Path.home() / "Library" / "Application Support" / "Ollama"
        else:
            path = Path.home() / ".ollama"
        try:
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.call(["open", str(path)])
            else:
                subprocess.call(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("Open Folder", str(e))

    def _prune_unused(self):
        if not messagebox.askyesno("Prune", "Remove unused model blobs to free disk space?"):
            return
        if not self.cli.binary_path:
            messagebox.showerror("Prune", "Ollama not found.")
            return
        self.status_var.set("Pruning...")
        self.progress_var.set(0)
        self.notebook.select(self.tab_logs)
        def work():
            ok, out = self.cli.prune()
            self.log_q.put(out if out else ("OK" if ok else "Prune failed"))
            self.status_q.put("Ready")
            self.progress_q.put(100 if ok else 0)
        threading.Thread(target=work, daemon=True).start()


def main():
    # Optional: make Python itself prefer UTF-8 regardless of console code page.
    os.environ.setdefault("PYTHONUTF8", "1")
    root = tk.Tk()
    app = ModelAdminApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()