#!/usr/bin/env python3
"""
An efficient wrapper script for matterport-dl.py that:
1. Checks if already running in the correct virtual environment
2. Sets up a virtual environment if needed
3. Installs requirements from requirements.txt only if modules are missing
4. Checks Python version (must be 3.12+)
5. Checks for the existence of matterport-dl.py
6. Warns if _matterport_interactive.py is missing but stdin is a TTY
7. Runs matterport-dl.py with any arguments passed to this script
"""
import os
import sys
import subprocess
import platform
import venv
import importlib.util
import importlib.metadata
import re
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL) #quiet control + c

# Set debug flag if --debug is in the command line arguments
DEBUG = "--debug" in sys.argv

# Environment variable to store external Python version
EXTERNAL_PY_VERSION_VAR = "EXTERNAL_PY_VERSION"

# Fallback mapping for packages not yet installed
# This is only used when a package isn't installed yet, so we can't query the system
FALLBACK_PACKAGE_TO_IMPORT_NAME = {
    "Pillow": "PIL",
    "curl-cffi": "curl_cffi"
}

def debug_print(message, is_error=False):
    """Print debug messages to stderr, only if not an error message and DEBUG is True."""
    if is_error or DEBUG:
        print(message, file=sys.stderr)

def get_package_to_import_mapping():
    """
    Dynamically build a mapping from package names to their import names.

    This uses importlib.metadata.packages_distributions() which is available in Python 3.10+
    to get a reverse mapping of module names to their distribution names, then inverts it.
    """
    package_to_import = {}

    try:
        # Get the mapping of module names to their distribution packages
        module_to_dist = importlib.metadata.packages_distributions()

        # Invert the mapping: for each module, associate its distribution with it
        for module_name, dist_names in module_to_dist.items():
            for dist_name in dist_names:
                # Use lowercase for case-insensitive matching
                package_to_import[dist_name.lower()] = module_name
    except Exception as e:
        debug_print(f"Warning: Could not build package-to-import mapping: {e}", is_error=True)

    # Add fallbacks for special cases and packages not yet installed
    for pkg, mod in FALLBACK_PACKAGE_TO_IMPORT_NAME.items():
        if pkg.lower() not in package_to_import:
            package_to_import[pkg.lower()] = mod

    return package_to_import

def normalize_path(path):
    """Normalize path for case-insensitive, slash-agnostic comparison."""
    return os.path.normcase(os.path.normpath(path))

def check_python_version():
    """Check if Python version is 3.12 or higher."""
    version_info = sys.version_info
    if version_info.major < 3 or (version_info.major == 3 and version_info.minor < 12):
        debug_print(f"Error: Python 3.12 or higher is required. You are using Python {platform.python_version()}", is_error=True)
        sys.exit(1)

def check_required_files(script_dir):
    """Check for the existence of required files."""
    # Check if matterport-dl.py exists
    matterport_script = os.path.join(script_dir, "matterport-dl.py")
    if not os.path.exists(matterport_script):
        debug_print(f"Error: matterport-dl.py not found in {script_dir}", is_error=True)
        sys.exit(1)

    # Check if _matterport_interactive.py exists, warn if not but stdin is a TTY
    interactive_script = os.path.join(script_dir, "_matterport_interactive.py")
    if not os.path.exists(interactive_script) and sys.stdin.isatty():
        debug_print("Warning: _matterport_interactive.py not found. Interactive mode will not be available.", is_error=True)

def setup_venv(script_dir):
    """Set up a virtual environment if it doesn't exist."""
    venv_dir = os.path.join(script_dir, "venv")

    # Check if venv already exists
    if os.path.exists(venv_dir) and os.path.exists(os.path.join(venv_dir, "Scripts" if sys.platform == "win32" else "bin")):
        return venv_dir

    debug_print(f"Setting up virtual environment in {venv_dir}...")
    venv.create(venv_dir, with_pip=True)
    return venv_dir

def is_in_correct_venv(script_dir):
    """Check if we're already running in the correct virtual environment."""
    expected_venv_path = normalize_path(os.path.join(script_dir, "venv"))
    current_venv_path = sys.prefix
    return current_venv_path and normalize_path(current_venv_path) == expected_venv_path

