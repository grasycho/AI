import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
from pathlib import Path
import sys
import subprocess
from datetime import datetime

class CondaEnvManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Conda Environment Manager")
        self.root.geometry("1000x600")
        
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        self.create_widgets()
        self.refresh_env_list()

    def create_widgets(self):
        # Control panel
        control_frame = ttk.LabelFrame(self.main_frame, text="Controls", padding="5")
        control_frame.grid(row=0, column=0, pady=5, sticky="ew")
        
        ttk.Button(control_frame, text="Create New Env", command=self.create_conda_env).grid(row=0, column=0, padx=5)
        ttk.Button(control_frame, text="Delete Selected", command=self.delete_env).grid(row=0, column=1, padx=5)
        ttk.Button(control_frame, text="Refresh List", command=self.refresh_env_list).grid(row=0, column=2, padx=5)
        
        ttk.Label(control_frame, text="Conda Envs Dir:").grid(row=0, column=3, padx=5)
        self.conda_dir_var = tk.StringVar(value=self.get_conda_envs_dir())
        ttk.Entry(control_frame, textvariable=self.conda_dir_var, width=40).grid(row=0, column=4, padx=5)
        ttk.Button(control_frame, text="Browse", command=self.browse_conda_dir).grid(row=0, column=5, padx=5)

        # Environment list
        env_frame = ttk.LabelFrame(self.main_frame, text="Conda Environments", padding="5")
        env_frame.grid(row=1, column=0, pady=5, sticky="nsew")
        
        columns = ("Name", "Size (MB)", "Created", "Python Version", "Packages")
        self.tree = ttk.Treeview(env_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
            self.tree.column(col, width=120 if col == "Name" else 100)
            
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(env_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Details panel
        details_frame = ttk.LabelFrame(self.main_frame, text="Environment Details", padding="5")
        details_frame.grid(row=2, column=0, pady=5, sticky="ew")
        
        self.details_text = tk.Text(details_frame, height=8, width=80)
        self.details_text.grid(row=0, column=0, padx=5)
        
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.show_details)

    def get_conda_envs_dir(self):
        # Try to get from conda info, fallback to user-specified default
        try:
            result = subprocess.check_output(['conda', 'info', '--base'], text=True, stderr=subprocess.STDOUT).strip()
            envs_dir = os.path.join(result, 'envs')
            if os.path.exists(envs_dir):
                return envs_dir
        except:
            pass
        # Default to your specific Miniconda path
        default_path = r"C:\Users\97460\miniconda3\envs"
        if os.path.exists(default_path):
            return default_path
        return os.path.expanduser("~/miniconda3/envs")

    def get_env_info(self, env_path):
        size = sum(f.stat().st_size for f in env_path.rglob('*') if f.is_file()) / (1024 * 1024)  # Size in MB
        created = datetime.fromtimestamp(env_path.stat().st_ctime).strftime('%Y-%m-%d %H:%M')
        
        python_exe = env_path / 'python.exe' if sys.platform == 'win32' else env_path / 'bin' / 'python'
        version = "Unknown"
        if python_exe.exists():
            try:
                version = subprocess.check_output([str(python_exe), '--version'], text=True, stderr=subprocess.STDOUT).strip()
            except:
                pass
                
        pkg_count = 0
        try:
            pkgs = subprocess.check_output([str(python_exe), '-m', 'pip', 'list'], text=True, stderr=subprocess.STDOUT).splitlines()[2:]
            pkg_count = len(pkgs)
        except:
            pass
            
        return {
            'size': round(size, 2),
            'created': created,
            'version': version,
            'packages': pkg_count
        }

    def refresh_env_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        conda_dir = Path(self.conda_dir_var.get())
        if not conda_dir.exists():
            messagebox.showwarning("Warning", f"Conda envs directory {conda_dir} does not exist")
            return
            
        for env in conda_dir.iterdir():
            if env.is_dir() and ((env / 'python.exe').exists() or (env / 'bin' / 'python').exists()):
                info = self.get_env_info(env)
                self.tree.insert('', 'end', values=(
                    env.name, info['size'], info['created'], info['version'], info['packages']
                ))

    def create_conda_env(self):
        name = tk.simpledialog.askstring("Create Conda Env", "Enter environment name:")
        if name:
            try:
                subprocess.run(['conda', 'create', '-n', name, 'python', '-y'], check=True, text=True, stderr=subprocess.STDOUT)
                self.refresh_env_list()
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Failed to create conda environment:\n{e.output}")

    def delete_env(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an environment to delete")
            return
            
        env_name = self.tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete {env_name}?"):
            try:
                subprocess.run(['conda', 'env', 'remove', '-n', env_name], check=True, text=True, stderr=subprocess.STDOUT)
                self.refresh_env_list()
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Failed to delete environment:\n{e.output}")
            except Exception:
                # Fallback to manual deletion if conda command fails
                base_dir = Path(self.conda_dir_var.get())
                shutil.rmtree(base_dir / env_name, ignore_errors=True)
                self.refresh_env_list()

    def browse_conda_dir(self):
        directory = filedialog.askdirectory(initialdir=self.conda_dir_var.get())
        if directory:
            self.conda_dir_var.set(directory)
            self.refresh_env_list()

    def sort_column(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        if col == "Size (MB)":
            items.sort(key=lambda x: float(x[0]), reverse=True)
        elif col == "Packages":
            items.sort(key=lambda x: int(x[0]), reverse=True)
        else:
            items.sort(reverse=True)
            
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)

    def show_details(self, event):
        selected = self.tree.selection()
        if not selected:
            return
            
        env_name = self.tree.item(selected[0])['values'][0]
        base_dir = Path(self.conda_dir_var.get())
        env_path = base_dir / env_name
        
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, f"Environment: {env_name}\n")
        self.details_text.insert(tk.END, f"Path: {env_path}\n")
        
        python_exe = env_path / 'python.exe' if sys.platform == 'win32' else env_path / 'bin' / 'python'
        if python_exe.exists():
            try:
                packages = subprocess.check_output([str(python_exe), '-m', 'pip', 'list'], text=True, stderr=subprocess.STDOUT)
                self.details_text.insert(tk.END, "\nInstalled Packages:\n")
                self.details_text.insert(tk.END, packages)
            except subprocess.CalledProcessError as e:
                self.details_text.insert(tk.END, f"\nUnable to list packages: {e.output}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CondaEnvManager(root)
    root.mainloop()