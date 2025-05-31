#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Set the OpenAI API key if provided as an argument
if [ ! -z "$1" ]; then
  export OPENAI_API_KEY=$1
fi

# Run the job finder script
python job_finder.py

# Deactivate the virtual environment
deactivate 