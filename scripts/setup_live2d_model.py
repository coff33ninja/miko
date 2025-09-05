
import os
import sys
import glob

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
STATIC_DIR = os.path.join(PROJECT_ROOT, 'src', 'web', 'static')
MODELS_DIR = os.path.join(STATIC_DIR, 'models')
ENV_FILE = os.path.join(PROJECT_ROOT, '.env')

def update_env_file(key, value):
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            lines = f.readlines()

    found = False
    with open(ENV_FILE, 'w') as f:
        for line in lines:
            if line.startswith(f'{key}=') :
                f.write(f'{key}={value}\n')
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f'{key}={value}\n')
    print(f"Updated {key} in .env to: {value}")

def find_model_config(model_name):
    model_path = os.path.join(MODELS_DIR, model_name)
    if not os.path.isdir(model_path):
        print(f"Error: Model directory '{model_path}' not found.")
        return None

    found_configs = []
    # Search up to 3 layers deep
    for root, dirs, files in os.walk(model_path):
        # Calculate current depth relative to model_path
        current_depth = root[len(model_path):].count(os.sep)
        if current_depth > 3:
            del dirs[:]
            continue

        for file in files:
            if file.endswith('.model3.json'):
                found_configs.append(os.path.join(root, file))

    if not found_configs:
        print(f"No *.model3.json found in '{model_path}' up to 3 layers deep.")
        return None
    elif len(found_configs) == 1:
        return found_configs[0]
    else:
        print("Multiple *.model3.json files found. Please select one:")
        for i, config_path in enumerate(found_configs):
            print(f"{i + 1}. {config_path}")
        while True:
            try:
                choice = int(input("Enter number of desired config: "))
                if 1 <= choice <= len(found_configs):
                    return found_configs[choice - 1]
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")

def main():
    if len(sys.argv) != 2:
        print("Usage: python setup_live2d_model.py <model_folder_name>")
        sys.exit(1)

    model_name = sys.argv[1]
    model_config_path = find_model_config(model_name)

    if model_config_path:
        # Calculate path relative to STATIC_DIR
        relative_path = os.path.relpath(model_config_path, STATIC_DIR).replace(os.sep, '/')
        update_env_file('LIVE2D_MODEL_CONFIG_PATH', relative_path)
    else:
        print("Failed to set LIVE2D_MODEL_CONFIG_PATH.")

if __name__ == '__main__':
    main()