def run_in_venv(script_dir, venv_dir):
    """Re-run this script in the virtual environment."""
    # Determine path to python executable in the virtual environment
    python_executable = os.path.join(
        venv_dir,
        "Scripts" if sys.platform == "win32" else "bin",
        "python"
    )

    script_path = os.path.abspath(__file__)

    debug_print(f"Restarting in virtual environment python executable: {python_executable} ...")
    try:
        # Pass all command line arguments to the new process
        process = subprocess.run([python_executable, script_path] + sys.argv[1:])
        sys.exit(process.returncode)
    except Exception as e:
        debug_print(f"Error running script in virtual environment: {e}", is_error=True)
        sys.exit(1)

def parse_requirements(requirements_file):
    """Parse requirements.txt to get module names and versions."""
    required_modules = {}

    with open(requirements_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Handle platform-specific dependencies
            if ';' in line:
                line, condition = line.split(';', 1)
                # Very basic condition evaluation - only handle platform conditions
                if 'platform_system' in condition:
                    if 'Windows' in condition and sys.platform != 'win32':
                        continue
                    elif 'Linux' in condition and sys.platform != 'linux':
                        continue
                    elif 'Darwin' in condition and sys.platform != 'darwin':
                        continue
                line = line.strip()

            # Handle version specifications
            if '==' in line:
                module_name, version = line.split('==', 1)
                required_modules[module_name.strip()] = version.strip()
            elif '>=' in line:
                module_name, version = line.split('>=', 1)
                required_modules[module_name.strip()] = version.strip()
            else:
                required_modules[line] = None

    return required_modules

def is_module_installed(module_name, package_to_import_mapping):
    """
    Check if a module is installed, using dynamic package-to-import mapping.

    First tries the mapping from packages_distributions, then falls back to
    common transformations and special cases.
    """
    # Try direct module import (for when package name matches import name)
    direct_import = module_name.replace('-', '_')
    if importlib.util.find_spec(direct_import) is not None:
        return True

    # Try using our dynamic mapping
    import_name = package_to_import_mapping.get(module_name.lower())
    if import_name and importlib.util.find_spec(import_name) is not None:
        return True

    # As a last resort, try some common transformations
    # 1. Convert to lowercase
    if importlib.util.find_spec(module_name.lower()) is not None:
        return True

    # 2. Replace hyphens with underscores in lowercase name
    if '-' in module_name and importlib.util.find_spec(module_name.lower().replace('-', '_')) is not None:
        return True

    return False

def check_and_install_modules(script_dir, venv_dir):
    """Check if required modules are installed with correct versions and install if needed."""
    requirements_file = os.path.join(script_dir, "requirements.txt")

    if not os.path.exists(requirements_file):
        debug_print(f"Error: requirements.txt not found in {script_dir} if you are sure you have all requirements installed you bypass this script and call matterport-dl.py directly", is_error=True)
        sys.exit(1)

    # Get dynamic mapping of package names to import names
    package_to_import_mapping = get_package_to_import_mapping()

    required_modules = parse_requirements(requirements_file)
    missing_modules = []

    # Check if modules are installed with correct versions
    for module_name, required_version in required_modules.items():
        try:
            # Check if the module is installed
            if not is_module_installed(module_name, package_to_import_mapping):
                debug_print(f"Module {module_name} is not installed")
                missing_modules.append(module_name)
                continue

            # If a specific version is required, check the version
            if required_version:
                try:
                    installed_version = importlib.metadata.version(module_name)
                    if required_version.startswith('>='):
                        version_to_check = required_version[2:]
                        if parse_version(installed_version) < parse_version(version_to_check):
                            debug_print(f"Module {module_name} version {installed_version} is older than required {required_version}")
                            missing_modules.append(module_name)
                    elif installed_version != required_version:
                        debug_print(f"Module {module_name} version {installed_version} doesn't match required {required_version}")
                        missing_modules.append(module_name)
                except importlib.metadata.PackageNotFoundError:
                    # If we can't find metadata but the module is importable, it might be a built-in
                    # or installed in a unusual way. Let's assume it's ok unless it has a specific version req
                    if required_version and '==' in required_version:
                        debug_print(f"Module {module_name} metadata not found, marking for installation")
                        missing_modules.append(module_name)
        except Exception as e:
            # If there's any unexpected error checking the module, log it
            debug_print(f"Error checking module {module_name}: {e}", is_error=True)
            missing_modules.append(module_name)

    # If any modules are missing or have incorrect versions, install them
    if missing_modules:
        # Determine path to pip executable
        pip_executable = os.path.join(
            venv_dir,
            "Scripts" if sys.platform == "win32" else "bin",
            "pip"
        )

        debug_print(f"Installing/upgrading the following modules: {', '.join(missing_modules)}")
        try:
            # Use subprocess to run pip install
            subprocess.check_call([pip_executable, "install", "-r", requirements_file])

            # After installation, update our package-to-module mapping
            # This is important for later calls where we might need to check other modules
            package_to_import_mapping = get_package_to_import_mapping()
        except subprocess.CalledProcessError as e:
            debug_print(f"Error installing requirements: {e}", is_error=True)
            sys.exit(1)
    else:
        debug_print("All required modules are already installed with correct versions.")

    return package_to_import_mapping

def parse_version(version_string):
    """Simple version parser for comparison."""
    return tuple(map(int, re.findall(r'\d+', version_string)))

def run_matterport_dl(script_dir):
    """Run matterport-dl.py with any arguments passed to this script."""
    matterport_script = os.path.join(script_dir, "matterport-dl.py")

    debug_print(f"Running matterport-dl.py...")

    # Use the current Python interpreter to run matterport-dl.py
    # as we're already in the virtual environment at this point
    sys.path.insert(0, str(script_dir))
    matterdl = None
    try:
        matterdl = importlib.import_module("matterport-dl")
    except Exception:
        pass
    if matterdl is not None:
        matterdl.main()
    else:
        debug_print(f"Error running matterport-dl.py directly, trying subprocess...", is_error=True)
        process = subprocess.run([sys.executable, matterport_script] + sys.argv[1:])
        sys.exit(process.returncode)

def get_python_version():
    """Get the current Python version string."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

def store_external_python_version():
    """Store the current Python version in environment variable if not in venv."""
    os.environ[EXTERNAL_PY_VERSION_VAR] = get_python_version()

def check_external_python_version():
    """
    Check if external Python version is newer than current venv Python version.
    Warn if the external version has been upgraded since venv creation.
    """
    if EXTERNAL_PY_VERSION_VAR in os.environ:
        external_version = os.environ[EXTERNAL_PY_VERSION_VAR]
        current_version = get_python_version()

        debug_print(f"External Python version: {parse_version(external_version)} vs virtual env version: {parse_version(current_version)}")

        if parse_version(external_version) > parse_version(current_version):
            debug_print("Warning: External Python version has been upgraded since this virtual environment was created.", is_error=True)
            debug_print("To use the newer Python version, delete the 'venv' folder next to run.py and run this script again.", is_error=True)
            debug_print(f"External version: {external_version}, Current virtual env version: {current_version}", is_error=True)

def main():
    """Main function that orchestrates the entire process."""
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Setup virtual environment if needed
    venv_dir = os.path.join(script_dir, "venv")

    # Check if we're already in the correct virtual environment
    if not is_in_correct_venv(script_dir):
        # Store the external Python version before switching to venv
        store_external_python_version()
        # Ensure venv exists
        venv_dir = setup_venv(script_dir)
        # Restart this script in the virtual environment
        run_in_venv(script_dir, venv_dir)
        # We should never reach here, as run_in_venv will exit
        return

    # We're now running in the virtual environment

    # Check Python version
    check_python_version()

    # Check for required files
    check_required_files(script_dir)

    # Check and install required modules if needed
    check_and_install_modules(script_dir, venv_dir)

    # Check external Python version
    check_external_python_version()

    # Run matterport-dl.py
    run_matterport_dl(script_dir)

if __name__ == "__main__":
    main()
