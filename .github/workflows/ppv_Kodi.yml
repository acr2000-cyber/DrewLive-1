import re

# Read the input file
with open('PPVLand.m3u8', 'r') as file:
    content = file.read()

# Define the pattern and replacement
pattern = r'\.m3u8'
replacement = '.m3u8|User-Agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%3B%20rv%3A143.0%29%20Gecko%2F20100101%20Firefox%2F143.0&Referer=https%3A%2F%2Fppv.to%2F&Origin=https%3A%2F%2Fppv.to'

# Replace all occurrences
content = re.sub(pattern, replacement, content)

# Write the output file
with open('PPVLand.m3u8', 'w') as file:
    file.write(content)

print("✅ M3U8 file processed successfully")
