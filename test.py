import os

# Get the value of your key variable from the environment
# The 'None' here is a default value if the variable isn't found
my_key = os.getenv('GEMINI_KEY', None)

if my_key:
    print(f"Key variable found: {my_key}")
    # You can now use 'my_key' in your application
else:
    print("Key variable not found. Please ensure it's set and the shell is sourced.")
