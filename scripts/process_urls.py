import json
import os
import random  # Add import for random module

# Get the absolute path of the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the project root (one level up from script_dir)
project_root = os.path.dirname(script_dir)

# Define the input and output file paths relative to the project root
input_file_path = os.path.join(project_root, "data", "all_urls.json")
output_file_path = os.path.join(project_root, "data", "uidaho_urls.json")


def main():
    """Reads URLs from input file, selects 100 random URLs, and writes them to the output file."""
    try:
        # Read the input JSON file
        with open(input_file_path, "r", encoding="utf-8") as f_in:
            all_urls = json.load(f_in)

        # Ensure the input is a list
        if not isinstance(all_urls, list):
            raise TypeError(
                f"Expected a list in {input_file_path}, but got {type(all_urls)}"
            )

        # Get 100 random URLs (or all if the file has less than 100)
        sample_size = min(100, len(all_urls))
        selected_urls = random.sample(all_urls, sample_size)

        # Create the output directory if it doesn't exist (relative to project root)
        output_dir = os.path.dirname(output_file_path)
        os.makedirs(output_dir, exist_ok=True)

        # Write the selected URLs to the output JSON file
        with open(output_file_path, "w", encoding="utf-8") as f_out:
            json.dump(
                selected_urls, f_out, indent=2
            )  # Use indent=2 for pretty printing

        # Use relative paths for user-friendly output
        relative_input_path = os.path.relpath(input_file_path, project_root)
        relative_output_path = os.path.relpath(output_file_path, project_root)
        print(
            f"Successfully wrote {len(selected_urls)} random URLs from '{relative_input_path}' to '{relative_output_path}'"
        )

    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {input_file_path}")
    except TypeError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
