#!/usr/bin/env python
import pkg_resources
import subprocess
import sys

def list_packages(filter_str=None):
    """
    List installed Python packages.
    If a filter string is provided, only packages with names containing the substring (case-insensitive) will be shown.
    """
    packages = sorted([(p.project_name, p.version) for p in pkg_resources.working_set])
    if filter_str:
        packages = [p for p in packages if filter_str.lower() in p[0].lower()]
    if not packages:
        print("No packages found.")
        return
    for name, version in packages:
        print(f"{name}=={version}")

def show_details(package_name):
    """
    Show package details by calling 'pip show <package_name>'.
    """
    try:
        output = subprocess.check_output([sys.executable, "-m", "pip", "show", package_name], stderr=subprocess.STDOUT)
        print(output.decode())
    except subprocess.CalledProcessError as e:
        print(f"Error showing details for '{package_name}'.")
        print(e.output.decode())

def delete_package(package_name):
    """
    Uninstall the given package using pip.
    """
    confirmation = input(f"Are you sure you want to uninstall '{package_name}'? [y/N]: ")
    if confirmation.lower() != "y":
        print("Aborted deletion.")
        return
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", package_name, "-y"])
        print(f"Package '{package_name}' uninstalled successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error uninstalling '{package_name}'.")
        print(e)

def main():
    while True:
        print("\n=== Python Installed Projects Manager ===")
        print("1. List installed packages")
        print("2. Search installed packages")
        print("3. Show package details")
        print("4. Delete a package")
        print("5. Exit")
        choice = input("Enter your choice (1-5): ").strip()
        if choice == "1":
            print("\nInstalled Packages:")
            list_packages()
        elif choice == "2":
            substr = input("Enter search term: ").strip()
            print(f"\nPackages containing '{substr}':")
            list_packages(filter_str=substr)
        elif choice == "3":
            pkg_name = input("Enter package name to get details: ").strip()
            print(f"\nDetails for '{pkg_name}':")
            show_details(pkg_name)
        elif choice == "4":
            pkg_name = input("Enter package name to delete: ").strip()
            delete_package(pkg_name)
        elif choice == "5":
            print("Exiting.")
            break
        else:
            print("Invalid option, please try again.")

if __name__ == "__main__":
    main()