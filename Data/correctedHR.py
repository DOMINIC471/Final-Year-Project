import pandas as pd
import re

# Path to the input and output files
input_file = 'hr.csv'  # Update with the correct path
output_file = 'extracted_hr_data.csv'  # Update with the desired output path

# Create empty lists to store extracted data
bed_numbers = []
heart_rates = []

# Open the input CSV and read line by line
with open(input_file, 'r') as file:
    for line in file:
        # Check if the line contains "Bed"
        if 'Bed' in line:
            # Extract the bed number using regex
            bed_match = re.search(r'"Bed (\d+)"', line)
            # Extract the heart rate after "HR";
            hr_match = re.search(r'"HR";"(\d+)"', line)
            
            # If both matches are found, append to the lists
            if bed_match and hr_match:
                bed_numbers.append(bed_match.group(1))  # Capture bed number
                heart_rates.append(int(hr_match.group(1)))  # Capture heart rate as integer

# Combine into a DataFrame
data = pd.DataFrame({
    'Bed Number': bed_numbers,
    'Heart Rate': heart_rates
})

# Write the extracted data to a new CSV file
data.to_csv(output_file, index=False)

print(f"Extracted data has been saved to {output_file}")
