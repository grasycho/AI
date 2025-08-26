import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
import subprocess
import threading
import os
import platform
import shlex
import webbrowser
import json

class OllamaModelManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama Model Manager")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#f5f5f5")
        # Changed button text color to black
        self.style.configure("TButton", padding=6, relief="flat", background="#0078d7", foreground="black")
        self.style.map("TButton", background=[("active", "#005fa3")])
        self.style.configure("TLabel", background="#f5f5f5", font=("Segoe UI", 10))
        
        # Setup main container with padding
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and description
        title_frame = ttk.Frame(self.main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(title_frame, text="Ollama Model Manager", font=("Segoe UI", 16, "bold"))
        title_label.pack(side=tk.LEFT, pady=5)
        
        # Create a frame for the model list and output
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Model list with custom header
        list_header = ttk.Frame(content_frame)
        list_header.pack(fill=tk.X)
        
        list_title = ttk.Label(list_header, text="Available Models", font=("Segoe UI", 12, "bold"))
        list_title.pack(side=tk.LEFT, pady=5)
        
        # Create Treeview for models
        columns = ("Name", "Blob", "Size", "Modified")
        self.model_tree = ttk.Treeview(content_frame, columns=columns, show="headings", selectmode="browse")
        
        # Configure column headings
        self.model_tree.heading("Name", text="Name", command=lambda: self.sort_treeview("Name", False))
        self.model_tree.heading("Blob", text="Blob")
        self.model_tree.heading("Size", text="Size", command=lambda: self.sort_treeview("Size", False))
        self.model_tree.heading("Modified", text="Modified", command=lambda: self.sort_treeview("Modified", False))
        
        # Configure column widths
        self.model_tree.column("Name", width=150)
        self.model_tree.column("Blob", width=150)
        self.model_tree.column("Size", width=100)
        self.model_tree.column("Modified", width=150)
        
        # Add scrollbar to treeview
        tree_scroll = ttk.Scrollbar(content_frame, orient="vertical", command=self.model_tree.yview)
        self.model_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.model_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind event to treeview selection
        self.model_tree.bind("<Double-1>", self.on_model_double_click)
        self.model_tree.bind("<<TreeviewSelect>>", self.on_model_select)
        
        # Command output section
        output_frame = ttk.LabelFrame(self.main_frame, text="Command Output")
        output_frame.pack(fill=tk.X, expand=False, pady=5)
        
        self.output_box = scrolledtext.ScrolledText(output_frame, width=50, height=10, wrap=tk.WORD)
        self.output_box.pack(fill=tk.X, expand=False, padx=5, pady=5)
        
        # Action buttons frame
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Left side buttons (primary actions)
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        self.refresh_button = ttk.Button(left_buttons, text="Refresh Models", command=self.refresh_models)
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Right side buttons (model actions)
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        self.model_actions_buttons = []
        
        self.delete_button = ttk.Button(right_buttons, text="Delete Model", command=self.on_delete)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.model_actions_buttons.append(self.delete_button)
        
        self.show_in_explorer_button = ttk.Button(right_buttons, text="Show in Explorer", 
                                                command=self.show_in_explorer)
        self.show_in_explorer_button.pack(side=tk.LEFT, padx=5)
        self.model_actions_buttons.append(self.show_in_explorer_button)
        
        self.export_button = ttk.Button(right_buttons, text="Export Model", command=self.export_model)
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.model_actions_buttons.append(self.export_button)
        
        self.run_button = ttk.Button(right_buttons, text="Run Model", command=self.run_model)
        self.run_button.pack(side=tk.LEFT, padx=5)
        self.model_actions_buttons.append(self.run_button)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Initialize model actions buttons as disabled
        self.toggle_model_buttons(False)
        
        # Sorting information
        self.sort_column = None
        self.sort_reverse = {}
        for col in columns:
            self.sort_reverse[col] = False
        
        # Initially load models
        self.selected_model = None
        self.model_data = {}
        self.refresh_models()
    
    def sort_treeview(self, column, toggle=True):
        """Sort treeview by column"""
        if toggle:
            if self.sort_column == column:
                self.sort_reverse[column] = not self.sort_reverse[column]
            else:
                self.sort_column = column
        else:
            self.sort_column = column
            
        items = [(self.model_tree.set(item, column), item) for item in self.model_tree.get_children('')]
        
        if column == "Size":
            def size_to_bytes(size_str):
                if not size_str:
                    return 0
                size_str = size_str.lower()
                multipliers = {
                    'b': 1,
                    'kb': 1024,
                    'mb': 1024**2,
                    'gb': 1024**3,
                    'tb': 1024**4
                }
                try:
                    # Check if the size_str ends with a recognized unit
                    for unit in multipliers:
                        if size_str.endswith(unit):
                            num = float(size_str[:-len(unit)])
                            return num * multipliers[unit]
                    return float(size_str)
                except (ValueError, TypeError):
                    return 0
                    
            items = [(size_to_bytes(item[0]), item[1]) for item in items]
        
        items.sort(reverse=self.sort_reverse[column])
        
        for index, (val, item) in enumerate(items):
            self.model_tree.move(item, '', index)
        
        arrow = "▼" if self.sort_reverse[column] else "▲"
        for col in self.model_tree["columns"]:
            header_text = col
            if col == column:
                header_text += f" {arrow}"
            self.model_tree.heading(col, text=header_text)
    
    def toggle_model_buttons(self, enabled=True):
        """Enable or disable model action buttons based on selection state"""
        state = "normal" if enabled else "disabled"
        for button in self.model_actions_buttons:
            button.configure(state=state)
    
    def refresh_models(self):
        """Refreshes the list of Ollama models"""
        self.status_var.set("Refreshing model list...")
        threading.Thread(target=self._refresh_models_thread, daemon=True).start()
    
    def _refresh_models_thread(self):
        """Background thread to refresh models"""
        try:
            output = self.run_command(["ollama", "list"])
        except Exception as e:
            output = f"Error: {str(e)}"
            
        models = {}
        tree_items = []
        lines = output.strip().split("\n")
        # Expect header: Name, Blob, Size, Modified
        # Assume each model line has at least 5 tokens:
        # [name tokens...] [blob] [size] [modified date] [modified time]
        if len(lines) > 1:
            for i in range(1, len(lines)):
                line = lines[i].strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                # Last two tokens form Modified
                modified = parts[-2] + " " + parts[-1]
                size = parts[-3]
                blob = parts[-4]
                name = " ".join(parts[:-4])
                model_key = f"{name}:{blob}"
                models[model_key] = {
                    "name": name,
                    "blob": blob,
                    "size": size,
                    "modified": modified,
                    "full_name": model_key
                }
                tree_items.append((name, blob, size, modified, model_key))
        
        self.root.after(0, lambda: self.update_model_list(output, models, tree_items))
    
    def update_model_list(self, raw_output, models, tree_items):
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(tk.END, raw_output)
        for item in self.model_tree.get_children():
            self.model_tree.delete(item)
            
        self.model_data = models
        for (name, blob, size, modified, model_key) in tree_items:
            self.model_tree.insert("", tk.END, values=(name, blob, size, modified), tags=(model_key,))
        
        count = len(models)
        if count:
            self.status_var.set(f"Found {count} models")
        else:
            self.status_var.set("No models found")
        
        if self.sort_column:
            self.sort_treeview(self.sort_column, False)
    
    def on_model_select(self, event):
        """Handle model selection in treeview"""
        selection = self.model_tree.selection()
        if not selection:
            self.toggle_model_buttons(False)
            self.selected_model = None
            return
            
        item_id = selection[0]
        values = self.model_tree.item(item_id, "values")
        
        if not values or len(values) < 2:
            return
            
        name, blob = values[0], values[1]
        model_key = f"{name}:{blob}"
        
        self.selected_model = self.model_data.get(model_key)
        
        if self.selected_model:
            self.toggle_model_buttons(True)
            self.status_var.set(f"Selected model: {model_key}")
    
    def on_model_double_click(self, event):
        """Handle double-click on model (run the model)"""
        if self.selected_model:
            self.run_model()
    
    def on_delete(self):
        """Deletes the selected model after confirmation"""
        if not self.selected_model:
            messagebox.showwarning("No Selection", "Please select a model to delete.")
            return
            
        model_name = self.selected_model.get("full_name", "")
        if not model_name:
            return
            
        confirm = messagebox.askyesno("Confirm Delete", 
                                    f"Are you sure you want to delete model '{model_name}'?")
        if confirm:
            self.status_var.set(f"Deleting model {model_name}...")
            threading.Thread(target=self._delete_model_thread, args=(model_name,), daemon=True).start()
    
    def _delete_model_thread(self, model_name):
        """Background thread to delete a model"""
        result = self.run_command(["ollama", "delete", model_name])
        self.root.after(0, lambda: self.output_box.delete(1.0, tk.END))
        self.root.after(0, lambda: self.output_box.insert(tk.END, result))
        self.root.after(0, lambda: messagebox.showinfo("Delete", f"Delete command completed:\n{result}"))
        self.root.after(100, self.refresh_models)
    
    def show_in_explorer(self):
        """Opens file explorer to the Ollama model directory"""
        if not self.selected_model:
            messagebox.showwarning("No Selection", "Please select a model first.")
            return
            
        system = platform.system()
        home_dir = os.path.expanduser("~")
        ollama_dir = None
        
        if system == "Windows":
            # New expected folder path, e.g. "C:\Users\{username}\.ollama\models\blobs"
            candidate = os.path.join(home_dir, ".ollama", "models", "blobs")
            if os.path.exists(candidate):
                ollama_dir = candidate
        elif system == "Darwin":  # macOS
            candidate = os.path.join(home_dir, ".ollama", "models", "blobs")
            if os.path.exists(candidate):
                ollama_dir = candidate
        else:  # Linux and others
            candidate = os.path.join(home_dir, ".ollama", "models", "blobs")
            if os.path.exists(candidate):
                ollama_dir = candidate
        
        if not ollama_dir:
            messagebox.showwarning("Directory Not Found", 
                                  f"Ollama models directory not found at expected locations.")
            return
            
        try:
            if system == "Windows":
                subprocess.run(["explorer", ollama_dir])
            elif system == "Darwin":
                subprocess.run(["open", ollama_dir])
            else:
                subprocess.run(["xdg-open", ollama_dir])
                
            self.status_var.set(f"Opened Ollama models directory: {ollama_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file explorer:\n{str(e)}")
    
    def export_model(self):
        """Export the selected model to a file"""
        if not self.selected_model:
            messagebox.showwarning("No Selection", "Please select a model to export.")
            return
            
        model_name = self.selected_model.get("full_name", "")
        if not model_name:
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".tar",
            filetypes=[("TAR files", "*.tar"), ("All files", "*.*")],
            title="Export Ollama Model",
            initialfile=f"{model_name.replace(':', '-')}.tar"
        )
        
        if not file_path:
            return
            
        self.status_var.set(f"Exporting model {model_name} to {file_path}...")
        threading.Thread(target=self._export_model_thread, args=(model_name, file_path), daemon=True).start()
    
    def _export_model_thread(self, model_name, file_path):
        """Background thread to export a model"""
        result = self.run_command(["ollama", "export", model_name, file_path])
        self.root.after(0, lambda: self.output_box.delete(1.0, tk.END))
        self.root.after(0, lambda: self.output_box.insert(tk.END, result))
        
        if os.path.exists(file_path):
            self.root.after(0, lambda: messagebox.showinfo("Export Successful", 
                                                         f"Model exported to:\n{file_path}"))
            self.root.after(0, lambda: self.status_var.set(f"Model exported to: {file_path}"))
        else:
            self.root.after(0, lambda: messagebox.showerror("Export Failed", 
                                                          f"Failed to export model. See output for details."))
            self.root.after(0, lambda: self.status_var.set("Export failed"))
    
    def run_model(self):
        """Run the selected model in a chat interface"""
        if not self.selected_model:
            messagebox.showwarning("No Selection", "Please select a model to run.")
            return
            
        model_name = self.selected_model.get("full_name", "")
        if not model_name:
            return
        
        chat_window = tk.Toplevel(self.root)
        chat_window.title(f"Chat with {model_name}")
        chat_window.geometry("600x500")
        chat_window.minsize(500, 400)
        
        chat_frame = ttk.Frame(chat_window, padding="10")
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        history_frame = ttk.LabelFrame(chat_frame, text="Conversation")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        chat_display = scrolledtext.ScrolledText(history_frame, wrap=tk.WORD, state=tk.DISABLED)
        chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill=tk.X)
        
        prompt_entry = ttk.Entry(input_frame)
        prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def send_message():
            prompt = prompt_entry.get().strip()
            if not prompt:
                return
                
            chat_display.config(state=tk.NORMAL)
            chat_display.insert(tk.END, f"You: {prompt}\n\n")
            chat_display.see(tk.END)
            chat_display.config(state=tk.DISABLED)
            
            prompt_entry.delete(0, tk.END)
            
            threading.Thread(target=query_model, 
                           args=(model_name, prompt, chat_display, chat_window), 
                           daemon=True).start()
        
        def query_model(model, prompt, display, window):
            window_title_processing = f"Chat with {model} (Processing...)"
            self.root.after(0, lambda: window.title(window_title_processing))
            try:
                cmd = ["ollama", "run", model, prompt]
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    universal_newlines=True
                )
                response = ""
                for line in process.stdout:
                    response += line
                final_response = response.strip()
                self.root.after(0, lambda: self.append_chat_message(display, model, final_response))
                self.root.after(0, lambda: window.title(f"Chat with {model}"))
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                self.root.after(0, lambda: self.append_chat_message(display, model, error_msg))
                self.root.after(0, lambda: window.title(f"Chat with {model} (Error)"))
        
        send_button = ttk.Button(input_frame, text="Send", command=send_message)
        send_button.pack(side=tk.RIGHT)
        
        prompt_entry.bind("<Return>", lambda event: send_message())
        prompt_entry.focus_set()
    
    def append_chat_message(self, display, sender, message):
        display.config(state=tk.NORMAL)
        display.insert(tk.END, f"{sender}: {message}\n\n")
        display.see(tk.END)
        display.config(state=tk.DISABLED)
    
    def run_command(self, command_args):
        """Runs a command given as a list and returns its output as text."""
        try:
            output = subprocess.check_output(command_args, stderr=subprocess.STDOUT)
            return output.decode()
        except subprocess.CalledProcessError as e:
            return e.output.decode()

def main():
    root = tk.Tk()
    app = OllamaModelManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
```‘‘‘‘

This version displays blob hashes instead of tags, uses the correct size information, and for Windows opens the directory at ".ollama\models\blobs" (which in your example is under your user home directory).