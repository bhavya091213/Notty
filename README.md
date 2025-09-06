# Notty


## Enhances notes while you take them

Run this script in the background while you take notes in MarkDown and you can have perfect notes

## Setup (MacOS)
Follow steps below to get this script working

### Venv
Create a ```.venv``` within the directory you clone this source code to. Install the pip dependencies below
1. ```pip install watchdog```
2. ```pip install -q -U google-genai```


### Environment Variables
Create a file named ```.profile``` within your User directory. Open new terminal window and run the commands found below:
- To create
```
touch ~/.profile
```
- To edit
```
nano ~/.profile
```

To set up the environment variable, copy the text below into the second line of your ```.profile```
```
export GEMENI_KEY="YOUR_KEY_HERE"
```
- **ENSURE YOU DO NOT PUT SPACES OTHER THAN THE ONE BETWEEN export AND GEMENI_KEY,** you will get an error describing bad assignment on line 2

Return to your ```.venv``` and source your environment
```
source ~/.profile
```

## Running Script
1. The script takes one parameter: a path to the file you are editing. Obtain the path simply by running the command below
```
realpath filename.md
```
*Do not worry about sanitizng filepath for whitespace, the script accounts for that*
2. cd into the directory of the script and run the command below
```
python3 main.py <YOUR_PATH_TO_FILE_HERE>
```
*note possibly need to change ```python3``` to whatever works for your system*
