import csv
import json

# This is not general purpose but a one-time script to convert a specific CSV file to JSON format.
csv_file_path = "/Users/colesummers/Documents/GitHub/profile-extractor/docs/research/second_pass/Example-categories-for-profiles.csv"
json_file_path = "output_urls.json"

urls = []

try:
    with open(csv_file_path, mode="r", encoding="utf-8") as infile:
        reader = csv.reader(infile)
        header = next(reader)  # Skip the header row
        for row in reader:
            if row:  # Ensure row is not empty
                urls.append(row[0])  # Add the URL from the first column

    with open(json_file_path, mode="w", encoding="utf-8") as outfile:
        json.dump(urls, outfile, indent=4)  # Write the list as a JSON array

    print(f"Successfully converted {csv_file_path} to {json_file_path}")

except FileNotFoundError:
    print(f"Error: The file {csv_file_path} was not found.")
except Exception as e:
    print(f"An error occurred: {e}")
